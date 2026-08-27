"""Remove unused legacy technical tables and harden magic-link functions.

Revision ID: 0063
Revises: 0062

The original bootstrap left three unused technical tables directly writable by
the application role. They are not part of the current product model and have
no RLS boundary. Remove that dormant attack surface and align the two oldest
SECURITY DEFINER magic-link functions with the repository-wide empty
``search_path`` invariant.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
ISSUE_MAGIC_LINK = f"{S}.app_issue_email_login_token(text, text, timestamptz, text, text)"
CONSUME_MAGIC_LINK = f"{S}.app_consume_email_login_token(text)"


def _set_magic_link_search_path_empty() -> None:
    for signature in (ISSUE_MAGIC_LINK, CONSUME_MAGIC_LINK):
        op.execute(f"ALTER FUNCTION {signature} SET search_path = ''")


def _restore_magic_link_search_path() -> None:
    for signature in (ISSUE_MAGIC_LINK, CONSUME_MAGIC_LINK):
        op.execute(f"ALTER FUNCTION {signature} SET search_path = {S}, pg_temp")


def upgrade() -> None:
    _set_magic_link_search_path_empty()

    # No CASCADE: an unexpected dependency must stop the migration rather than
    # silently deleting a newly introduced consumer.
    op.drop_table("processing_jobs", schema=S)
    op.drop_table("audit_events", schema=S)
    op.drop_table("service_metadata", schema=S)


def downgrade() -> None:
    # Restore the exact bootstrap-era schema and application privileges so the
    # 0062 state remains a real, usable migration boundary.
    op.create_table(
        "service_metadata",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=S,
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=True),
        sa.Column("actor_user_id", sa.String(255), nullable=True),
        sa.Column("profile_id", sa.String(255), nullable=True),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=S,
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], schema=S)
    op.create_index(
        "ix_audit_events_actor_user_id",
        "audit_events",
        ["actor_user_id"],
        schema=S,
    )

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        schema=S,
    )
    op.create_index("ix_processing_jobs_job_type", "processing_jobs", ["job_type"], schema=S)
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"], schema=S)

    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP}') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON
              {S}.service_metadata,
              {S}.audit_events,
              {S}.processing_jobs
            TO {APP};
          END IF;
        END $$;
        """
    )

    _restore_magic_link_search_path()
