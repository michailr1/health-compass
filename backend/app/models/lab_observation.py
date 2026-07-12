"""HC-017 source-preserving Lab draft and confirmed observation models."""

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
        ForeignKeyConstraint(
            ["document_id", "profile_id"],
            [
                f"{SCHEMA}.profile_documents.id",
                f"{SCHEMA}.profile_documents.profile_id",
            ],
            name="fk_lab_observations_document_profile",
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
    source_draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.lab_observation_drafts.id"),
        nullable=False,
        unique=True,
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
    confirmation_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    draft_updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    document_updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    review_finalized_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    patient_decision_updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ack_source_matches: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ack_metadata_matches: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ack_profile_selected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ack_not_present_assignment: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ack_no_interpretation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confirmed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=False
    )
    confirmed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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
    reviewed_text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
