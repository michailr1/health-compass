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
    op.execute(f"DROP POLICY IF EXISTS sessions_current_select ON {S}.auth_sessions")
    op.execute(f"DROP POLICY IF EXISTS sessions_current_update ON {S}.auth_sessions")
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

    op.execute(
        f"""
        CREATE POLICY sessions_current_select
        ON {S}.auth_sessions
        FOR SELECT
        USING (session_token_hash = {S}.app_current_session_hash())
        """
    )
    op.execute(
        f"""
        CREATE POLICY sessions_current_update
        ON {S}.auth_sessions
        FOR UPDATE
        USING (session_token_hash = {S}.app_current_session_hash())
        WITH CHECK (session_token_hash = {S}.app_current_session_hash())
        """
    )
