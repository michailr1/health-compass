"""Extended create schemas for observable Clinical Context questions."""

from __future__ import annotations

from typing import Literal

from app.schemas.clinical_context import ConditionCreateRequest

ConditionOnsetTiming = Literal["recent", "long_ago", "unknown"]
ConditionPresencePattern = Literal["yes", "resolved", "recurring", "unknown"]


class ConditionCreateWithQuestions(ConditionCreateRequest):
    onset_timing: ConditionOnsetTiming | None = None
    presence_pattern: ConditionPresencePattern | None = None
