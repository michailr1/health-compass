"""Schema tests for owner-initiated permanent Clinical Context erasure."""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from app.schemas.clinical_erasure import ClinicalEraseRequest


def test_permanent_erasure_requires_explicit_true_confirmation() -> None:
    timestamp = datetime.datetime.now(datetime.UTC)
    with pytest.raises(ValidationError):
        ClinicalEraseRequest(
            expected_updated_at=timestamp,
            confirm_permanent_deletion=False,
        )


def test_permanent_erasure_requires_concurrency_timestamp() -> None:
    with pytest.raises(ValidationError):
        ClinicalEraseRequest(confirm_permanent_deletion=True)


def test_permanent_erasure_accepts_explicit_confirmation_and_timestamp() -> None:
    timestamp = datetime.datetime.now(datetime.UTC)
    payload = ClinicalEraseRequest(
        expected_updated_at=timestamp,
        confirm_permanent_deletion=True,
    )
    assert payload.expected_updated_at == timestamp
    assert payload.confirm_permanent_deletion is True
