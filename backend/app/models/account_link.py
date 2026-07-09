"""Short-lived account-linking intents used before user bootstrap."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "health_compass"


class AccountLinkIntent(Base):
    __tablename__ = "account_link_intents"
    __table_args__ = (
        CheckConstraint(
            "flow_type IN ("
            "'google_first_email_existing', "
            "'email_first_google_existing', "
            "'settings_add_google', "
            "'settings_add_email'"
            ")",
            name="ck_account_link_intents_flow_type",
        ),
        CheckConstraint(
            "status IN ('pending_confirmation', 'completed', 'declined', 'expired', 'cancelled')",
            name="ck_account_link_intents_status",
        ),
        CheckConstraint(
            "initiating_provider IN ('google', 'email')",
            name="ck_account_link_intents_initiating_provider",
        ),
        CheckConstraint(
            "required_provider IN ('google', 'email')",
            name="ck_account_link_intents_required_provider",
        ),
        CheckConstraint(
            "initiating_provider <> required_provider",
            name="ck_account_link_intents_distinct_providers",
        ),
        Index("ix_account_link_intents_expiry", "status", "expires_at"),
        Index("ix_account_link_intents_candidate", "candidate_user_id", "created_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    flow_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending_confirmation",
    )
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False)
    candidate_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    initiating_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    initiating_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    required_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    required_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    initiating_claims: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    browser_binding_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    state_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nonce_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pkce_verifier_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declined_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
