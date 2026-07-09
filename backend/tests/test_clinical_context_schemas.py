from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from app.schemas.clinical_context import MedicationCreateRequest


def test_medication_dates_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        MedicationCreateRequest(
            medication_name="Test",
            started_on=datetime.date(2026, 7, 10),
            ended_on=datetime.date(2026, 7, 9),
        )
