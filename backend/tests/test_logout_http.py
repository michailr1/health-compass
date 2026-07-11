"""HC-015 Slice C: logout is POST-only and GET never changes state (CR-18)."""

from __future__ import annotations

import datetime
import os
import uuid

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.session_tokens import hash_token, new_session_token

pytestmark = pytest.mark.integration

ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"


def _admin_url() -> str:
    url = os.environ.get(ADMIN_ENV, "").strip()
    if not url:
        pytest.skip(f"{ADMIN_ENV} is not configured")
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _seed_session() -> tuple[uuid.UUID, str]:
    user_id = uuid.uuid4()
    token = new_session_token()
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        connection.execute(
            """
            INSERT INTO health_compass.users (id, email, display_name, status)
            VALUES (%s, %s, 'Logout test', 'active')
            """,
            (user_id, f"logout-{user_id.hex}@example.test"),
        )
        connection.execute(
            """
            INSERT INTO health_compass.auth_sessions (id, user_id, session_token_hash, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (
                uuid.uuid4(),
                user_id,
                hash_token(token),
                datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
            ),
        )
    return user_id, token


def _session_revoked(token: str) -> bool:
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        row = connection.execute(
            """
            SELECT revoked_at IS NOT NULL
            FROM health_compass.auth_sessions
            WHERE session_token_hash = %s
            """,
            (hash_token(token),),
        ).fetchone()
    assert row is not None
    return bool(row[0])


def _cleanup(user_id: uuid.UUID) -> None:
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        connection.execute(
            "DELETE FROM health_compass.auth_sessions WHERE user_id = %s", (user_id,)
        )
        connection.execute("DELETE FROM health_compass.users WHERE id = %s", (user_id,))


def _get_client(token: str | None = None) -> AsyncClient:
    from app.main import app

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    if token is not None:
        client.cookies.set(settings.session_cookie_name, token)
    return client


async def _dispose_app_engine() -> None:
    from app.db.session import engine

    await engine.dispose()


async def test_get_logout_is_rejected_and_does_not_revoke() -> None:
    user_id, token = _seed_session()
    try:
        async with _get_client(token) as client:
            response = await client.get("/auth/logout")
        assert response.status_code == 405
        assert _session_revoked(token) is False
    finally:
        await _dispose_app_engine()
        _cleanup(user_id)


async def test_post_logout_revokes_local_session() -> None:
    user_id, token = _seed_session()
    try:
        async with _get_client(token) as client:
            response = await client.post("/auth/logout")
        assert response.status_code == 303
        assert _session_revoked(token) is True
    finally:
        await _dispose_app_engine()
        _cleanup(user_id)


async def test_cross_origin_post_logout_is_rejected() -> None:
    user_id, token = _seed_session()
    try:
        async with _get_client(token) as client:
            response = await client.post(
                "/auth/logout", headers={"Origin": "https://evil.example"}
            )
        assert response.status_code == 403
        assert _session_revoked(token) is False
    finally:
        await _dispose_app_engine()
        _cleanup(user_id)


async def test_same_origin_post_logout_is_accepted() -> None:
    user_id, token = _seed_session()
    try:
        async with _get_client(token) as client:
            response = await client.post(
                "/auth/logout", headers={"Origin": "https://health.funti.cc"}
            )
        assert response.status_code == 303
        assert _session_revoked(token) is True
    finally:
        await _dispose_app_engine()
        _cleanup(user_id)
