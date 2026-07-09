"""Fix ownership and execution context of RLS context helpers.

Revision ID: 0021
Revises: 0020
"""

from __future__ import annotations

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_roles
            WHERE rolname = '{R}'
              AND rolbypassrls
              AND NOT rolcanlogin
          ) THEN
            RAISE EXCEPTION
              'Provision first: CREATE ROLE {R} NOLOGIN BYPASSRLS; '
              'GRANT {R} TO health_compass_migrator';
          END IF;
        END $$;
        """
    )

    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_current_user_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
          SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
        $$
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_current_session_hash()
        RETURNS text
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
          SELECT NULLIF(current_setting('app.current_session_hash', true), '')
        $$
        """
    )

    for signature in [
        f"{S}.app_current_user_id()",
        f"{S}.app_current_session_hash()",
    ]:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {R}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO health_compass_app")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    for signature in [
        f"{S}.app_current_user_id()",
        f"{S}.app_current_session_hash()",
    ]:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO health_compass_migrator")
        op.execute(f"ALTER FUNCTION {signature} SECURITY INVOKER")
        op.execute(f"ALTER FUNCTION {signature} RESET row_security")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO health_compass_app")
