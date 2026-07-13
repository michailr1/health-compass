"""Unit tests for HC-017 E3 lifecycle request contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.lab_observation import (
    EraseLabObservationRequest,
    VoidLabObservationRequest,
)
from app.schemas.lab_observation_lifecycle import (
    CorrectLabObservationLifecycleRequest,
)


def _fields() -> dict[str, object]:
    return {
        "source_analyte_text": "Глюкоза",
        "source_value_text": "5.6",
        "value_kind": "numeric",
        "numeric_value": Decimal("5.6"),
        "source_unit_text": "ммоль/л",
        "unit_not_present": False,
        "source_reference_range_text": "3.9–6.1",
        "reference_range_not_present": False,
        "source_observed_at_text": "13.07.2026",
        "observed_time_unknown": False,
        "observed_date": "2026-07-13",
        "observed_precision": "date",
    }


def _correction_values() -> dict[str, object]:
    return {
        "expected_lifecycle_version": 1,
        "idempotency_key": "correct:0123456789abcdef",
        "reason": "Исправлена опечатка при переносе значения",
        "fields": _fields(),
        "acknowledge_source_matches": True,
        "acknowledge_unit_and_range": True,
        "acknowledge_observed_at": True,
        "acknowledge_profile": True,
        "acknowledge_structured_record": True,
        "acknowledge_not_present_assignment": False,
    }


def test_correction_requires_fresh_acknowledgements_and_snapshot_contract() -> None:
    payload = CorrectLabObservationLifecycleRequest.model_validate(
        _correction_values()
    )
    assert payload.fields.numeric_value == Decimal("5.6")
    assert payload.expected_lifecycle_version == 1
    assert payload.acknowledge_structured_record is True


@pytest.mark.parametrize(
    "updates",
    [
        {"expected_lifecycle_version": 0},
        {"idempotency_key": "short"},
        {"reason": ""},
        {"reason": "x" * 1001},
        {"acknowledge_source_matches": False},
        {"acknowledge_unit_and_range": False},
        {"acknowledge_observed_at": False},
        {"acknowledge_profile": False},
        {"acknowledge_structured_record": False},
    ],
)
def test_invalid_correction_contract_is_rejected(updates: dict[str, object]) -> None:
    values = _correction_values()
    values.update(updates)
    with pytest.raises(ValidationError):
        CorrectLabObservationLifecycleRequest.model_validate(values)


def test_void_requires_reason_and_optimistic_version() -> None:
    payload = VoidLabObservationRequest(
        expected_lifecycle_version=2,
        reason="Результат относится к другому исследованию",
    )
    assert payload.expected_lifecycle_version == 2


def test_permanent_erasure_requires_literal_true() -> None:
    with pytest.raises(ValidationError):
        EraseLabObservationRequest(
            expected_lifecycle_version=1,
            confirm_permanent_deletion=False,
        )
    accepted = EraseLabObservationRequest(
        expected_lifecycle_version=1,
        confirm_permanent_deletion=True,
    )
    assert accepted.confirm_permanent_deletion is True
