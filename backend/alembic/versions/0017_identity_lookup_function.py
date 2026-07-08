"""Add narrow identity lookup function.

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "health_compass"


def upgrade() -> None:
    op.execute(f"""
    CREATE OR REPLACE FUNCTION {S}.app_lookup_identity_user_id(identity_provider text, identity_subject text)
    RETURNS uuid
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = {S}, pg_temp
    AS $$
      SELECT ui.user_id
      FROM {S}.user_identities ui
      WHERE ui.provider = identity_provider
        AND ui.subject = identity_subject
      LIMIT 1
    $$
    """)
    op.execute(f"GRANT EXECUTE ON FUNCTION {S}.app_lookup_identity_user_id(text, text) TO health_compass_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {S}.app_lookup_identity_user_id(text, text)")
