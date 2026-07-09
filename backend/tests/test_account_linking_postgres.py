from __future__ import annotations

import os

import psycopg
import pytest
from psycopg import errors

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
                   has_function_privilege('public', p.oid, 'EXECUTE') AS public_execute,
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
        assert "search_path=" in config, name
        assert "row_security=off" in config, name
