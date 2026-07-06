"""Initial migration: create technical tables.

Revision ID: 0001
Revises: None
Create Date: 2026-07-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schema
    op.execute("CREATE SCHEMA IF NOT EXISTS health_compass")

    # service_metadata
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
        schema="health_compass",
    )

    # audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=True),
        sa.Column("actor_user_id", sa.String(255), nullable=True, index=True),
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
        schema="health_compass",
    )

    # processing_jobs
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(100), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
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
        schema="health_compass",
    )


def downgrade() -> None:
    op.drop_table("processing_jobs", schema="health_compass")
    op.drop_table("audit_events", schema="health_compass")
    op.drop_table("service_metadata", schema="health_compass")
    # Schema is kept — Alembic manages alembic_version in it
