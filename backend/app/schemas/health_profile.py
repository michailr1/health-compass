"""Schemas for Basic Health Profile, measurements, and consent."""

from __future__ import annotations

import datetime
import math
import uuid
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

SexValue = Literal["male", "female", "not_specified"]
HEALTH_DATA_CONSENT_VERSION = "health-data-processing-v1"


class ProfilePatchRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    date_of_birth: datetime.date | None = None
    sex: SexValue | None = None
    height_cm: Decimal | None = Field(default=None, gt=0, max_digits=5, decimal_places=2)
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name cannot be blank")
        return normalized

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, value: datetime.date | None) -> datetime.date | None:
        if value is not None and value > datetime.date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class ProfileReadiness(BaseModel):
    age_references: bool
    sex_specific_references: bool
    bmi: bool
    local_time_context: bool
    missing_fields: list[str]


class BodyMeasurementCreateRequest(BaseModel):
    measurement_type: Literal["weight"] = "weight"
    value: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    unit: Literal["kg"] = "kg"
    measured_at: datetime.datetime
    confirm_unusual_value: bool = False

    @field_validator("value")
    @classmethod
    def validate_finite_value(cls, value: Decimal) -> Decimal:
        if not math.isfinite(float(value)):
            raise ValueError("value must be finite")
        return value

    @field_validator("measured_at")
    @classmethod
    def validate_measured_at(cls, value: datetime.datetime) -> datetime.datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("measured_at must include a timezone offset")
        return value


class BodyMeasurementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    measurement_type: str
    value: Decimal
    unit: str
    measured_at: datetime.datetime
    source_type: str
    confirmation_status: str
    created_by_user_id: uuid.UUID
    created_at: datetime.datetime
    voided_at: datetime.datetime | None = None
    voided_by_user_id: uuid.UUID | None = None
    void_reason: str | None = None


class MeasurementVoidRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason cannot be blank")
        return normalized


class ConsentAcceptRequest(BaseModel):
    document_version: Literal[HEALTH_DATA_CONSENT_VERSION]


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    consent_type: str = "health_data_processing"
    document_version: str | None = None
    accepted_at: datetime.datetime | None = None
    revoked_at: datetime.datetime | None = None
    active: bool
