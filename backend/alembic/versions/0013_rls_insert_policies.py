"""Allow bootstrap inserts under RLS.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "health_compass"
WM = "workspace_" + "members"
PP = "profile_" + "permissions"
DS = "dashboard_" + "snapshots"


def upgrade() -> None:
    op.execute(f"""
    CREATE POLICY workspaces_owner_insert ON {S}.workspaces
    FOR INSERT WITH CHECK (created_by_user_id = {S}.app_current_user_id())
    """)
    op.execute(f"""
    CREATE POLICY workspace_owner_member_insert ON {S}.{WM}
    FOR INSERT WITH CHECK (user_id = {S}.app_current_user_id())
    """)
    op.execute(f"""
    CREATE POLICY profiles_owner_insert ON {S}.health_profiles
    FOR INSERT WITH CHECK (owner_user_id = {S}.app_current_user_id())
    """)
    op.execute(f"""
    CREATE POLICY profile_owner_access_insert ON {S}.{PP}
    FOR INSERT WITH CHECK (user_id = {S}.app_current_user_id() AND permission = 'owner')
    """)
    op.execute(f"""
    CREATE POLICY dashboard_owner_insert ON {S}.{DS}
    FOR INSERT WITH CHECK ({S}.app_can_view_profile(profile_id))
    """)


def downgrade() -> None:
    for policy, table in [
        ("dashboard_owner_insert", DS),
        ("profile_owner_access_insert", PP),
        ("profiles_owner_insert", "health_profiles"),
        ("workspace_owner_member_insert", WM),
        ("workspaces_owner_insert", "workspaces"),
    ]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {S}.{table}")
