"""Force RLS and remove duplicate insert policies.

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "health_compass"
TABLES = [
    "users",
    "user_identities",
    "auth_sessions",
    "workspaces",
    "workspace_members",
    "health_profiles",
    "profile_permissions",
    "invitations",
    "dashboard_snapshots",
]
DUPLICATE_POLICIES = [
    ("workspaces_insert_self", "workspaces"),
    ("workspace_members_insert_self", "workspace_members"),
    ("profiles_insert_self", "health_profiles"),
    ("profile_access_insert_self", "profile_permissions"),
    ("dashboard_insert_visible", "dashboard_snapshots"),
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")
    for policy, table in DUPLICATE_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {S}.{table}")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {S}.{table} NO FORCE ROW LEVEL SECURITY")
