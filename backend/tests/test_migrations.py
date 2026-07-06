"""Tests for Alembic migrations."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

# Load .env file if present
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


def _get_alembic_config() -> Config:
    """Return Alembic config pointing to the test database."""
    alembic_cfg = Config("alembic.ini")
    url = os.environ.get(
        "DATABASE_MIGRATOR_URL",
        "postgresql+psycopg://health_compass_test_migrator:test@127.0.0.1:5433/health_compass_test",
    )
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    return alembic_cfg


def _get_migrator_url() -> str:
    return os.environ.get(
        "DATABASE_MIGRATOR_URL",
        "postgresql+psycopg://health_compass_test_migrator:test@127.0.0.1:5433/health_compass_test",
    )


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


def _get_current_revision(connection, alembic_cfg) -> str | None:
    """Get current Alembic revision from the database."""
    script = ScriptDirectory.from_config(alembic_cfg)

    def get_rev(rev, context):
        return rev

    with EnvironmentContext(alembic_cfg, script, fn=get_rev) as ec:
        ec.configure(connection=connection)
        ec.run_migrations()
    return None


@pytest.mark.order(1)
def test_migration_upgrade():
    """Test that alembic upgrade head works on a clean database."""
    alembic_cfg = _get_alembic_config()
    engine = create_engine(_get_migrator_url())
    with engine.begin() as conn:
        # Run upgrade
        _run_migration(conn, alembic_cfg, "head")

        # Verify tables exist
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

        # Verify alembic_version exists in health_compass schema
        result = conn.execute(
            text(
                "SELECT version_num FROM health_compass.alembic_version"
            )
        )
        version = result.scalar()
        assert version is not None


@pytest.mark.order(2)
def test_migration_downgrade():
    """Test that alembic downgrade works."""
    alembic_cfg = _get_alembic_config()
    engine = create_engine(_get_migrator_url())
    with engine.begin() as conn:
        # Downgrade to base using proper downgrade direction
        _run_downgrade(conn, alembic_cfg)

        # Verify tables are gone (alembic_version is managed by Alembic)
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
    """Test that upgrade works again after downgrade (idempotent)."""
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
