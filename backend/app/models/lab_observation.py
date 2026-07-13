"""HC-017 E1-E3 laboratory draft, observation and lifecycle models."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "health_compass"


class LabObservationDraft(Base):
    __tablename__ = "lab_observation_drafts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "profile_id"],
            [
                f"{SCHEMA}.profile_documents.id",
                f"{SCHEMA}.profile_documents.profile_id",
            ],
            name="fk_lab_observation_drafts_document_profile",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "confirmed_observation_id",
            name="uq_lab_observation_drafts_confirmed_observation",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.health_profiles.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ocr_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.document_ocr_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    patient_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.document_ocr_patient_decisions.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_analyte_text: Mapped[str] = mapped_column(String(500), nullable=False)
    source_value_text: Mapped[str] = mapped_column(String(500), nullable=False)
    value_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    comparator: Mapped[str | None] = mapped_column(String(8), nullable=True)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 12), nullable=True)
    text_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    qualitative_value_text: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    source_unit_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit_not_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_reference_range_text: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    reference_range_not_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_observed_at_text: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    observed_time_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    observed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_precision: Mapped[str] = mapped_column(String(32), nullable=False)
    source_specimen_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_flag_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=False
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=False
    )
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=True
    )
    confirmed_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.lab_observations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LabObservationDraftSource(Base):
    __tablename__ = "lab_observation_draft_sources"
    __table_args__ = (
        UniqueConstraint(
            "draft_id",
            "candidate_id",
            "source_role",
            name="uq_lab_observation_draft_source",
        ),
        ForeignKeyConstraint(
            ["document_id", "profile_id"],
            [
                f"{SCHEMA}.profile_documents.id",
                f"{SCHEMA}.profile_documents.profile_id",
            ],
            name="fk_lab_draft_sources_document_profile",
            ondelete="CASCADE",
        ),
        {"schema": SCHEMA},
    )

    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.lab_observation_drafts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.document_ocr_candidates.id"),
        primary_key=True,
    )
    source_role: Mapped[str] = mapped_column(String(32), primary_key=True)
    candidate_updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.health_profiles.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ocr_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.document_ocr_runs.id"), nullable=False
    )
    page_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.document_artifacts.id"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)


class LabObservation(Base):
    __tablename__ = "lab_observations"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "confirmation_idempotency_key",
            name="uq_lab_observations_profile_idempotency",
        ),
        UniqueConstraint("source_draft_id", name="uq_lab_observations_source_draft"),
        UniqueConstraint(
            "supersedes_observation_id", name="uq_lab_observations_supersedes"
        ),
        UniqueConstraint(
            "superseded_by_observation_id",
            name="uq_lab_observations_superseded_by",
        ),
        ForeignKeyConstraint(
            ["document_id", "profile_id"],
            [
                f"{SCHEMA}.profile_documents.id",
                f"{SCHEMA}.profile_documents.profile_id",
            ],
            name="fk_lab_observations_document_profile",
            ondelete="RESTRICT",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.health_profiles.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ocr_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.document_ocr_runs.id"), nullable=False
    )
    patient_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.document_ocr_patient_decisions.id"),
        nullable=False,
    )
    source_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.lab_observation_drafts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    patient_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    source_analyte_text: Mapped[str] = mapped_column(String(500), nullable=False)
    source_value_text: Mapped[str] = mapped_column(String(500), nullable=False)
    value_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    comparator: Mapped[str | None] = mapped_column(String(8), nullable=True)
    numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 12), nullable=True)
    text_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    qualitative_value_text: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    source_unit_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit_not_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_reference_range_text: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    reference_range_not_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_observed_at_text: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    observed_time_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    observed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_precision: Mapped[str] = mapped_column(String(32), nullable=False)
    source_specimen_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_flag_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_draft_updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_document_updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_review_finalized_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_patient_decision_updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    confirmation_idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    ack_source: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ack_unit_range: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ack_observed_at: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ack_profile: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ack_structured_record: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ack_not_present_assignment: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confirmed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=False
    )
    confirmed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    lifecycle_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lifecycle_updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    supersedes_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{SCHEMA}.lab_observations.id",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=True,
    )
    superseded_by_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{SCHEMA}.lab_observations.id",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=True,
    )
    superseded_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    superseded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    voided_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    voided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=True
    )
    void_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class LabObservationSource(Base):
    __tablename__ = "lab_observation_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "profile_id"],
            [
                f"{SCHEMA}.profile_documents.id",
                f"{SCHEMA}.profile_documents.profile_id",
            ],
            name="fk_lab_observation_sources_document_profile",
            ondelete="RESTRICT",
        ),
        {"schema": SCHEMA},
    )

    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.lab_observations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.document_ocr_candidates.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    source_role: Mapped[str] = mapped_column(String(32), primary_key=True)
    candidate_updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.health_profiles.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ocr_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.document_ocr_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    page_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.document_artifacts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
