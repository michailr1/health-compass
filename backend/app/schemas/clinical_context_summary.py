"""Summary and reviewed-empty schemas for Clinical Context."""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel

ClinicalSection = Literal["conditions", "allergies", "medications", "supplements"]


class ClinicalSectionReviewRequest(BaseModel):
    section: ClinicalSection
    confirmed_empty: bool = False


class ClinicalSectionState(BaseModel):
    reviewed: bool
    confirmed_empty: bool
    reviewed_at: datetime.datetime | None = None
    active_count: int
    total_count: int


class ClinicalContextSummary(BaseModel):
    profile_id: uuid.UUID
    sections: dict[ClinicalSection, ClinicalSectionState]
