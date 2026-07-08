"""Restore strict RLS for users after OIDC bootstrap fix.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "health_compass"


def upgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS users_oidc_insert ON {S}.users")
    op.execute(f"DROP POLICY IF EXISTS users_insert_self ON {S}.users")
    op.execute(
        f"CREATE POLICY users_insert_self ON {S}.users "
        f"FOR INSERT WITH CHECK (id = {S}.app_current_user_id())"
    )
    op.execute(f"ALTER TABLE {S}.users ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS users_insert_self ON {S}.users")
    op.execute(f"CREATE POLICY users_oidc_insert ON {S}.users FOR INSERT WITH CHECK (true)")
