"""HC-015+ full migration cycle in an isolated database.

Runs ``upgrade head → downgrade base → upgrade head`` against a dedicated
throwaway database (never the shared test DB, never production) and asserts
security-critical invariants after the second upgrade.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from alembic.command import downgrade, upgrade
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

CYCLE_DB = "health_compass_cycle_test"

DEFINER_FUNCTIONS = (
    "app_duplicate_user_activity(uuid)",
    "app_duplicate_user_activity_pre_documents(uuid)",
    "app_assess_duplicate_user_pair(uuid, uuid)",
    "app_apply_duplicate_absorption(uuid)",
    "app_can_edit_profile(uuid)",
    "app_can_view_profile(uuid)",
    "app_can_view_document(uuid)",
    "app_lookup_identity_user_id(text, text)",
    "app_consume_email_login_token(text)",
)

FORCE_RLS_TABLES = (
    "users",
    "user_identities",
    "workspaces",
    "workspace_members",
    "health_profiles",
    "profile_permissions",
    "body_measurements",
    "profile_audit_events",
    "user_consents",
    "profile_conditions",
    "profile_allergies",
    "profile_medications",
    "profile_supplements",
    "profile_clinical_safety_flags",
    "profile_clinical_reviews",
    "profile_intake_decisions",
    "profile_documents",
    "document_processing_jobs",
)

CANONICAL_TABLES = (
    "profile_conditions",
    "profile_allergies",
    "profile_medications",
    "profile_supplements",
)

DOCUMENT_TABLES = (
    "profile_documents",
    "document_processing_jobs",
)


def _admin_url() -> str:
    url = os.environ.get("TEST_DATABASE_ADMIN_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_ADMIN_URL is not configured")
    return url


def _cycle_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    return urlunsplit(
        (parts.scheme, parts.netloc, f"/{CYCLE_DB}", parts.query, parts.fragment)
    )


def _admin_dsn(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _provision_cycle_database(admin_url: str) -> None:
    with psycopg.connect(_admin_dsn(admin_url), autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {CYCLE_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {CYCLE_DB} OWNER health_compass_migrator")
        conn.execute(f"GRANT CONNECT ON DATABASE {CYCLE_DB} TO health_compass_app")
    with psycopg.connect(_admin_dsn(_cycle_url(admin_url)), autocommit=True) as conn:
        conn.execute("CREATE SCHEMA health_compass AUTHORIZATION health_compass_migrator")
        conn.execute("GRANT USAGE ON SCHEMA health_compass TO health_compass_app")


def _drop_cycle_database(admin_url: str) -> None:
    with psycopg.connect(_admin_dsn(admin_url), autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {CYCLE_DB} WITH (FORCE)")


def _migrator_cycle_url() -> str:
    url = os.environ.get("TEST_DATABASE_MIGRATOR_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_MIGRATOR_URL is not configured")
    return _cycle_url(url)


def test_full_migration_cycle_restores_all_security_invariants() -> None:
    admin_url = _admin_url()
    if not urlsplit(admin_url.replace("postgresql+psycopg://", "postgresql://", 1)).path.endswith(
        "_test"
    ):
        pytest.fail("migration cycle test requires a *_test admin database URL")

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", _migrator_cycle_url())
    expected_head = ScriptDirectory.from_config(config).get_current_head()
    assert expected_head is not None

    heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
    assert len(heads) == 1, f"parallel Alembic heads detected: {heads}"

    _provision_cycle_database(admin_url)
    try:
        upgrade(config, "head")
        downgrade(config, "base")

        # An honest base state: nothing left but the version table.
        with psycopg.connect(_admin_dsn(_cycle_url(admin_url))) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'health_compass'"
                )
            }
            assert tables <= {"alembic_version"}, tables
            functions = [
                row[0]
                for row in conn.execute(
                    "SELECT p.proname FROM pg_proc p "
                    "JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE n.nspname = 'health_compass'"
                )
            ]
            assert functions == [], functions

        upgrade(config, "head")

        engine = create_engine(_migrator_cycle_url())
        try:
            with engine.connect() as conn:
                revision = conn.execute(
                    text("SELECT version_num FROM health_compass.alembic_version")
                ).scalar_one()
                assert revision == expected_head

                for signature in DEFINER_FUNCTIONS:
                    owner = conn.execute(
                        text(
                            "SELECT r.rolname FROM pg_proc p "
                            "JOIN pg_roles r ON r.oid = p.proowner "
                            "WHERE p.oid = :sig ::regprocedure"
                        ),
                        {"sig": f"health_compass.{signature}"},
                    ).scalar_one()
                    assert owner == "health_compass_rls_definer", (signature, owner)

                    public_execute = conn.execute(
                        text(
                            "SELECT has_function_privilege('public', "
                            ":sig ::regprocedure, 'EXECUTE')"
                        ),
                        {"sig": f"health_compass.{signature}"},
                    ).scalar_one()
                    assert public_execute is False, signature

                rls_rows = conn.execute(
                    text(
                        "SELECT relname, relrowsecurity, relforcerowsecurity "
                        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = 'health_compass' AND relname = ANY(:tables)"
                    ),
                    {"tables": list(FORCE_RLS_TABLES)},
                ).all()
                assert len(rls_rows) == len(FORCE_RLS_TABLES)
                for row in rls_rows:
                    assert row.relrowsecurity and row.relforcerowsecurity, row.relname

                for table in CANONICAL_TABLES:
                    direct_update = conn.execute(
                        text(
                            "SELECT count(*) FROM information_schema.column_privileges "
                            "WHERE grantee = 'health_compass_app' "
                            "AND table_schema = 'health_compass' "
                            "AND table_name = :table "
                            "AND column_name = 'canonical_concept_id' "
                            "AND privilege_type = 'UPDATE'"
                        ),
                        {"table": table},
                    ).scalar_one()
                    assert direct_update == 0, table

                document_mutation_grants = conn.execute(
                    text(
                        "SELECT table_name, privilege_type "
                        "FROM information_schema.role_table_grants "
                        "WHERE grantee = 'health_compass_app' "
                        "AND table_schema = 'health_compass' "
                        "AND table_name = ANY(:tables) "
                        "AND privilege_type IN ('UPDATE', 'DELETE')"
                    ),
                    {"tables": list(DOCUMENT_TABLES)},
                ).all()
                assert document_mutation_grants == []

                users_update_columns = {
                    row[0]
                    for row in conn.execute(
                        text(
                            "SELECT column_name FROM information_schema.column_privileges "
                            "WHERE grantee = 'health_compass_app' "
                            "AND table_schema = 'health_compass' "
                            "AND table_name = 'users' AND privilege_type = 'UPDATE'"
                        )
                    )
                }
                assert users_update_columns == {"display_name", "updated_at"}

                definer_grants = conn.execute(
                    text(
                        "SELECT count(*) FROM information_schema.role_table_grants "
                        "WHERE grantee = 'health_compass_rls_definer' "
                        "AND table_schema = 'health_compass' "
                        "AND table_name IN ("
                        "'profile_clinical_reviews', 'profile_intake_decisions', "
                        "'profile_documents') "
                        "AND privilege_type = 'SELECT'"
                    )
                ).scalar_one()
                assert definer_grants == 3
        finally:
            engine.dispose()
    finally:
        _drop_cycle_database(admin_url)
