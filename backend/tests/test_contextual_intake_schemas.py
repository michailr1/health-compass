"""Contract tests for HC-012c Contextual Intake decisions."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.contextual_intake import ContextualIntakeDecisionRequest


def test_save_to_profile_requires_section_and_payload() -> None:
    payload = ContextualIntakeDecisionRequest(
        prompt_key="analysis.medication.detected",
        decision="save_to_profile",
        proposed_section="medications",
        record_payload={"display_name": "Метформин", "status": "active"},
    )
    assert payload.decision == "save_to_profile"


def test_analysis_only_requires_scope_and_rejects_record_payload() -> None:
    scope_id = uuid.uuid4()
    payload = ContextualIntakeDecisionRequest(
        prompt_key="analysis.medication.detected",
        decision="analysis_only",
        proposed_section="medications",
        analysis_scope_id=scope_id,
    )
    assert payload.analysis_scope_id == scope_id

    with pytest.raises(ValidationError):
        ContextualIntakeDecisionRequest(
            prompt_key="analysis.medication.detected",
            decision="analysis_only",
            proposed_section="medications",
            analysis_scope_id=scope_id,
            record_payload={"display_name": "Метформин"},
        )


def test_defer_rejects_transient_or_durable_payloads() -> None:
    with pytest.raises(ValidationError):
        ContextualIntakeDecisionRequest(
            prompt_key="analysis.medication.detected",
            decision="defer",
            record_payload={"display_name": "Метформин"},
        )
