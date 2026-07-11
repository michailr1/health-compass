"""Narrow the runtime UPDATE grant on users to non-identity columns.

HC-015 Slice C hardening (CR-19/FBL-06): revision 0007 granted the runtime
role table-wide UPDATE on ``health_compass.users`` and the self-update RLS
policy does not restrict columns, so a compromised session could rewrite its
own ``email`` or ``status``. The application only ever updates
``display_name`` (plus the ORM-managed ``updated_at``), so the grant is
narrowed to exactly those columns.

Revision ID: 0048
Revises: 0047
"""

from __future__ import annotations

from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(f"REVOKE UPDATE ON {S}.users FROM {APP}")
    op.execute(f"GRANT UPDATE (display_name, updated_at) ON {S}.users TO {APP}")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ON {S}.users FROM {APP}")
    op.execute(f"GRANT UPDATE ON {S}.users TO {APP}")
