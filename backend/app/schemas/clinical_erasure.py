"""Schemas for owner-initiated permanent Clinical Context erasure."""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel

ClinicalEraseSection = Literal[
    "conditions",
    "allergies",
    "medications",
    "supplements",
    "clinical-safety-flags",
]


class ClinicalEraseRequest(BaseModel):
    expected_updated_at: datetime.datetime
    confirm_permanent_deletion: Literal[True]


class ClinicalEraseResponse(BaseModel):
    deleted: Literal[True]
    record_id: uuid.UUID
    section: ClinicalEraseSection
