"""Schemas for explicit Contextual Intake decisions."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

IntakeDecision = Literal["save_to_profile", "analysis_only", "defer"]
ClinicalSection = Literal["conditions", "allergies", "medications", "supplements"]


class ContextualIntakeDecisionRequest(BaseModel):
    prompt_key: str = Field(min_length=1, max_length=128)
    context_type: str = Field(default="clinical_context", min_length=1, max_length=64)
    decision: IntakeDecision
    proposed_section: ClinicalSection | None = None
    analysis_scope_id: uuid.UUID | None = None
    record_payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_decision_shape(self):
        if self.decision == "save_to_profile":
            if self.proposed_section is None or self.record_payload is None:
                raise ValueError("save_to_profile requires proposed_section and record_payload")
            if self.analysis_scope_id is not None:
                raise ValueError("save_to_profile cannot include analysis_scope_id")
        elif self.decision == "analysis_only":
            if self.analysis_scope_id is None:
                raise ValueError("analysis_only requires analysis_scope_id")
            if self.record_payload is not None:
                raise ValueError("analysis_only cannot persist record_payload")
        else:
            if self.analysis_scope_id is not None or self.record_payload is not None:
                raise ValueError("defer cannot include analysis_scope_id or record_payload")
        return self


class ContextualIntakeDecisionResponse(BaseModel):
    decision_id: uuid.UUID
    decision: IntakeDecision
    record_id: uuid.UUID | None = None
