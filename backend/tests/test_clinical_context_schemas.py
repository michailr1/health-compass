"""Unit tests for Clinical Context request validation."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.clinical_context import (
    ClinicalVoidRequest,
    ConditionCreateRequest,
    MedicationCreateRequest,
    SafetyFlagCreateRequest,
    SupplementCreateRequest,
)
from app.schemas.clinical_context_summary import ClinicalSectionReviewRequest


def test_manual_condition_is_confirmed_and_trimmed() -> None:
    payload = ConditionCreateRequest(display_name="  Гипертония  ")
    assert payload.display_name == "Гипертония"
    assert payload.source_type == "manual"
    assert payload.confirmation_status == "confirmed"


def test_manual_record_cannot_be_needs_review() -> None:
    with pytest.raises(ValidationError):
        ConditionCreateRequest(
            display_name="Состояние",
            source_type="manual",
            confirmation_status="needs_review",
        )


def test_medication_requires_dose_unit_pair() -> None:
    with pytest.raises(ValidationError):
        MedicationCreateRequest(display_name="Препарат", dose_value=Decimal("10"))

    payload = MedicationCreateRequest(
        display_name="Препарат",
        dose_value=Decimal("10"),
        dose_unit=" mg ",
    )
    assert payload.dose_unit == "mg"


def test_medication_rejects_invalid_date_order() -> None:
    with pytest.raises(ValidationError):
        MedicationCreateRequest(
            display_name="Препарат",
            start_date=datetime.date(2026, 7, 10),
            end_date=datetime.date(2026, 7, 9),
        )


def test_supplement_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        SupplementCreateRequest(display_name="   ")


def test_safety_flag_requires_explicit_true_confirmation() -> None:
    with pytest.raises(ValidationError):
        SafetyFlagCreateRequest(
            flag_type="nutrition_calorie_feedback_suppressed",
            explicit_user_confirmation=False,
        )

    payload = SafetyFlagCreateRequest(
        flag_type="nutrition_calorie_feedback_suppressed",
        explicit_user_confirmation=True,
    )
    assert payload.explicit_user_confirmation is True


def test_void_reason_is_trimmed_and_not_blank() -> None:
    assert ClinicalVoidRequest(reason="  Ошибка ввода  ").reason == "Ошибка ввода"
    with pytest.raises(ValidationError):
        ClinicalVoidRequest(reason="   ")


def test_review_request_accepts_only_known_sections() -> None:
    payload = ClinicalSectionReviewRequest(section="allergies", confirmed_empty=True)
    assert payload.confirmed_empty is True

    with pytest.raises(ValidationError):
        ClinicalSectionReviewRequest(section="unknown", confirmed_empty=True)
