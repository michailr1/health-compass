"""Unit tests for Basic Health Profile request validation."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.health_profile import (
    BodyMeasurementCreateRequest,
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


def test_profile_patch_rejects_future_birth_date() -> None:
    with pytest.raises(ValidationError):
        ProfilePatchRequest(
            date_of_birth=datetime.date.today() + datetime.timedelta(days=1)
        )


def test_profile_patch_rejects_unknown_sex() -> None:
    with pytest.raises(ValidationError):
        ProfilePatchRequest(sex="unknown")


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
