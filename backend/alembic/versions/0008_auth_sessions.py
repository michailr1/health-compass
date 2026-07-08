"""Create auth session table.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "health_compass"


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token_hash", sa.String(128), nullable=False),
        sa.Column("csrf_token_hash", sa.String(128), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("session_token_hash", name="uq_auth_sessions_token_hash"),
        schema=SCHEMA,
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], schema=SCHEMA)
    op.execute(f"ALTER TABLE {SCHEMA}.auth_sessions ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY auth_sessions_self_select ON {SCHEMA}.auth_sessions FOR SELECT USING (user_id = {SCHEMA}.app_current_user_id())")
    op.execute(f"CREATE POLICY auth_sessions_self_update ON {SCHEMA}.auth_sessions FOR UPDATE USING (user_id = {SCHEMA}.app_current_user_id())")


def downgrade() -> None:
    op.drop_table("auth_sessions", schema=SCHEMA)
