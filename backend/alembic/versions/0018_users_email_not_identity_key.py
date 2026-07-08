"""Stop treating users.email as a global identity key.

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "health_compass"


def upgrade() -> None:
    # Authentication identities are unique by (provider, subject). Email is a
    # mutable profile/contact attribute and must not merge or reject distinct
    # provider identities.
    op.drop_constraint("uq_users_email", "users", schema=SCHEMA, type_="unique")
    op.create_index("ix_users_email", "users", ["email"], unique=False, schema=SCHEMA)


def downgrade() -> None:
    # Downgrade can fail if distinct users acquired the same email after this
    # migration. That is intentional: silently merging identities is unsafe.
    op.drop_index("ix_users_email", table_name="users", schema=SCHEMA)
    op.create_unique_constraint("uq_users_email", "users", ["email"], schema=SCHEMA)
