from __future__ import annotations

import os
import uuid

import psycopg
import pytest

ADMIN_DSN = os.getenv("HC_TEST_DATABASE_ADMIN_DSN")
APP_DSN = os.getenv("HC_TEST_DATABASE_APP_DSN")

pytestmark = pytest.mark.integration


def require_dsn(value: str | None, name: str) -> str:
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def test_declined_intent_can_be_claimed_for_separate_account() -> None:
    admin_dsn = require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN")
    app_dsn = require_dsn(APP_DSN, "HC_TEST_DATABASE_APP_DSN")

    candidate_user_id = uuid.uuid4()
    intent_id = uuid.uuid4()
    email = f"hc-separate-{candidate_user_id.hex}@example.test"
    browser_hash = "c" * 64

    with psycopg.connect(admin_dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO health_compass.users (id, email, display_name, status)
            VALUES (%s, %s, 'Separate account test', 'active')
            """,
            (candidate_user_id, email),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.account_link_intents (
              id, flow_type, status, normalized_email, candidate_user_id,
              initiating_provider, initiating_subject, required_provider,
              initiating_claims, browser_binding_hash, expires_at, declined_at
            ) VALUES (
              %s, 'google_first_email_existing', 'declined', %s, %s,
              'google', %s, 'email',
              jsonb_build_object('email', %s::text, 'email_verified', true),
              %s, now() + interval '15 minutes', now()
            )
            """,
            (
                intent_id,
                email,
                candidate_user_id,
                f"google-{candidate_user_id.hex}",
                email,
                browser_hash,
            ),
        )

    try:
        with psycopg.connect(app_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT health_compass.app_claim_declined_link_for_separate_account(%s, %s)
                """,
                (intent_id, browser_hash),
            )
            payload = cursor.fetchone()[0]

        assert payload["normalized_email"] == email
        assert payload["provider"] == "google"

        with psycopg.connect(admin_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, declined_at, completed_at
                FROM health_compass.account_link_intents
                WHERE id = %s
                """,
                (intent_id,),
            )
            assert cursor.fetchone() == ("cancelled", None, None)
    finally:
        with psycopg.connect(admin_dsn) as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM health_compass.users WHERE id = %s", (candidate_user_id,))
