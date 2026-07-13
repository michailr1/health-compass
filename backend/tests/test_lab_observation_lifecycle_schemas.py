"""Unit tests for HC-017 E3 lifecycle request contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.lab_observation import (
    CorrectLabObservationRequest,
    EraseLabObservationRequest,
    VoidLabObservationRequest,
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


def test_correction_requires_new_snapshot_reason_version_and_idempotency() -> None:
    payload = CorrectLabObservationRequest(
        expected_lifecycle_version=1,
        idempotency_key="correct:0123456789abcdef",
        reason="Исправлена опечатка при переносе значения",
        fields=_fields(),
    )
    assert payload.fields.numeric_value == Decimal("5.6")
    assert payload.expected_lifecycle_version == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"expected_lifecycle_version": 0},
        {"idempotency_key": "short"},
        {"reason": ""},
        {"reason": "x" * 1001},
    ],
)
def test_invalid_correction_contract_is_rejected(updates: dict[str, object]) -> None:
    values: dict[str, object] = {
        "expected_lifecycle_version": 1,
        "idempotency_key": "correct:0123456789abcdef",
        "reason": "Исправление",
        "fields": _fields(),
    }
    values.update(updates)
    with pytest.raises(ValidationError):
        CorrectLabObservationRequest.model_validate(values)


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
