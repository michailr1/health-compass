"""Allow OIDC provisioning and server session lookup under RLS.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-06
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "health_compass"


def upgrade() -> None:
    op.execute(f"CREATE POLICY users_oidc_insert ON {S}.users FOR INSERT WITH CHECK (true)")
    op.execute(f"CREATE POLICY identities_oidc_insert ON {S}.user_identities FOR INSERT WITH CHECK (true)")
    op.execute(f"CREATE POLICY identities_oidc_update ON {S}.user_identities FOR UPDATE USING (true) WITH CHECK (true)")
    op.execute(f"CREATE POLICY sessions_insert ON {S}.auth_sessions FOR INSERT WITH CHECK (true)")
    op.execute(f"DROP POLICY IF EXISTS auth_sessions_self_select ON {S}.auth_sessions")
    op.execute(f"DROP POLICY IF EXISTS auth_sessions_self_update ON {S}.auth_sessions")
    op.execute(f"CREATE POLICY sessions_token_select ON {S}.auth_sessions FOR SELECT USING (true)")
    op.execute(f"CREATE POLICY sessions_token_update ON {S}.auth_sessions FOR UPDATE USING (true) WITH CHECK (true)")


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS sessions_token_update ON {S}.auth_sessions")
    op.execute(f"DROP POLICY IF EXISTS sessions_token_select ON {S}.auth_sessions")
    op.execute(f"DROP POLICY IF EXISTS sessions_insert ON {S}.auth_sessions")
    op.execute(f"DROP POLICY IF EXISTS identities_oidc_update ON {S}.user_identities")
    op.execute(f"DROP POLICY IF EXISTS identities_oidc_insert ON {S}.user_identities")
    op.execute(f"DROP POLICY IF EXISTS users_oidc_insert ON {S}.users")
