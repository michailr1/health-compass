"""Unit tests for Basic Health Profile request validation."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.health_profile import (
    BodyMeasurementCreateRequest,
    ConsentAcceptRequest,
    MeasurementVoidRequest,
    ProfilePatchRequest,
)


def test_profile_patch_accepts_supported_values() -> None:
    payload = ProfilePatchRequest(
        display_name="Михаил",
        date_of_birth=datetime.date(1985, 1, 1),
        sex="male",
        height_cm=Decimal("188.00"),
        timezone="Europe/Paris",
    )

    assert payload.sex == "male"
    assert payload.height_cm == Decimal("188.00")
    assert payload.timezone == "Europe/Paris"


def test_profile_patch_strips_display_name() -> None:
    payload = ProfilePatchRequest(display_name="  Михаил  ")
    assert payload.display_name == "Михаил"


def test_profile_patch_rejects_blank_display_name() -> None:
    with pytest.raises(ValidationError):
        ProfilePatchRequest(display_name="   ")


def test_profile_patch_rejects_future_birth_date() -> None:
    with pytest.raises(ValidationError):
        ProfilePatchRequest(
            date_of_birth=datetime.date.today() + datetime.timedelta(days=1)
        )


def test_profile_patch_rejects_unknown_sex() -> None:
    with pytest.raises(ValidationError):
        ProfilePatchRequest(sex="unknown")


def test_profile_patch_accepts_explicit_null_sex() -> None:
    payload = ProfilePatchRequest(sex=None)
    assert payload.model_dump(exclude_unset=True) == {"sex": None}


def test_profile_patch_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError):
        ProfilePatchRequest(timezone="Not/A_Real_Zone")


def test_weight_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValidationError):
        BodyMeasurementCreateRequest(
            value=Decimal("98.0"),
            measured_at=datetime.datetime(2026, 7, 9, 8, 0, 0),
        )


def test_weight_accepts_timezone_aware_timestamp() -> None:
    payload = BodyMeasurementCreateRequest(
        value=Decimal("98.0"),
        measured_at=datetime.datetime(
            2026,
            7,
            9,
            8,
            0,
            0,
            tzinfo=datetime.timezone(datetime.timedelta(hours=2)),
        ),
    )

    assert payload.measurement_type == "weight"
    assert payload.unit == "kg"
    assert payload.value == Decimal("98.0")


def test_void_reason_is_trimmed_and_cannot_be_blank() -> None:
    assert MeasurementVoidRequest(reason="  Ошибка ввода  ").reason == "Ошибка ввода"
    with pytest.raises(ValidationError):
        MeasurementVoidRequest(reason="   ")


def test_consent_accepts_only_current_document_version() -> None:
    payload = ConsentAcceptRequest(document_version="health-data-processing-v1")
    assert payload.document_version == "health-data-processing-v1"

    with pytest.raises(ValidationError):
        ConsentAcceptRequest(document_version="arbitrary-version")
