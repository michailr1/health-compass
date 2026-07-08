"""Allow identity lookup before user context is known.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-06
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA_NAME = "health_compass"


def upgrade() -> None:
    op.execute(
        "CREATE POLICY identity_lookup_policy ON "
        f"{SCHEMA_NAME}.user_identities FOR SELECT USING (true)"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS identity_lookup_policy ON "
        f"{SCHEMA_NAME}.user_identities"
    )
