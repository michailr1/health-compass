"""Secure document intake, processing and artifact metadata models."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "health_compass"


class ProfileDocument(Base):
    __tablename__ = "profile_documents"
    __table_args__ = (
        UniqueConstraint("id", "profile_id", name="uq_profile_documents_id_profile"),
        UniqueConstraint(
            "quarantine_storage_key",
            name="uq_profile_documents_quarantine_storage_key",
        ),
        UniqueConstraint(
            "current_storage_key",
            name="uq_profile_documents_current_storage_key",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.health_profiles.id"), nullable=False
    )
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    detected_media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    encrypted_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    quarantine_storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    current_storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    accepted_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    encryption_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    encryption_key_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scanner_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_scanned"
    )
    scanner_engine: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scanner_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scanner_signature_version: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    scanner_signature_timestamp: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scanner_completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    render_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_started"
    )
    render_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    render_engine: Mapped[str | None] = mapped_column(String(64), nullable=True)
    render_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    render_completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    voided_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    voided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=True
    )
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deletion_requested_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    erased_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "profile_id"],
            [
                f"{SCHEMA}.profile_documents.id",
                f"{SCHEMA}.profile_documents.profile_id",
            ],
            name="fk_document_processing_jobs_document_profile",
            ondelete="CASCADE",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.health_profiles.id"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DocumentArtifact(Base):
    __tablename__ = "document_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "profile_id"],
            [
                f"{SCHEMA}.profile_documents.id",
                f"{SCHEMA}.profile_documents.profile_id",
            ],
            name="fk_document_artifacts_document_profile",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "document_id",
            "run_id",
            "artifact_type",
            "page_number",
            name="uq_document_artifacts_page",
        ),
        UniqueConstraint("storage_key", name="uq_document_artifacts_storage_key"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.health_profiles.id"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    encrypted_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    encryption_format: Mapped[str] = mapped_column(String(32), nullable=False)
    encryption_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
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
