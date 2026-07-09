from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

ADMIN_DSN = os.getenv("HC_TEST_DATABASE_ADMIN_DSN")
APP_DSN = os.getenv("HC_TEST_DATABASE_APP_DSN")

pytestmark = pytest.mark.integration


def require_dsn(value: str | None, name: str) -> str:
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def test_concurrent_google_step_up_removes_one_email_identity() -> None:
    admin_dsn = require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN")
    app_dsn = require_dsn(APP_DSN, "HC_TEST_DATABASE_APP_DSN")

    user_id = uuid.uuid4()
    google_identity_id = uuid.uuid4()
    email_identity_id = uuid.uuid4()
    email = f"hc-remove-{user_id.hex}@example.test"
    google_subject = f"google-{user_id.hex}"
    browser_hash = "b" * 64
    state_hash = "s" * 64
    nonce_hash = "n" * 64
    pkce_hash = "p" * 64

    with psycopg.connect(admin_dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO health_compass.users (id, email, display_name, status)
            VALUES (%s, %s, 'Identity removal test', 'active')
            """,
            (user_id, email),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.user_identities (
              id, user_id, provider, subject, issuer, claims, last_seen_at
            ) VALUES
              (
                %s, %s, 'google', %s, 'https://accounts.google.com',
                jsonb_build_object('email', %s::text, 'email_verified', true), now()
              ),
              (
                %s, %s, 'email', %s, 'health-compass-email',
                jsonb_build_object('email', %s::text, 'email_verified', true), now()
              )
            """,
            (
                google_identity_id,
                user_id,
                google_subject,
                email,
                email_identity_id,
                user_id,
                email,
                email,
            ),
        )

    intent_id: uuid.UUID | None = None
    try:
        with psycopg.connect(app_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT health_compass.app_create_identity_removal_intent(
                  %s, %s, %s, now() + interval '15 minutes'
                )
                """,
                (user_id, email_identity_id, browser_hash),
            )
            removal = cursor.fetchone()[0]
            assert removal["target_provider"] == "email"
            assert removal["required_provider"] == "google"
            intent_id = uuid.UUID(removal["intent_id"])

            cursor.execute(
                """
                SELECT health_compass.app_prepare_identity_removal_google(
                  %s, %s, %s, %s, %s
                )
                """,
                (intent_id, browser_hash, state_hash, nonce_hash, pkce_hash),
            )
            assert cursor.fetchone()[0] is True

        def complete() -> dict:
            with psycopg.connect(app_dsn) as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT health_compass.app_complete_identity_removal_google(
                      %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        intent_id,
                        browser_hash,
                        state_hash,
                        nonce_hash,
                        pkce_hash,
                        google_subject,
                        email,
                    ),
                )
                return cursor.fetchone()[0]

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: complete(), range(2)))

        assert all(result["user_id"] == str(user_id) for result in results)
        assert all(result["intent_id"] == str(intent_id) for result in results)
        assert all(result["removed_provider"] == "email" for result in results)
        assert sorted(result["replayed"] for result in results) == [False, True]

        with psycopg.connect(admin_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT provider, count(*)
                FROM health_compass.user_identities
                WHERE user_id = %s
                GROUP BY provider
                ORDER BY provider
                """,
                (user_id,),
            )
            assert cursor.fetchall() == [("google", 1)]
            cursor.execute(
                "SELECT status FROM health_compass.identity_removal_intents WHERE id = %s",
                (intent_id,),
            )
            assert cursor.fetchone()[0] == "completed"

        with psycopg.connect(app_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT health_compass.app_create_identity_removal_intent(
                  %s, %s, %s, now() + interval '15 minutes'
                )
                """,
                (user_id, google_identity_id, browser_hash),
            )
            assert cursor.fetchone()[0] is None
    finally:
        with psycopg.connect(admin_dsn) as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM health_compass.users WHERE id = %s", (user_id,))
