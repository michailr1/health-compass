"""Preserve duplicate resolution intents when the initiating user is absorbed.

Revision ID: 0032
Revises: 0031
"""

from __future__ import annotations

from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None

S = "health_compass"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {S}.duplicate_resolution_intents "
        "DROP CONSTRAINT duplicate_resolution_intents_initiating_user_id_fkey"
    )
    op.execute(
        f"ALTER TABLE {S}.duplicate_resolution_intents "
        "ALTER COLUMN initiating_user_id DROP NOT NULL"
    )
    op.execute(
        f"ALTER TABLE {S}.duplicate_resolution_intents "
        f"ADD CONSTRAINT duplicate_resolution_intents_initiating_user_id_fkey "
        f"FOREIGN KEY (initiating_user_id) REFERENCES {S}.users(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {S}.duplicate_resolution_intents "
        "DROP CONSTRAINT duplicate_resolution_intents_initiating_user_id_fkey"
    )
    op.execute(
        f"DELETE FROM {S}.duplicate_resolution_intents WHERE initiating_user_id IS NULL"
    )
    op.execute(
        f"ALTER TABLE {S}.duplicate_resolution_intents "
        "ALTER COLUMN initiating_user_id SET NOT NULL"
    )
    op.execute(
        f"ALTER TABLE {S}.duplicate_resolution_intents "
        f"ADD CONSTRAINT duplicate_resolution_intents_initiating_user_id_fkey "
        f"FOREIGN KEY (initiating_user_id) REFERENCES {S}.users(id) ON DELETE CASCADE"
    )
