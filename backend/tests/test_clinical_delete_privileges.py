"""Regression tests for effective Clinical Context DELETE privileges."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

CLINICAL_TABLES = (
    "profile_conditions",
    "profile_allergies",
    "profile_medications",
    "profile_supplements",
    "profile_clinical_safety_flags",
    "profile_clinical_reviews",
)


def _migrator_url() -> str:
    url = os.environ.get("TEST_DATABASE_MIGRATOR_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_MIGRATOR_URL is not configured")
    database_name = urlsplit(
        url.replace("postgresql+psycopg://", "postgresql://", 1)
    ).path.lstrip("/")
    if not database_name.endswith("_test"):
        pytest.fail("migration privilege tests require a *_test database")
    return url


def test_app_role_has_no_effective_delete_on_clinical_context_tables() -> None:
    engine = create_engine(_migrator_url())
    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM health_compass.alembic_version")
            ).scalar_one()
            assert revision == "0042"

            effective_delete = {
                table: connection.execute(
                    text(
                        "SELECT has_table_privilege("
                        "'health_compass_app', :qualified_table, 'DELETE')"
                    ),
                    {"qualified_table": f"health_compass.{table}"},
                ).scalar_one()
                for table in CLINICAL_TABLES
            }
            assert effective_delete == {table: False for table in CLINICAL_TABLES}

            direct_grants = connection.execute(
                text(
                    "SELECT table_name FROM information_schema.role_table_grants "
                    "WHERE grantee = 'health_compass_app' "
                    "AND table_schema = 'health_compass' "
                    "AND table_name = ANY(:tables) "
                    "AND privilege_type = 'DELETE'"
                ),
                {"tables": list(CLINICAL_TABLES)},
            ).scalars().all()
            assert direct_grants == []
    finally:
        engine.dispose()
