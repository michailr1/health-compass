"""HC-015 Slice C: scanner-safe Email Magic Link lifecycle (CR-03).

GET must never consume the one-time token or create a session; only the
explicit POST from the interstitial does. Replay and expiry stay rejected and
the raw token never appears in captured application logs.
"""

from __future__ import annotations

import logging
import os
import uuid

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.magic_links import hash_magic_token, new_magic_token

pytestmark = pytest.mark.integration

ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"


def _admin_url() -> str:
    url = os.environ.get(ADMIN_ENV, "").strip()
    if not url:
        pytest.skip(f"{ADMIN_ENV} is not configured")
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _issue_token(email: str, *, expired: bool = False) -> str:
    token = new_magic_token()
    interval = "- interval '1 minute'" if expired else "+ interval '15 minutes'"
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        connection.execute(
            f"""
            INSERT INTO health_compass.email_login_tokens (email, token_hash, expires_at)
            VALUES (%s, %s, now() {interval})
            """,
            (email, hash_magic_token(token)),
        )
    return token


def _token_state(token: str) -> tuple[bool, bool] | None:
    """Return (used, session_exists_for_email) for the token's email."""
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        row = connection.execute(
            """
            SELECT email, used_at IS NOT NULL
            FROM health_compass.email_login_tokens
            WHERE token_hash = %s
            """,
            (hash_magic_token(token),),
        ).fetchone()
        if row is None:
            return None
        email, used = row
        sessions = connection.execute(
            """
            SELECT count(*)
            FROM health_compass.auth_sessions s
            JOIN health_compass.users u ON u.id = s.user_id
            WHERE u.email = %s AND s.revoked_at IS NULL
            """,
            (email,),
        ).fetchone()[0]
        return used, sessions > 0


def _cleanup(email: str) -> None:
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        connection.execute(
            "DELETE FROM health_compass.email_login_tokens WHERE email = %s", (email,)
        )
        connection.execute(
            """
            DELETE FROM health_compass.auth_sessions s
            USING health_compass.users u
            WHERE s.user_id = u.id AND u.email = %s
            """,
            (email,),
        )
        connection.execute(
            "DELETE FROM health_compass.user_identities WHERE subject = %s", (email,)
        )
        connection.execute(
            """
            DELETE FROM health_compass.workspace_members wm
            USING health_compass.workspaces w, health_compass.users u
            WHERE wm.workspace_id = w.id AND w.created_by_user_id = u.id AND u.email = %s
            """,
            (email,),
        )
        connection.execute(
            """
            DELETE FROM health_compass.profile_permissions pp
            USING health_compass.health_profiles hp, health_compass.users u
            WHERE pp.profile_id = hp.id AND hp.owner_user_id = u.id AND u.email = %s
            """,
            (email,),
        )
        connection.execute(
            """
            DELETE FROM health_compass.health_profiles hp
            USING health_compass.users u
            WHERE hp.owner_user_id = u.id AND u.email = %s
            """,
            (email,),
        )
        connection.execute(
            """
            DELETE FROM health_compass.workspaces w
            USING health_compass.users u
            WHERE w.created_by_user_id = u.id AND u.email = %s
            """,
            (email,),
        )
        connection.execute("DELETE FROM health_compass.users WHERE email = %s", (email,))


def _get_client() -> AsyncClient:
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _dispose_app_engine() -> None:
    from app.db.session import engine

    await engine.dispose()


async def test_scanner_get_never_consumes_and_post_consumes_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    email = f"magic-{uuid.uuid4().hex}@example.test"
    token = _issue_token(email)

    try:
        with caplog.at_level(logging.DEBUG):
            async with _get_client() as client:
                # Scanner/prefetch opens the link repeatedly: neutral page, no writes.
                for _ in range(3):
                    page = await client.get("/auth/email/consume", params={"token": token})
                    assert page.status_code == 200
                    assert "Войти" in page.text
                    assert page.headers["cache-control"] == "no-store"
                    assert page.headers["referrer-policy"] == "no-referrer"
                assert _token_state(token) == (False, False)

                # The human clicks the interstitial button: POST consumes once.
                consumed = await client.post(
                    "/auth/email/consume", data={"token": token}
                )
                assert consumed.status_code == 303
                assert consumed.headers["location"].endswith("/app")
                assert "hc_session=" in consumed.headers.get("set-cookie", "")
                assert _token_state(token) == (True, True)

            # Replay of the same token must fail without another session.
            async with _get_client() as client:
                replayed = await client.post(
                    "/auth/email/consume", data={"token": token}
                )
                assert replayed.status_code == 303
                assert "status=invalid" in replayed.headers["location"]
                assert "hc_session=" not in replayed.headers.get("set-cookie", "")

        # The raw token must never reach application/server log records; the
        # httpx *test client* logger echoes the request URL and is excluded.
        for record in caplog.records:
            if record.name.startswith(("httpx", "httpcore")):
                continue
            assert token not in record.getMessage(), record.name
            assert token not in str(getattr(record, "path", "")), record.name
    finally:
        await _dispose_app_engine()
        _cleanup(email)


async def test_expired_token_is_rejected_by_post() -> None:
    email = f"magic-expired-{uuid.uuid4().hex}@example.test"
    token = _issue_token(email, expired=True)
    try:
        async with _get_client() as client:
            response = await client.post("/auth/email/consume", data={"token": token})
        assert response.status_code == 303
        assert "status=invalid" in response.headers["location"]
        assert _token_state(token) == (False, False)
    finally:
        await _dispose_app_engine()
        _cleanup(email)


async def test_cross_origin_post_is_rejected() -> None:
    email = f"magic-origin-{uuid.uuid4().hex}@example.test"
    token = _issue_token(email)
    try:
        async with _get_client() as client:
            response = await client.post(
                "/auth/email/consume",
                data={"token": token},
                headers={"Origin": "https://evil.example"},
            )
        assert response.status_code == 403
        assert _token_state(token) == (False, False)
    finally:
        await _dispose_app_engine()
        _cleanup(email)


async def test_malformed_token_gets_friendly_redirect_without_db_write() -> None:
    async with _get_client() as client:
        page = await client.get("/auth/email/consume", params={"token": "short"})
        assert page.status_code == 303
        assert "status=invalid" in page.headers["location"]

        posted = await client.post("/auth/email/consume", data={"token": "<script>"})
        assert posted.status_code == 303
        assert "status=invalid" in posted.headers["location"]
    await _dispose_app_engine()
