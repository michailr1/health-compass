"""Integration checks for HC-013 auth-session security invariants."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration


def _migrator_url() -> str:
    url = os.environ.get("TEST_DATABASE_MIGRATOR_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_MIGRATOR_URL is not configured")
    database_name = urlsplit(
        url.replace("postgresql+psycopg://", "postgresql://", 1)
    ).path.lstrip("/")
    if not database_name.endswith("_test"):
        pytest.fail("session management tests require a *_test database")
    return url


def test_auth_sessions_keep_force_rls_and_layered_policies() -> None:
    engine = create_engine(_migrator_url())
    try:
        with engine.connect() as connection:
            row_security = connection.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'health_compass' AND c.relname = 'auth_sessions'"
                )
            ).one()
            assert tuple(row_security) == (True, True)

            policies = set(
                connection.execute(
                    text(
                        "SELECT policyname FROM pg_policies "
                        "WHERE schemaname = 'health_compass' AND tablename = 'auth_sessions'"
                    )
                ).scalars()
            )
            assert {
                "sessions_current_select",
                "sessions_current_update",
                "sessions_self_insert",
                "auth_sessions_self_select",
                "auth_sessions_self_update",
            }.issubset(policies)

            privileges = {
                privilege: connection.execute(
                    text(
                        "SELECT has_table_privilege("
                        "'health_compass_app', 'health_compass.auth_sessions', :privilege)"
                    ),
                    {"privilege": privilege},
                ).scalar_one()
                for privilege in ("SELECT", "UPDATE")
            }
            assert privileges == {"SELECT": True, "UPDATE": True}
    finally:
        engine.dispose()
