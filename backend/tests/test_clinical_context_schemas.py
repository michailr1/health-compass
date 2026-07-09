from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from app.schemas.clinical_context import (
    AllergyCreateRequest,
    AllergyPatchRequest,
    MedicationCreateRequest,
    MedicationPatchRequest,
)


def test_medication_dates_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        MedicationCreateRequest(
            medication_name="Test",
            started_on=datetime.date(2026, 7, 10),
            ended_on=datetime.date(2026, 7, 9),
        )


def test_blank_allergen_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AllergyCreateRequest(allergen="   ")


def test_blank_medication_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MedicationCreateRequest(medication_name="   ")


def test_patch_cannot_clear_required_names() -> None:
    with pytest.raises(ValidationError):
        AllergyPatchRequest(allergen=None)
    with pytest.raises(ValidationError):
        MedicationPatchRequest(medication_name=None)
