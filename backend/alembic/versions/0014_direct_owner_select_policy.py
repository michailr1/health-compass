"""Allow owner rows to be visible during INSERT RETURNING.

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "health_compass"


def upgrade() -> None:
    op.execute(f"""
    CREATE POLICY profiles_owner_direct_select ON {S}.health_profiles
    FOR SELECT USING (owner_user_id = {S}.app_current_user_id())
    """)


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS profiles_owner_direct_select ON {S}.health_profiles")
