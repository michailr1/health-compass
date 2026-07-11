"""Enable RLS for identity tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-06
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "health_compass"
WM = "workspace_" + "members"
PP = "profile_" + "permissions"
DS = "dashboard_" + "snapshots"


def upgrade() -> None:
    op.execute(f"""
    CREATE OR REPLACE FUNCTION {S}.app_current_user_id()
    RETURNS uuid LANGUAGE sql STABLE AS $$
      SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
    $$
    """)
    op.execute(f"""
    CREATE OR REPLACE FUNCTION {S}.app_can_view_profile(target_profile_id uuid)
    RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = {S}, pg_temp AS $$
      SELECT EXISTS (
        SELECT 1 FROM {S}.health_profiles hp
        WHERE hp.id = target_profile_id AND hp.owner_user_id = {S}.app_current_user_id()
      ) OR EXISTS (
        SELECT 1 FROM {S}.{PP} pp
        WHERE pp.profile_id = target_profile_id
          AND pp.user_id = {S}.app_current_user_id()
          AND pp.permission IN ('owner', 'edit', 'analyze', 'view')
      )
    $$
    """)
    op.execute(f"""
    CREATE OR REPLACE FUNCTION {S}.app_has_workspace_access(target_workspace_id uuid)
    RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = {S}, pg_temp AS $$
      SELECT EXISTS (
        SELECT 1 FROM {S}.{WM} wm
        WHERE wm.workspace_id = target_workspace_id
          AND wm.user_id = {S}.app_current_user_id()
      )
    $$
    """)

    for table in ["users", "user_identities", "workspaces", WM, "health_profiles", PP, "invitations", DS]:
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")

    op.execute(f"CREATE POLICY users_self_select ON {S}.users FOR SELECT USING (id = {S}.app_current_user_id())")
    op.execute(f"CREATE POLICY identities_self_select ON {S}.user_identities FOR SELECT USING (user_id = {S}.app_current_user_id())")
    op.execute(f"CREATE POLICY workspaces_access_select ON {S}.workspaces FOR SELECT USING ({S}.app_has_workspace_access(id))")
    op.execute(f"CREATE POLICY workspace_access_select ON {S}.{WM} FOR SELECT USING ({S}.app_has_workspace_access(workspace_id))")
    op.execute(f"CREATE POLICY profiles_view_select ON {S}.health_profiles FOR SELECT USING ({S}.app_can_view_profile(id))")
    op.execute(f"CREATE POLICY profile_access_select ON {S}.{PP} FOR SELECT USING ({S}.app_can_view_profile(profile_id))")
    op.execute(f"CREATE POLICY dashboard_view_select ON {S}.{DS} FOR SELECT USING ({S}.app_can_view_profile(profile_id))")


def downgrade() -> None:
    # Drop the policies created by this revision before their functions;
    # otherwise the function drops fail on dependent objects (HC-015 Slice E).
    op.execute(f"DROP POLICY IF EXISTS dashboard_view_select ON {S}.{DS}")
    op.execute(f"DROP POLICY IF EXISTS profile_access_select ON {S}.{PP}")
    op.execute(f"DROP POLICY IF EXISTS profiles_view_select ON {S}.health_profiles")
    op.execute(f"DROP POLICY IF EXISTS workspace_access_select ON {S}.{WM}")
    op.execute(f"DROP POLICY IF EXISTS workspaces_access_select ON {S}.workspaces")
    op.execute(f"DROP POLICY IF EXISTS identities_self_select ON {S}.user_identities")
    op.execute(f"DROP POLICY IF EXISTS users_self_select ON {S}.users")
    for table in [DS, "invitations", PP, "health_profiles", WM, "workspaces", "user_identities", "users"]:
        op.execute(f"ALTER TABLE {S}.{table} DISABLE ROW LEVEL SECURITY")
    op.execute(f"DROP FUNCTION IF EXISTS {S}.app_has_workspace_access(uuid)")
    op.execute(f"DROP FUNCTION IF EXISTS {S}.app_can_view_profile(uuid)")
    op.execute(f"DROP FUNCTION IF EXISTS {S}.app_current_user_id()")
