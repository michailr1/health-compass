"""Schemas for Clinical Context dictionary suggestions."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel

SuggestionSource = Literal["personal", "global"]


class ClinicalSuggestion(BaseModel):
    id: uuid.UUID | None = None
    display_text: str
    qualifier: str | None = None
    source: SuggestionSource
    canonical_concept_id: uuid.UUID | None = None
    matched_text: str


class ClinicalSuggestionList(BaseModel):
    items: list[ClinicalSuggestion]
