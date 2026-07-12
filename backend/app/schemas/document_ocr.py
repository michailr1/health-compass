"""API schemas for HC-017 D1 OCR status and review candidates."""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

OCRRunStatus = Literal["queued", "leased", "succeeded", "failed", "cancelled"]
OCRCandidateStatus = Literal[
    "needs_review",
    "accepted",
    "edited",
    "rejected",
    "deferred",
]


class DocumentOCRStatusResponse(BaseModel):
    document_id: uuid.UUID
    profile_id: uuid.UUID
    status: Literal[
        "not_started",
        "queued",
        "processing",
        "review_required",
        "error",
    ]
    run_id: uuid.UUID | None
    run_status: OCRRunStatus | None
    attempt: int | None
    language_spec: str | None
    psm: int | None
    engine_name: str | None
    engine_version: str | None
    candidate_count: int
    needs_review_count: int
    completed_at: datetime.datetime | None
    safe_error_code: str | None


class DocumentOCRCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    document_id: uuid.UUID
    profile_id: uuid.UUID
    page_artifact_id: uuid.UUID
    page_number: int
    candidate_index: int
    status: OCRCandidateStatus
    original_text: str
    reviewed_text: str | None
    confidence_min: float
    confidence_mean: float
    left_px: int
    top_px: int
    width_px: int
    height_px: int
    source_word_count: int
    reviewed_at: datetime.datetime | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
