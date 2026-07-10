"""Allow users to list and update only their own auth sessions.

Revision ID: 0046
Revises: 0045
"""

from __future__ import annotations

from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None

S = "health_compass"


def upgrade() -> None:
    # Keep sessions_current_* policies: they are required to authenticate a
    # cookie before app.current_user_id is known. The new owner policies become
    # effective after get_current_user installs the user context.
    op.execute(f"DROP POLICY IF EXISTS auth_sessions_self_select ON {S}.auth_sessions")
    op.execute(f"DROP POLICY IF EXISTS auth_sessions_self_update ON {S}.auth_sessions")

    op.execute(
        f"""
        CREATE POLICY auth_sessions_self_select
        ON {S}.auth_sessions
        FOR SELECT
        USING (user_id = {S}.app_current_user_id())
        """
    )
    op.execute(
        f"""
        CREATE POLICY auth_sessions_self_update
        ON {S}.auth_sessions
        FOR UPDATE
        USING (user_id = {S}.app_current_user_id())
        WITH CHECK (user_id = {S}.app_current_user_id())
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS auth_sessions_self_update ON {S}.auth_sessions")
    op.execute(f"DROP POLICY IF EXISTS auth_sessions_self_select ON {S}.auth_sessions")
