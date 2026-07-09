from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from psycopg import errors

ADMIN_DSN = os.getenv("HC_TEST_DATABASE_ADMIN_DSN")
APP_DSN = os.getenv("HC_TEST_DATABASE_APP_DSN")
MIGRATOR_DSN = os.getenv("HC_TEST_DATABASE_MIGRATOR_DSN")

pytestmark = pytest.mark.integration


def require_dsn(value: str | None, name: str) -> str:
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def test_link_tables_have_enable_and_force_rls() -> None:
    dsn = require_dsn(MIGRATOR_DSN, "HC_TEST_DATABASE_MIGRATOR_DSN")
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'health_compass'
              AND c.relname IN ('account_link_intents', 'account_link_email_tokens')
            ORDER BY c.relname
            """
        )
        rows = cursor.fetchall()

    assert rows == [
        ("account_link_email_tokens", True, True),
        ("account_link_intents", True, True),
    ]


def test_app_role_cannot_read_link_tables_directly() -> None:
    dsn = require_dsn(APP_DSN, "HC_TEST_DATABASE_APP_DSN")
    for table in ("account_link_intents", "account_link_email_tokens"):
        with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
            with pytest.raises(errors.InsufficientPrivilege):
                cursor.execute(f"SELECT * FROM health_compass.{table} LIMIT 1")


def test_public_cannot_execute_account_link_functions() -> None:
    dsn = require_dsn(MIGRATOR_DSN, "HC_TEST_DATABASE_MIGRATOR_DSN")
    expected = {
        "app_complete_google_link_result",
        "app_consume_link_email_token_result",
        "app_create_account_link_intent",
        "app_decline_account_link",
        "app_issue_link_email_token",
        "app_prepare_google_link",
    }
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.proname,
                   EXISTS (
                     SELECT 1
                     FROM aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) acl
                     WHERE acl.grantee = 0
                       AND acl.privilege_type = 'EXECUTE'
                   ) AS public_execute,
                   has_function_privilege('health_compass_app', p.oid, 'EXECUTE') AS app_execute
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'health_compass'
              AND p.proname = ANY(%s)
            ORDER BY p.proname
            """,
            (sorted(expected),),
        )
        rows = cursor.fetchall()

    assert {row[0] for row in rows} == expected
    assert all(public_execute is False for _, public_execute, _ in rows)
    assert all(app_execute is True for _, _, app_execute in rows)


def test_security_definer_functions_use_empty_search_path_and_row_security_off() -> None:
    dsn = require_dsn(MIGRATOR_DSN, "HC_TEST_DATABASE_MIGRATOR_DSN")
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.proname, p.prosecdef, coalesce(p.proconfig, ARRAY[]::text[])
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'health_compass'
              AND p.proname LIKE 'app_%link%'
            ORDER BY p.proname
            """
        )
        rows = cursor.fetchall()

    assert rows
    for name, security_definer, config in rows:
        assert security_definer is True, name
        assert any(item.startswith("search_path=") for item in config), name
        assert "row_security=off" in config, name


def test_concurrent_link_email_completion_creates_one_identity() -> None:
    admin_dsn = require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN")
    app_dsn = require_dsn(APP_DSN, "HC_TEST_DATABASE_APP_DSN")

    user_id = uuid.uuid4()
    google_identity_id = uuid.uuid4()
    intent_id = uuid.uuid4()
    token_id = uuid.uuid4()
    email = f"hc-link-{user_id.hex}@example.test"
    google_subject = f"google-{user_id.hex}"
    browser_hash = "b" * 64
    token_hash = "t" * 64

    with psycopg.connect(admin_dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO health_compass.users (id, email, display_name, status)
            VALUES (%s, %s, %s, 'active')
            """,
            (user_id, email, "HC concurrency test"),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.user_identities (
              id, user_id, provider, subject, issuer, claims, last_seen_at
            ) VALUES (
              %s, %s, 'google', %s, 'https://accounts.google.com',
              jsonb_build_object('email', %s::text, 'email_verified', true), now()
            )
            """,
            (google_identity_id, user_id, google_subject, email),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.account_link_intents (
              id, flow_type, status, normalized_email, candidate_user_id,
              initiating_provider, initiating_subject, required_provider,
              initiating_claims, browser_binding_hash, expires_at
            ) VALUES (
              %s, 'settings_add_email', 'pending_confirmation', %s, %s,
              'google', %s, 'email',
              jsonb_build_object('email', %s::text, 'email_verified', true),
              %s, now() + interval '15 minutes'
            )
            """,
            (intent_id, email, user_id, google_subject, email, browser_hash),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.account_link_email_tokens (
              id, intent_id, purpose, token_hash, expires_at
            ) VALUES (%s, %s, 'link_email', %s, now() + interval '15 minutes')
            """,
            (token_id, intent_id, token_hash),
        )

    def complete() -> dict:
        with psycopg.connect(app_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT health_compass.app_consume_link_email_token_result(%s, %s, %s)
                """,
                (token_hash, browser_hash, "https://accounts.google.com"),
            )
            return cursor.fetchone()[0]

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: complete(), range(2)))

        assert all(result["user_id"] == str(user_id) for result in results)
        assert all(result["intent_id"] == str(intent_id) for result in results)
        assert sorted(result["replayed"] for result in results) == [False, True]

        with psycopg.connect(admin_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM health_compass.user_identities
                WHERE provider = 'email' AND subject = %s AND user_id = %s
                """,
                (email, user_id),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                "SELECT status FROM health_compass.account_link_intents WHERE id = %s",
                (intent_id,),
            )
            assert cursor.fetchone()[0] == "completed"
    finally:
        with psycopg.connect(admin_dsn) as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM health_compass.users WHERE id = %s", (user_id,))
