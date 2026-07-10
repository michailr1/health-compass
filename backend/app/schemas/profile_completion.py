"""Derived profile questionnaire completion schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CompletionState = Literal["complete", "deferred", "incomplete"]


class ProfileCompletionSection(BaseModel):
    key: str
    title: str
    state: CompletionState
    missing_fields: list[str]
    next_action: str


class ProfileCompletionSummary(BaseModel):
    completed_sections: int
    total_sections: int
    progress_percent: int
    next_section: str | None
    sections: list[ProfileCompletionSection]
