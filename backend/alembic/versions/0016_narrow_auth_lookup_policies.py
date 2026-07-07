"""Narrow auth lookup RLS policies.

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "health_compass"


def upgrade() -> None:
    # Remove broad policies that opened identities and sessions to every app-role query.
    for policy, table in [
        ("identity_lookup_policy", "user_identities"),
        ("identities_oidc_insert", "user_identities"),
        ("identities_oidc_update", "user_identities"),
        ("sessions_token_select", "auth_sessions"),
        ("sessions_token_update", "auth_sessions"),
        ("sessions_insert", "auth_sessions"),
    ]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {S}.{table}")

    op.execute(f"""
    CREATE OR REPLACE FUNCTION {S}.app_current_session_hash()
    RETURNS text
    LANGUAGE sql
    STABLE
    SET search_path = {S}, pg_temp
    AS $$
      SELECT NULLIF(current_setting('app.current_session_hash', true), '')
    $$
    """)

    op.execute(f"""
    CREATE POLICY identities_self_insert ON {S}.user_identities
    FOR INSERT WITH CHECK (user_id = {S}.app_current_user_id())
    """)
    op.execute(f"""
    CREATE POLICY identities_self_update ON {S}.user_identities
    FOR UPDATE USING (user_id = {S}.app_current_user_id())
    WITH CHECK (user_id = {S}.app_current_user_id())
    """)
    op.execute(f"""
    CREATE POLICY sessions_self_insert ON {S}.auth_sessions
    FOR INSERT WITH CHECK (user_id = {S}.app_current_user_id())
    """)
    op.execute(f"""
    CREATE POLICY sessions_current_select ON {S}.auth_sessions
    FOR SELECT USING (session_token_hash = {S}.app_current_session_hash())
    """)
    op.execute(f"""
    CREATE POLICY sessions_current_update ON {S}.auth_sessions
    FOR UPDATE USING (session_token_hash = {S}.app_current_session_hash())
    WITH CHECK (session_token_hash = {S}.app_current_session_hash())
    """)


def downgrade() -> None:
    for policy, table in [
        ("sessions_current_update", "auth_sessions"),
        ("sessions_current_select", "auth_sessions"),
        ("sessions_self_insert", "auth_sessions"),
        ("identities_self_update", "user_identities"),
        ("identities_self_insert", "user_identities"),
    ]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {S}.{table}")
    op.execute(f"DROP FUNCTION IF EXISTS {S}.app_current_session_hash()")
