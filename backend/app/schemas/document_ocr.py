"""API schemas for HC-017 OCR extraction and human review."""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OCRRunStatus = Literal["queued", "leased", "succeeded", "failed", "cancelled"]
OCRCandidateStatus = Literal[
    "needs_review",
    "accepted",
    "edited",
    "rejected",
    "deferred",
]
OCRReviewStatus = Literal["not_started", "in_progress", "finalized"]
OCRReviewAction = Literal["accept", "edit", "reject", "defer"]
OCRPatientDecisionValue = Literal["unknown", "match", "mismatch", "not_present"]


class DocumentOCRStatusResponse(BaseModel):
    document_id: uuid.UUID
    profile_id: uuid.UUID
    status: Literal[
        "not_started",
        "queued",
        "processing",
        "review_required",
        "reviewed",
        "error",
    ]
    run_id: uuid.UUID | None
    run_status: OCRRunStatus | None
    review_status: OCRReviewStatus | None = None
    attempt: int | None
    language_spec: str | None
    psm: int | None
    engine_name: str | None
    engine_version: str | None
    candidate_count: int
    needs_review_count: int
    completed_at: datetime.datetime | None
    review_finalized_at: datetime.datetime | None = None
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
    review_note: str | None
    reviewed_at: datetime.datetime | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class DocumentOCRPatientDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    document_id: uuid.UUID
    profile_id: uuid.UUID
    decision: OCRPatientDecisionValue
    note: str | None
    decided_at: datetime.datetime
    created_at: datetime.datetime
    updated_at: datetime.datetime


class OCRCandidateVersion(BaseModel):
    id: uuid.UUID
    updated_at: datetime.datetime


class DocumentOCRReviewResponse(BaseModel):
    document_id: uuid.UUID
    profile_id: uuid.UUID
    run_id: uuid.UUID
    document_updated_at: datetime.datetime
    ocr_status: Literal["review_required", "reviewed"]
    review_status: OCRReviewStatus
    candidates: list[DocumentOCRCandidateResponse]
    candidate_versions: list[OCRCandidateVersion]
    patient_decision: DocumentOCRPatientDecisionResponse | None
    unresolved_count: int
    deferred_count: int
    can_finalize: bool
    finalized_at: datetime.datetime | None


class DocumentOCRCandidateReviewRequest(BaseModel):
    action: OCRReviewAction
    reviewed_text: str | None = Field(default=None, min_length=1, max_length=4000)
    review_note: str | None = Field(default=None, min_length=1, max_length=500)
    expected_updated_at: datetime.datetime

    @model_validator(mode="after")
    def validate_action_payload(self) -> "DocumentOCRCandidateReviewRequest":
        if self.action == "edit":
            if self.reviewed_text is None:
                raise ValueError("reviewed_text is required for edit")
        elif self.action in {"reject", "defer"} and self.reviewed_text is not None:
            raise ValueError("reviewed_text is not allowed for reject or defer")
        return self


class DocumentOCRPatientDecisionRequest(BaseModel):
    decision: OCRPatientDecisionValue
    note: str | None = Field(default=None, min_length=1, max_length=500)
    expected_document_updated_at: datetime.datetime
    expected_decision_updated_at: datetime.datetime | None = None


class DocumentOCRFinalizeRequest(BaseModel):
    expected_document_updated_at: datetime.datetime
    candidate_versions: list[OCRCandidateVersion] = Field(max_length=5000)
    expected_patient_decision_updated_at: datetime.datetime
