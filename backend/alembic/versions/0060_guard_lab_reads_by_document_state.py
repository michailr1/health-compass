"""Guard Lab observation reads by the source document lifecycle.

Revision ID: 0060
Revises: 0059

A document can enter deletion_pending through more than one application path.
The Lab RLS boundary must therefore verify document availability independently
of the caller's direct permission to read the source document.
"""

from __future__ import annotations

from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"
SIGNATURE = f"{S}.app_lab_document_available(uuid,uuid)"


def _drop_e3_policies() -> None:
    op.execute(
        f"DROP POLICY IF EXISTS lab_observation_sources_select_edit "
        f"ON {S}.lab_observation_sources"
    )
    op.execute(
        f"DROP POLICY IF EXISTS lab_observations_select_lifecycle_edit "
        f"ON {S}.lab_observations"
    )
    op.execute(
        f"DROP POLICY IF EXISTS lab_observations_select_active "
        f"ON {S}.lab_observations"
    )


def _create_0059_policies() -> None:
    op.execute(
        f"""
        CREATE POLICY lab_observations_select_active
        ON {S}.lab_observations FOR SELECT
        USING (
          status = 'active'
          AND {S}.app_can_view_profile(profile_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY lab_observations_select_lifecycle_edit
        ON {S}.lab_observations FOR SELECT
        USING ({S}.app_can_edit_profile(profile_id))
        """
    )
    op.execute(
        f"""
        CREATE POLICY lab_observation_sources_select_edit
        ON {S}.lab_observation_sources FOR SELECT
        USING ({S}.app_can_edit_profile(profile_id))
        """
    )


def upgrade() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_lab_document_available(
          p_document_id uuid,
          p_profile_id uuid
        )
        RETURNS boolean
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        BEGIN
          IF SESSION_USER <> '{APP}'
             OR NOT {S}.app_can_view_profile(p_profile_id) THEN
            RETURN false;
          END IF;
          RETURN EXISTS (
            SELECT 1
            FROM {S}.profile_documents d
            WHERE d.id = p_document_id
              AND d.profile_id = p_profile_id
              AND d.deletion_requested_at IS NULL
              AND d.erased_at IS NULL
          );
        END;
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {SIGNATURE} OWNER TO {DEFINER}")
    op.execute(f"ALTER FUNCTION {SIGNATURE} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")

    _drop_e3_policies()
    op.execute(
        f"""
        CREATE POLICY lab_observations_select_active
        ON {S}.lab_observations FOR SELECT
        USING (
          status = 'active'
          AND {S}.app_can_view_profile(profile_id)
          AND {S}.app_lab_document_available(document_id, profile_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY lab_observations_select_lifecycle_edit
        ON {S}.lab_observations FOR SELECT
        USING (
          {S}.app_can_edit_profile(profile_id)
          AND {S}.app_lab_document_available(document_id, profile_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY lab_observation_sources_select_edit
        ON {S}.lab_observation_sources FOR SELECT
        USING (
          {S}.app_can_edit_profile(profile_id)
          AND {S}.app_lab_document_available(document_id, profile_id)
        )
        """
    )


def downgrade() -> None:
    _drop_e3_policies()
    _create_0059_policies()
    op.execute(f"REVOKE EXECUTE ON FUNCTION {SIGNATURE} FROM {APP}")
    op.execute(f"DROP FUNCTION IF EXISTS {SIGNATURE}")
