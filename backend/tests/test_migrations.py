"""Tests for Alembic migrations."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest
from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

TEST_DATABASE_ENV = "TEST_DATABASE_MIGRATOR_URL"


def _get_migrator_url() -> str:
    """Return a dedicated migration-test database URL or skip safely."""
    url = os.environ.get(TEST_DATABASE_ENV, "").strip()
    if not url:
        pytest.skip(
            f"{TEST_DATABASE_ENV} is not configured; migration tests require a dedicated test database"
        )

    database_name = urlsplit(url.replace("postgresql+psycopg://", "postgresql://", 1)).path.lstrip("/")
    if not database_name.endswith("_test"):
        pytest.fail(
            f"{TEST_DATABASE_ENV} must point to a database whose name ends with '_test'"
        )

    return url


def _get_alembic_config() -> Config:
    """Return Alembic config pointing to the dedicated test database."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", _get_migrator_url())
    return alembic_cfg


def _run_migration(connection, alembic_cfg, target_revision: str | None = None):
    """Run Alembic migration to target revision.

    If target_revision is None, downgrade to base (no revision).
    """
    script = ScriptDirectory.from_config(alembic_cfg)

    def upgrade(rev, context):
        if target_revision is None:
            return script._upgrade_revs("base", rev)
        return script._upgrade_revs(target_revision, rev)

    with EnvironmentContext(alembic_cfg, script, fn=upgrade) as ec:
        ec.configure(
            connection=connection,
            version_table_schema="health_compass",
            include_schemas=True,
        )
        ec.run_migrations()


def _run_downgrade(connection, alembic_cfg):
    """Run Alembic downgrade to base using the downgrade direction."""
    from alembic.command import downgrade as alembic_downgrade

    alembic_downgrade(alembic_cfg, "base")


@pytest.mark.order(1)
def test_migration_upgrade():
    """Test that alembic upgrade head works on a clean test database."""
    alembic_cfg = _get_alembic_config()
    engine = create_engine(_get_migrator_url())
    with engine.begin() as conn:
        _run_migration(conn, alembic_cfg, "head")

        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'health_compass' "
                "ORDER BY table_name"
            )
        )
        tables = [row[0] for row in result]
        assert "service_metadata" in tables
        assert "audit_events" in tables
        assert "processing_jobs" in tables
        assert "body_measurements" in tables
        assert "profile_audit_events" in tables
        assert "user_consents" in tables

        result = conn.execute(text("SELECT version_num FROM health_compass.alembic_version"))
        version = result.scalar()
        assert version == "0022"

        rls_rows = conn.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'health_compass' "
                "AND relname IN ('body_measurements', 'profile_audit_events', 'user_consents')"
            )
        ).all()
        assert len(rls_rows) == 3
        assert all(row[1] and row[2] for row in rls_rows)

        public_execute = conn.execute(
            text(
                "SELECT has_function_privilege("
                "'public', "
                "'health_compass.app_can_edit_profile(uuid)', "
                "'EXECUTE')"
            )
        ).scalar_one()
        assert public_execute is False


@pytest.mark.order(2)
def test_migration_downgrade():
    """Test that alembic downgrade works on the dedicated test database."""
    alembic_cfg = _get_alembic_config()
    engine = create_engine(_get_migrator_url())
    with engine.begin() as conn:
        _run_downgrade(conn, alembic_cfg)

        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'health_compass' "
                "AND table_name != 'alembic_version' "
                "ORDER BY table_name"
            )
        )
        tables = [row[0] for row in result]
        assert len(tables) == 0, f"Tables still exist: {tables}"


@pytest.mark.order(3)
def test_migration_upgrade_after_downgrade():
    """Test that upgrade works again after downgrade."""
    alembic_cfg = _get_alembic_config()
    engine = create_engine(_get_migrator_url())
    with engine.begin() as conn:
        _run_migration(conn, alembic_cfg, "head")

        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'health_compass' "
                "ORDER BY table_name"
            )
        )
        tables = [row[0] for row in result]
        assert "service_metadata" in tables
        assert "audit_events" in tables
        assert "processing_jobs" in tables
        assert "body_measurements" in tables
        assert "profile_audit_events" in tables
        assert "user_consents" in tables
