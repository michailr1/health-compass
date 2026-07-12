"""HC-017 D1 OCR run, provenance and review-candidate models."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "health_compass"


class DocumentOCRRun(Base):
    __tablename__ = "document_ocr_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "profile_id"],
            [
                f"{SCHEMA}.profile_documents.id",
                f"{SCHEMA}.profile_documents.profile_id",
            ],
            name="fk_document_ocr_runs_document_profile",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "document_id",
            "render_run_id",
            "language_spec",
            "psm",
            name="uq_document_ocr_runs_document_render_config",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.health_profiles.id"), nullable=False
    )
    render_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    input_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language_spec: Mapped[str] = mapped_column(String(64), nullable=False)
    traineddata_manifest_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    psm: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_attempt_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DocumentOCRArtifact(Base):
    __tablename__ = "document_ocr_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "profile_id"],
            [
                f"{SCHEMA}.profile_documents.id",
                f"{SCHEMA}.profile_documents.profile_id",
            ],
            name="fk_document_ocr_artifacts_document_profile",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "run_id",
            "page_number",
            name="uq_document_ocr_artifacts_run_page",
        ),
        UniqueConstraint("storage_key", name="uq_document_ocr_artifacts_storage_key"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.document_ocr_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.health_profiles.id"), nullable=False
    )
    page_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.document_artifacts.id"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    encrypted_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    encryption_format: Mapped[str] = mapped_column(String(32), nullable=False)
    encryption_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_name: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    language_spec: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deletion_requested_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    erased_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DocumentOCRCandidate(Base):
    __tablename__ = "document_ocr_candidates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "profile_id"],
            [
                f"{SCHEMA}.profile_documents.id",
                f"{SCHEMA}.profile_documents.profile_id",
            ],
            name="fk_document_ocr_candidates_document_profile",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "run_id",
            "page_number",
            "candidate_index",
            name="uq_document_ocr_candidates_run_index",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.document_ocr_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.health_profiles.id"), nullable=False
    )
    page_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.document_artifacts.id"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_min: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_mean: Mapped[float] = mapped_column(Float, nullable=False)
    left_px: Mapped[int] = mapped_column(Integer, nullable=False)
    top_px: Mapped[int] = mapped_column(Integer, nullable=False)
    width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    source_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
