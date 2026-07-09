"""Break RLS recursion and close tenant escalation paths.

Revision ID: 0020
Revises: 0019
"""

from __future__ import annotations

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"

FUNCTIONS = [
    f"{S}.app_can_view_profile(uuid)",
    f"{S}.app_has_workspace_access(uuid)",
    f"{S}.app_owns_profile(uuid)",
    f"{S}.app_created_workspace(uuid)",
    f"{S}.app_lookup_identity_user_id(text, text)",
    f"{S}.app_issue_email_login_token(text, text, timestamptz, text, text)",
    f"{S}.app_consume_email_login_token(text)",
]


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_roles
            WHERE rolname = '{R}' AND rolbypassrls AND NOT rolcanlogin
          ) THEN
            RAISE EXCEPTION
              'Provision first: CREATE ROLE {R} NOLOGIN BYPASSRLS; '
              'GRANT {R} TO health_compass_migrator';
          END IF;
        END $$;
        """
    )

    op.execute(f"GRANT USAGE ON SCHEMA {S} TO {R}")
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")
    op.execute(
        f"""
        GRANT SELECT ON
          {S}.health_profiles,
          {S}.profile_permissions,
          {S}.workspaces,
          {S}.workspace_members,
          {S}.user_identities
        TO {R}
        """
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.email_login_tokens TO {R}")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_current_user_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        SET search_path = ''
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
        SET search_path = ''
        AS $$
          SELECT NULLIF(current_setting('app.current_session_hash', true), '')
        $$
        """
    )

    # PostgreSQL validates SQL function bodies as the creating role. On a clean
    # database the migrator owns FORCE-RLS tables but deliberately has no
    # BYPASSRLS, so setting row_security=off inside CREATE FUNCTION is rejected
    # before ownership can be transferred. Create first, transfer ownership to
    # the dedicated BYPASSRLS NOLOGIN role, and only then set row_security=off.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_can_view_profile(target_profile_id uuid)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM {S}.health_profiles hp
            WHERE hp.id = target_profile_id
              AND hp.owner_user_id = {S}.app_current_user_id()
          ) OR EXISTS (
            SELECT 1 FROM {S}.profile_permissions pp
            WHERE pp.profile_id = target_profile_id
              AND pp.user_id = {S}.app_current_user_id()
              AND pp.permission IN ('owner', 'edit', 'analyze', 'view')
          )
        $$
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_has_workspace_access(target_workspace_id uuid)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM {S}.workspace_members wm
            WHERE wm.workspace_id = target_workspace_id
              AND wm.user_id = {S}.app_current_user_id()
          )
        $$
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_owns_profile(target_profile_id uuid)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM {S}.health_profiles hp
            WHERE hp.id = target_profile_id
              AND hp.owner_user_id = {S}.app_current_user_id()
          )
        $$
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_created_workspace(target_workspace_id uuid)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM {S}.workspaces w
            WHERE w.id = target_workspace_id
              AND w.created_by_user_id = {S}.app_current_user_id()
          )
        $$
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_lookup_identity_user_id(
          identity_provider text,
          identity_subject text
        ) RETURNS uuid
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        AS $$
          SELECT ui.user_id
          FROM {S}.user_identities ui
          WHERE ui.provider = identity_provider
            AND ui.subject = identity_subject
          LIMIT 1
        $$
        """
    )

    for signature in FUNCTIONS:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {R}")
        op.execute(f"ALTER FUNCTION {signature} SET row_security = off")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO health_compass_app")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")

    for signature in [
        f"{S}.app_current_user_id()",
        f"{S}.app_current_session_hash()",
    ]:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO health_compass_app")

    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {S} "
        "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
    )

    op.execute(f"ALTER TABLE {S}.email_login_tokens FORCE ROW LEVEL SECURITY")

    op.execute(
        f"DROP POLICY IF EXISTS profile_owner_access_insert "
        f"ON {S}.profile_permissions"
    )
    op.execute(
        f"""
        CREATE POLICY pp_owner_bootstrap_insert
        ON {S}.profile_permissions
        FOR INSERT
        WITH CHECK (
          user_id = {S}.app_current_user_id()
          AND permission = 'owner'
          AND {S}.app_owns_profile(profile_id)
        )
        """
    )

    op.execute(
        f"DROP POLICY IF EXISTS workspace_owner_member_insert "
        f"ON {S}.workspace_members"
    )
    op.execute(
        f"""
        CREATE POLICY wm_creator_bootstrap_insert
        ON {S}.workspace_members
        FOR INSERT
        WITH CHECK (
          user_id = {S}.app_current_user_id()
          AND role = 'owner'
          AND {S}.app_created_workspace(workspace_id)
        )
        """
    )

    op.execute(f"DROP POLICY IF EXISTS profiles_owner_insert ON {S}.health_profiles")
    op.execute(
        f"""
        CREATE POLICY profiles_owner_insert
        ON {S}.health_profiles
        FOR INSERT
        WITH CHECK (
          owner_user_id = {S}.app_current_user_id()
          AND {S}.app_has_workspace_access(workspace_id)
        )
        """
    )

    op.execute(
        f"""
        CREATE POLICY pp_self_select
        ON {S}.profile_permissions
        FOR SELECT
        USING (user_id = {S}.app_current_user_id())
        """
    )
    op.execute(
        f"""
        CREATE POLICY wm_self_select
        ON {S}.workspace_members
        FOR SELECT
        USING (user_id = {S}.app_current_user_id())
        """
    )
    op.execute(
        f"""
        CREATE POLICY users_self_update
        ON {S}.users
        FOR UPDATE
        USING (id = {S}.app_current_user_id())
        WITH CHECK (id = {S}.app_current_user_id())
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS users_self_update ON {S}.users")
    op.execute(f"DROP POLICY IF EXISTS wm_self_select ON {S}.workspace_members")
    op.execute(f"DROP POLICY IF EXISTS pp_self_select ON {S}.profile_permissions")
    op.execute(f"DROP POLICY IF EXISTS profiles_owner_insert ON {S}.health_profiles")
    op.execute(
        f"DROP POLICY IF EXISTS wm_creator_bootstrap_insert ON {S}.workspace_members"
    )
    op.execute(
        f"DROP POLICY IF EXISTS pp_owner_bootstrap_insert ON {S}.profile_permissions"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {S}.app_created_workspace(uuid)")
    op.execute(f"DROP FUNCTION IF EXISTS {S}.app_owns_profile(uuid)")
