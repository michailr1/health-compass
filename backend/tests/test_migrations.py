"""Integration tests for the current Alembic migration boundary."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

TEST_DATABASE_ENV = "TEST_DATABASE_MIGRATOR_URL"
LEGACY_TABLES = {"audit_events", "processing_jobs", "service_metadata"}
MAGIC_LINK_SIGNATURES = (
    "health_compass.app_issue_email_login_token(text,text,timestamp with time zone,text,text)",
    "health_compass.app_consume_email_login_token(text)",
)


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


def _current_database_revision(engine) -> str:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT version_num FROM health_compass.alembic_version")
        ).scalar_one()


def _search_path_value(config: list[str] | None) -> str | None:
    for entry in config or []:
        if entry.startswith("search_path="):
            return entry.split("=", 1)[1].strip('"')
    return None


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


def _assert_clinical_context_head(engine, expected_head: str) -> None:
    clinical_tables = {
        "profile_conditions",
        "profile_allergies",
        "profile_medications",
        "profile_supplements",
        "profile_clinical_safety_flags",
        "profile_clinical_reviews",
    }
    with engine.connect() as connection:
        assert _current_database_revision(engine) == expected_head
        tables = set(
            connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'health_compass'"
                )
            ).scalars()
        )
        assert clinical_tables <= tables

        rls_rows = connection.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'health_compass' "
                "AND relname = ANY(:tables)"
            ),
            {"tables": sorted(clinical_tables)},
        ).all()
        assert len(rls_rows) == len(clinical_tables)
        assert all(row.relrowsecurity and row.relforcerowsecurity for row in rls_rows)

        app_delete_grants = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE grantee = 'health_compass_app' "
                "AND table_schema = 'health_compass' "
                "AND table_name = ANY(:tables) "
                "AND privilege_type = 'DELETE'"
            ),
            {"tables": sorted(clinical_tables)},
        ).scalar_one()
        assert app_delete_grants == 0

        public_helper = connection.execute(
            text(
                "SELECT has_function_privilege("
                "'public', 'health_compass.app_duplicate_user_activity(uuid)', 'EXECUTE')"
            )
        ).scalar_one()
        app_helper = connection.execute(
            text(
                "SELECT has_function_privilege("
                "'health_compass_app', "
                "'health_compass.app_duplicate_user_activity(uuid)', 'EXECUTE')"
            )
        ).scalar_one()
        assert public_helper is False
        assert app_helper is False


def _assert_revision_0063_hardening(engine) -> None:
    with engine.connect() as connection:
        assert _current_database_revision(engine) == "0063"
        tables = set(
            connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'health_compass' "
                    "AND table_name = ANY(:tables)"
                ),
                {"tables": sorted(LEGACY_TABLES)},
            ).scalars()
        )
        assert tables == set()

        for signature in MAGIC_LINK_SIGNATURES:
            row = connection.execute(
                text(
                    "SELECT p.proconfig, owner.rolname AS owner, "
                    "has_function_privilege('health_compass_app', p.oid, 'EXECUTE') AS app_execute, "
                    "has_function_privilege('public', p.oid, 'EXECUTE') AS public_execute "
                    "FROM pg_proc p "
                    "JOIN pg_roles owner ON owner.oid = p.proowner "
                    "WHERE p.oid = CAST(:signature AS regprocedure)"
                ),
                {"signature": signature},
            ).one()
            assert _search_path_value(row.proconfig) == ""
            assert row.owner == "health_compass_rls_definer"
            assert row.app_execute is True
            assert row.public_execute is False


def _assert_revision_0062_legacy_boundary(engine) -> None:
    with engine.connect() as connection:
        assert _current_database_revision(engine) == "0062"
        tables = set(
            connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'health_compass' "
                    "AND table_name = ANY(:tables)"
                ),
                {"tables": sorted(LEGACY_TABLES)},
            ).scalars()
        )
        assert tables == LEGACY_TABLES

        grants = connection.execute(
            text(
                "SELECT table_name, privilege_type "
                "FROM information_schema.role_table_grants "
                "WHERE grantee = 'health_compass_app' "
                "AND table_schema = 'health_compass' "
                "AND table_name = ANY(:tables) "
                "AND privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')"
            ),
            {"tables": sorted(LEGACY_TABLES)},
        ).all()
        assert len(grants) == 12

        for signature in MAGIC_LINK_SIGNATURES:
            config = connection.execute(
                text(
                    "SELECT p.proconfig FROM pg_proc p "
                    "WHERE p.oid = CAST(:signature AS regprocedure)"
                ),
                {"signature": signature},
            ).scalar_one()
            assert _search_path_value(config) == "health_compass, pg_temp"


def test_migration_0021_0022_cycle_and_current_head() -> None:
    """Verify the historical 0021↔0022 boundary, then the current full head."""
    config = _get_alembic_config()
    engine = create_engine(_get_migrator_url())
    expected_head = ScriptDirectory.from_config(config).get_current_head()
    assert expected_head is not None

    try:
        upgrade(config, "0022")
        _assert_revision_0022(engine)

        downgrade(config, "0021")
        _assert_revision_0021(engine)

        upgrade(config, "0022")
        _assert_revision_0022(engine)

        upgrade(config, "head")
        _assert_clinical_context_head(engine, expected_head)

        downgrade(config, "-1")
        assert _current_database_revision(engine) != expected_head

        upgrade(config, "head")
        _assert_clinical_context_head(engine, expected_head)
    finally:
        engine.dispose()


def test_hc020_0062_0063_boundary_is_reversible() -> None:
    """The HC-020 security cleanup must have a true 0062 downgrade."""
    config = _get_alembic_config()
    engine = create_engine(_get_migrator_url())

    try:
        upgrade(config, "0063")
        _assert_revision_0063_hardening(engine)

        downgrade(config, "0062")
        _assert_revision_0062_legacy_boundary(engine)

        upgrade(config, "0063")
        _assert_revision_0063_hardening(engine)

        upgrade(config, "head")
    finally:
        engine.dispose()
