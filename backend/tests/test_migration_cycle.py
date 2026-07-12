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

SCANNER_FUNCTIONS = (
    "app_claim_document_job(text, integer, integer)",
    "app_heartbeat_document_job(uuid, text, timestamp with time zone, integer)",
    (
        "app_complete_document_scan(uuid, text, timestamp with time zone, text, text, "
        "text, timestamp with time zone, text, uuid, text, uuid)"
    ),
    (
        "app_fail_document_job(uuid, text, timestamp with time zone, text, boolean, "
        "integer, integer)"
    ),
)

RENDERER_FUNCTIONS = (
    "app_claim_render_job(text, integer, integer)",
    "app_heartbeat_render_job(uuid, text, timestamp with time zone, integer)",
    (
        "app_complete_document_render(uuid, text, timestamp with time zone, uuid, text, "
        "bigint, text, text, integer, text, text, jsonb, uuid)"
    ),
    (
        "app_fail_render_job(uuid, text, timestamp with time zone, text, boolean, "
        "integer, integer)"
    ),
)

RECONCILER_FUNCTIONS = (
    "app_list_document_storage_references()",
    "app_mark_document_object_missing(text, text, uuid)",
)

APP_DOCUMENT_FUNCTIONS = (
    "app_reserve_document_upload(uuid, bigint, bigint, bigint, integer, integer)",
)

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
    *SCANNER_FUNCTIONS,
    *RENDERER_FUNCTIONS,
    *RECONCILER_FUNCTIONS,
    *APP_DOCUMENT_FUNCTIONS,
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
    "document_artifacts",
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
    "document_artifacts",
)

WORKER_ROLES = (
    "health_compass_worker",
    "health_compass_renderer",
    "health_compass_reconciler",
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
        for role in WORKER_ROLES:
            conn.execute(f"GRANT CONNECT ON DATABASE {CYCLE_DB} TO {role}")
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


def _has_execute(conn, role: str, signature: str) -> bool:
    return conn.execute(
        text(
            "SELECT has_function_privilege(:role, :sig ::regprocedure, 'EXECUTE')"
        ),
        {"role": role, "sig": f"health_compass.{signature}"},
    ).scalar_one()


def test_full_migration_cycle_restores_all_security_invariants() -> None:
    admin_url = _admin_url()
    parsed_admin = urlsplit(
        admin_url.replace("postgresql+psycopg://", "postgresql://", 1)
    )
    if not parsed_admin.path.endswith("_test"):
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
                    assert _has_execute(conn, "public", signature) is False, signature

                for signature in SCANNER_FUNCTIONS:
                    assert _has_execute(conn, "health_compass_worker", signature) is True
                    assert _has_execute(conn, "health_compass_app", signature) is False
                    assert _has_execute(conn, "health_compass_renderer", signature) is False
                    assert _has_execute(conn, "health_compass_reconciler", signature) is False

                for signature in RENDERER_FUNCTIONS:
                    assert _has_execute(conn, "health_compass_renderer", signature) is True
                    assert _has_execute(conn, "health_compass_app", signature) is False
                    assert _has_execute(conn, "health_compass_worker", signature) is False
                    assert _has_execute(conn, "health_compass_reconciler", signature) is False

                for signature in RECONCILER_FUNCTIONS:
                    assert _has_execute(conn, "health_compass_reconciler", signature) is True
                    assert _has_execute(conn, "health_compass_app", signature) is False
                    assert _has_execute(conn, "health_compass_worker", signature) is False
                    assert _has_execute(conn, "health_compass_renderer", signature) is False

                for signature in APP_DOCUMENT_FUNCTIONS:
                    assert _has_execute(conn, "health_compass_app", signature) is True
                    for role in WORKER_ROLES:
                        assert _has_execute(conn, role, signature) is False

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

                artifact_mutation_grants = conn.execute(
                    text(
                        "SELECT privilege_type "
                        "FROM information_schema.role_table_grants "
                        "WHERE grantee = 'health_compass_app' "
                        "AND table_schema = 'health_compass' "
                        "AND table_name = 'document_artifacts' "
                        "AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE')"
                    )
                ).all()
                assert artifact_mutation_grants == []

                for role in WORKER_ROLES:
                    worker_table_grants = conn.execute(
                        text(
                            "SELECT table_name, privilege_type "
                            "FROM information_schema.role_table_grants "
                            "WHERE grantee = :role "
                            "AND table_schema = 'health_compass' "
                            "AND table_name = ANY(:tables)"
                        ),
                        {"role": role, "tables": list(DOCUMENT_TABLES)},
                    ).all()
                    assert worker_table_grants == [], role

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
