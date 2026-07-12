"""Unit tests for HC-017 D2 human-review request validation."""

from __future__ import annotations

import datetime
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.document_ocr import (
    DocumentOCRCandidateReviewRequest,
    DocumentOCRFinalizeRequest,
    DocumentOCRPatientDecisionRequest,
    OCRCandidateVersion,
)

NOW = datetime.datetime(2026, 7, 12, tzinfo=datetime.UTC)


def test_edit_requires_replacement_text() -> None:
    with pytest.raises(ValidationError):
        DocumentOCRCandidateReviewRequest(
            action="edit",
            reviewed_text=None,
            expected_updated_at=NOW,
        )


def test_reject_and_defer_forbid_reviewed_text() -> None:
    for action in ("reject", "defer"):
        with pytest.raises(ValidationError):
            DocumentOCRCandidateReviewRequest(
                action=action,
                reviewed_text="not allowed",
                expected_updated_at=NOW,
            )


def test_accept_may_omit_reviewed_text() -> None:
    payload = DocumentOCRCandidateReviewRequest(
        action="accept",
        expected_updated_at=NOW,
    )
    assert payload.reviewed_text is None


def test_patient_decision_requires_document_version() -> None:
    payload = DocumentOCRPatientDecisionRequest(
        decision="match",
        expected_document_updated_at=NOW,
    )
    assert payload.expected_decision_updated_at is None


def test_finalize_keeps_candidate_versions_explicit() -> None:
    candidate_id = uuid.uuid4()
    payload = DocumentOCRFinalizeRequest(
        expected_document_updated_at=NOW,
        candidate_versions=[OCRCandidateVersion(id=candidate_id, updated_at=NOW)],
        expected_patient_decision_updated_at=NOW,
    )
    assert payload.candidate_versions[0].id == candidate_id
