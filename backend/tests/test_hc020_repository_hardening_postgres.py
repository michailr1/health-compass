"""PostgreSQL regression coverage for HC-020 repository hardening."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

LEGACY_TABLES = {"audit_events", "processing_jobs", "service_metadata"}
MAGIC_LINK_SIGNATURES = (
    "health_compass.app_issue_email_login_token(text,text,timestamp with time zone,text,text)",
    "health_compass.app_consume_email_login_token(text)",
)


def _search_path_value(config: list[str] | None) -> str | None:
    for entry in config or []:
        if entry.startswith("search_path="):
            return entry.split("=", 1)[1].strip('"')
    return None


@pytest.mark.anyio
async def test_legacy_technical_tables_are_not_exposed(
    test_session: AsyncSession,
) -> None:
    """Defect-first: the old head exposed all three tables to the app role."""
    rows = await test_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'health_compass' "
            "AND table_name = ANY(:tables)"
        ),
        {"tables": sorted(LEGACY_TABLES)},
    )
    assert set(rows.scalars()) == set()

    grants = await test_session.execute(
        text(
            "SELECT table_name, privilege_type "
            "FROM information_schema.role_table_grants "
            "WHERE grantee = 'health_compass_app' "
            "AND table_schema = 'health_compass' "
            "AND table_name = ANY(:tables)"
        ),
        {"tables": sorted(LEGACY_TABLES)},
    )
    assert grants.all() == []


@pytest.mark.anyio
async def test_magic_link_definers_use_empty_search_path(
    test_session: AsyncSession,
) -> None:
    """Defect-first: both bootstrap-era functions used health_compass,pg_temp."""
    for signature in MAGIC_LINK_SIGNATURES:
        row = (
            await test_session.execute(
                text(
                    "SELECT p.proconfig, owner.rolname AS owner, "
                    "has_function_privilege('health_compass_app', p.oid, 'EXECUTE') AS app_execute, "
                    "has_function_privilege('public', p.oid, 'EXECUTE') AS public_execute "
                    "FROM pg_proc p "
                    "JOIN pg_roles owner ON owner.oid = p.proowner "
                    "WHERE p.oid = CAST(:signature AS regprocedure)"
                ),
                {"signature": signature},
            )
        ).one()

        assert _search_path_value(row.proconfig) == ""
        assert row.owner == "health_compass_rls_definer"
        assert row.app_execute is True
        assert row.public_execute is False
