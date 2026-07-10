"""Summary and review-state schemas for Clinical Context."""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, model_validator

ClinicalSection = Literal["conditions", "allergies", "medications", "supplements"]
StoredReviewState = Literal["unknown", "deferred", "confirmed_none"]
EffectiveReviewState = Literal["unknown", "deferred", "confirmed_none", "has_entries"]


class ClinicalSectionReviewRequest(BaseModel):
    section: ClinicalSection
    review_state: StoredReviewState
    expected_updated_at: datetime.datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def map_legacy_confirmed_empty(cls, value: Any) -> Any:
        if isinstance(value, dict) and "review_state" not in value and "confirmed_empty" in value:
            value = dict(value)
            value["review_state"] = "confirmed_none" if value.pop("confirmed_empty") else "unknown"
        return value


class ClinicalSectionState(BaseModel):
    review_state: StoredReviewState
    effective_state: EffectiveReviewState
    reviewed_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None
    active_count: int
    history_count: int


class ClinicalContextSummary(BaseModel):
    profile_id: uuid.UUID
    sections: dict[ClinicalSection, ClinicalSectionState]
