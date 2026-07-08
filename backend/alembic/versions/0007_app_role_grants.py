"""Grant application role access to identity tables.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-06
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "health_compass"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'health_compass_app') THEN
            GRANT USAGE ON SCHEMA {SCHEMA} TO health_compass_app;
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {SCHEMA} TO health_compass_app;
            GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {SCHEMA} TO health_compass_app;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    pass
