"""Focused contract tests for HC-012b Slice A review states."""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from app.schemas.clinical_context_summary import (
    ClinicalContextSummary,
    ClinicalSectionReviewRequest,
    ClinicalSectionState,
)


def test_review_request_accepts_stored_states() -> None:
    for value in ("unknown", "deferred", "confirmed_none"):
        payload = ClinicalSectionReviewRequest(section="conditions", review_state=value)
        assert payload.review_state == value


def test_review_request_rejects_derived_has_entries() -> None:
    with pytest.raises(ValidationError):
        ClinicalSectionReviewRequest(section="conditions", review_state="has_entries")


def test_summary_exposes_stored_and_effective_state() -> None:
    now = datetime.datetime.now(datetime.UTC)
    section = ClinicalSectionState(
        review_state="unknown",
        effective_state="has_entries",
        reviewed_at=now,
        updated_at=now,
        active_count=1,
        history_count=2,
    )
    summary = ClinicalContextSummary(
        profile_id="00000000-0000-0000-0000-000000000001",
        sections={
            "conditions": section,
            "allergies": ClinicalSectionState(
                review_state="deferred",
                effective_state="deferred",
                active_count=0,
                history_count=0,
            ),
            "medications": ClinicalSectionState(
                review_state="confirmed_none",
                effective_state="confirmed_none",
                active_count=0,
                history_count=0,
            ),
            "supplements": ClinicalSectionState(
                review_state="unknown",
                effective_state="unknown",
                active_count=0,
                history_count=0,
            ),
        },
    )
    assert summary.sections["conditions"].effective_state == "has_entries"
    assert summary.sections["allergies"].review_state == "deferred"
