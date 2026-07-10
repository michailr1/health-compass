"""Integration tests for Contextual Intake decision privileges."""

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
        pytest.fail("contextual intake tests require a *_test database")
    return url


def test_intake_decisions_are_append_only_for_app_role() -> None:
    engine = create_engine(_migrator_url())
    try:
        with engine.connect() as connection:
            privileges = {
                privilege: connection.execute(
                    text(
                        "SELECT has_table_privilege("
                        "'health_compass_app', "
                        "'health_compass.profile_intake_decisions', "
                        ":privilege)"
                    ),
                    {"privilege": privilege},
                ).scalar_one()
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
            }
            assert privileges == {
                "SELECT": True,
                "INSERT": True,
                "UPDATE": False,
                "DELETE": False,
            }

            force_rls = connection.execute(
                text(
                    "SELECT relforcerowsecurity FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'health_compass' "
                    "AND c.relname = 'profile_intake_decisions'"
                )
            ).scalar_one()
            assert force_rls is True
    finally:
        engine.dispose()
