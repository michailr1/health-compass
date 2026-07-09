"""Integration tests for the current Alembic migration boundary."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import create_engine, text

TEST_DATABASE_ENV = "TEST_DATABASE_MIGRATOR_URL"


def _get_migrator_url() -> str:
    """Return a dedicated migration-test database URL or skip safely."""
    url = os.environ.get(TEST_DATABASE_ENV, "").strip()
    if not url:
        pytest.skip(
            f"{TEST_DATABASE_ENV} is not configured; migration tests require a dedicated test database"
        )

    database_name = urlsplit(
        url.replace("postgresql+psycopg://", "postgresql://", 1)
    ).path.lstrip("/")
    if not database_name.endswith("_test"):
        pytest.fail(
            f"{TEST_DATABASE_ENV} must point to a database whose name ends with '_test'"
        )
    return url


def _get_alembic_config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", _get_migrator_url())
    return config


def _assert_revision_0022(engine) -> None:
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT version_num FROM health_compass.alembic_version")
        ).scalar_one()
        assert version == "0022"

        tables = set(
            connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'health_compass'"
                )
            ).scalars()
        )
        assert {"body_measurements", "profile_audit_events", "user_consents"} <= tables

        rls_rows = connection.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'health_compass' "
                "AND relname IN ('body_measurements', 'profile_audit_events', 'user_consents')"
            )
        ).all()
        assert len(rls_rows) == 3
        assert all(row.relrowsecurity and row.relforcerowsecurity for row in rls_rows)

        public_execute = connection.execute(
            text(
                "SELECT has_function_privilege("
                "'public', "
                "'health_compass.app_can_edit_profile(uuid)', "
                "'EXECUTE')"
            )
        ).scalar_one()
        assert public_execute is False

        definer_create = connection.execute(
            text(
                "SELECT has_schema_privilege("
                "'health_compass_rls_definer', 'health_compass', 'CREATE')"
            )
        ).scalar_one()
        assert definer_create is False


def _assert_revision_0021(engine) -> None:
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT version_num FROM health_compass.alembic_version")
        ).scalar_one()
        assert version == "0021"

        tables = set(
            connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'health_compass'"
                )
            ).scalars()
        )
        assert "body_measurements" not in tables
        assert "profile_audit_events" not in tables
        assert "user_consents" not in tables

        new_columns = connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'health_compass' "
                "AND table_name = 'health_profiles' "
                "AND column_name IN ('height_cm', 'timezone', 'updated_at')"
            )
        ).scalars().all()
        assert new_columns == []

        helper_exists = connection.execute(
            text("SELECT to_regprocedure('health_compass.app_can_edit_profile(uuid)')")
        ).scalar_one()
        assert helper_exists is None


def test_migration_0021_0022_cycle() -> None:
    """Verify clean upgrade and the required 0021 -> 0022 -> 0021 -> 0022 cycle."""
    config = _get_alembic_config()
    engine = create_engine(_get_migrator_url())
    try:
        upgrade(config, "head")
        _assert_revision_0022(engine)

        downgrade(config, "0021")
        _assert_revision_0021(engine)

        upgrade(config, "0022")
        _assert_revision_0022(engine)
    finally:
        engine.dispose()
