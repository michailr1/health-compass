"""Allow first-profile bootstrap through application role.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-06
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "health_compass"
WM = "workspace_" + "members"
PP = "profile_" + "permissions"
DS = "dashboard_" + "snapshots"


def upgrade() -> None:
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.auth_sessions TO health_compass_app")
    op.execute(f"CREATE POLICY workspaces_insert_self ON {S}.workspaces FOR INSERT WITH CHECK (created_by_user_id = {S}.app_current_user_id())")
    op.execute(f"CREATE POLICY workspace_members_insert_self ON {S}.{WM} FOR INSERT WITH CHECK (user_id = {S}.app_current_user_id())")
    op.execute(f"CREATE POLICY profiles_insert_self ON {S}.health_profiles FOR INSERT WITH CHECK (owner_user_id = {S}.app_current_user_id())")
    op.execute(f"CREATE POLICY profile_access_insert_self ON {S}.{PP} FOR INSERT WITH CHECK (user_id = {S}.app_current_user_id())")
    op.execute(f"CREATE POLICY dashboard_insert_visible ON {S}.{DS} FOR INSERT WITH CHECK ({S}.app_can_view_profile(profile_id))")


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS dashboard_insert_visible ON {S}.{DS}")
    op.execute(f"DROP POLICY IF EXISTS profile_access_insert_self ON {S}.{PP}")
    op.execute(f"DROP POLICY IF EXISTS profiles_insert_self ON {S}.health_profiles")
    op.execute(f"DROP POLICY IF EXISTS workspace_members_insert_self ON {S}.{WM}")
    op.execute(f"DROP POLICY IF EXISTS workspaces_insert_self ON {S}.workspaces")
