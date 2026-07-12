"""Unit tests for E2 explicit confirmation request contracts."""

from __future__ import annotations

import datetime
import uuid

import pytest
from pydantic import ValidationError

from app.schemas.lab_observation import ConfirmLabObservationRequest


def _payload() -> dict[str, object]:
    now = datetime.datetime.now(datetime.UTC)
    return {
        "idempotency_key": f"confirm:{uuid.uuid4()}",
        "expected_draft_updated_at": now,
        "expected_document_updated_at": now,
        "expected_review_finalized_at": now,
        "expected_patient_decision_updated_at": now,
        "acknowledge_source_matches": True,
        "acknowledge_unit_and_range": True,
        "acknowledge_observed_at": True,
        "acknowledge_profile": True,
        "acknowledge_structured_record": True,
        "acknowledge_not_present_assignment": False,
    }


def test_confirmation_request_requires_every_base_acknowledgement() -> None:
    for field in (
        "acknowledge_source_matches",
        "acknowledge_unit_and_range",
        "acknowledge_observed_at",
        "acknowledge_profile",
        "acknowledge_structured_record",
    ):
        payload = _payload()
        payload[field] = False
        with pytest.raises(ValidationError):
            ConfirmLabObservationRequest.model_validate(payload)


def test_confirmation_request_accepts_explicit_complete_contract() -> None:
    parsed = ConfirmLabObservationRequest.model_validate(_payload())
    assert parsed.acknowledge_source_matches is True
    assert parsed.acknowledge_not_present_assignment is False


@pytest.mark.parametrize(
    "key",
    [
        "too-short",
        "contains whitespace and is invalid",
        "contains/slash/is/invalid",
    ],
)
def test_confirmation_idempotency_key_is_bounded_and_opaque(key: str) -> None:
    payload = _payload()
    payload["idempotency_key"] = key
    with pytest.raises(ValidationError):
        ConfirmLabObservationRequest.model_validate(payload)
