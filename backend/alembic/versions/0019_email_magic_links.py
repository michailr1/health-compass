"""Add secure one-time email magic links.

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-07
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "health_compass"


def upgrade() -> None:
    op.create_table(
        "email_login_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("requested_ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_email_login_tokens_hash"),
        schema=S,
    )
    op.create_index("ix_email_login_tokens_email_created", "email_login_tokens", ["email", "created_at"], schema=S)
    op.execute(f"ALTER TABLE {S}.email_login_tokens ENABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON {S}.email_login_tokens FROM health_compass_app")

    op.execute(f"""
    CREATE FUNCTION {S}.app_issue_email_login_token(
      login_email text,
      login_token_hash text,
      login_expires_at timestamptz,
      login_ip text,
      login_user_agent text
    ) RETURNS boolean
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = {S}, pg_temp
    AS $$
    BEGIN
      IF (
        SELECT count(*) FROM {S}.email_login_tokens
        WHERE email = login_email AND created_at > now() - interval '15 minutes'
      ) >= 5 THEN
        RETURN false;
      END IF;

      IF login_ip IS NOT NULL AND (
        SELECT count(*) FROM {S}.email_login_tokens
        WHERE requested_ip = login_ip AND created_at > now() - interval '15 minutes'
      ) >= 20 THEN
        RETURN false;
      END IF;

      INSERT INTO {S}.email_login_tokens(
        email, token_hash, requested_ip, user_agent, expires_at
      ) VALUES (
        login_email, login_token_hash, login_ip, login_user_agent, login_expires_at
      );
      RETURN true;
    END
    $$
    """)

    op.execute(f"""
    CREATE FUNCTION {S}.app_consume_email_login_token(login_token_hash text)
    RETURNS text
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = {S}, pg_temp
    AS $$
    DECLARE consumed_email text;
    BEGIN
      UPDATE {S}.email_login_tokens
      SET used_at = now()
      WHERE token_hash = login_token_hash
        AND used_at IS NULL
        AND expires_at > now()
      RETURNING email INTO consumed_email;
      RETURN consumed_email;
    END
    $$
    """)

    op.execute(f"GRANT EXECUTE ON FUNCTION {S}.app_issue_email_login_token(text, text, timestamptz, text, text) TO health_compass_app")
    op.execute(f"GRANT EXECUTE ON FUNCTION {S}.app_consume_email_login_token(text) TO health_compass_app")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {S}.app_consume_email_login_token(text)")
    op.execute(f"DROP FUNCTION IF EXISTS {S}.app_issue_email_login_token(text, text, timestamptz, text, text)")
    op.drop_table("email_login_tokens", schema=S)
