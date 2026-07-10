"""Read-only curated dictionary models for Clinical Context."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "health_compass"


class ClinicalDictionaryConcept(Base):
    __tablename__ = "clinical_dictionary_concepts"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(255), nullable=False)
    qualifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    source_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ClinicalDictionaryAlias(Base):
    __tablename__ = "clinical_dictionary_aliases"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.clinical_dictionary_concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
