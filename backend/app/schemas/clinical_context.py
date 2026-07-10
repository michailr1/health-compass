"""Pydantic schemas for Clinical Context Slice 2."""

from __future__ import annotations

import datetime
import math
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SourceType = Literal["manual", "document"]
ConfirmationStatus = Literal["confirmed", "needs_review"]
ConditionStatus = Literal["active", "resolved", "inactive", "unknown"]
AllergyType = Literal["allergy", "intolerance", "unknown"]
AllergySeverity = Literal["mild", "moderate", "severe", "unknown"]
MedicationStatus = Literal["active", "completed", "paused", "stopped", "unknown"]
SupplementType = Literal["vitamin", "mineral", "herbal", "sports", "other", "unknown"]
SafetyFlagType = Literal["nutrition_calorie_feedback_suppressed"]
SafetyFlagStatus = Literal["active", "inactive"]


def _normalize_required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be blank")
    return normalized


def _validate_dates(start: datetime.date | None, end: datetime.date | None) -> None:
    if start is not None and end is not None and end < start:
        raise ValueError("end date cannot be earlier than start date")


class ClinicalCreateBase(BaseModel):
    source_type: SourceType = "manual"
    confirmation_status: ConfirmationStatus = "confirmed"

    @model_validator(mode="after")
    def validate_manual_confirmation(self):
        if self.source_type == "manual" and self.confirmation_status != "confirmed":
            raise ValueError("manual records must be confirmed")
        return self


class ConditionCreateRequest(ClinicalCreateBase):
    display_name: str = Field(min_length=1, max_length=255)
    code_system: str | None = Field(default=None, max_length=64)
    code: str | None = Field(default=None, max_length=128)
    clinical_status: ConditionStatus = "active"
    onset_date: datetime.date | None = None
    resolved_date: datetime.date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _normalize_required(value, "display_name")

    @model_validator(mode="after")
    def validate_date_order(self):
        _validate_dates(self.onset_date, self.resolved_date)
        return self


class ConditionPatchRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    code_system: str | None = Field(default=None, max_length=64)
    code: str | None = Field(default=None, max_length=128)
    clinical_status: ConditionStatus | None = None
    onset_date: datetime.date | None = None
    resolved_date: datetime.date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    expected_updated_at: datetime.datetime

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_required(value, "display_name")

    @model_validator(mode="after")
    def validate_date_order(self):
        _validate_dates(self.onset_date, self.resolved_date)
        return self


class AllergyCreateRequest(ClinicalCreateBase):
    substance_name: str = Field(min_length=1, max_length=255)
    code_system: str | None = Field(default=None, max_length=64)
    code: str | None = Field(default=None, max_length=128)
    allergy_type: AllergyType = "unknown"
    reaction: str | None = Field(default=None, max_length=500)
    severity: AllergySeverity | None = None
    clinical_status: ConditionStatus = "active"

    @field_validator("substance_name")
    @classmethod
    def validate_substance_name(cls, value: str) -> str:
        return _normalize_required(value, "substance_name")


class AllergyPatchRequest(BaseModel):
    substance_name: str | None = Field(default=None, min_length=1, max_length=255)
    code_system: str | None = Field(default=None, max_length=64)
    code: str | None = Field(default=None, max_length=128)
    allergy_type: AllergyType | None = None
    reaction: str | None = Field(default=None, max_length=500)
    severity: AllergySeverity | None = None
    clinical_status: ConditionStatus | None = None
    expected_updated_at: datetime.datetime

    @field_validator("substance_name")
    @classmethod
    def validate_substance_name(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_required(value, "substance_name")


class DoseFields(BaseModel):
    dose_value: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=4)
    dose_unit: str | None = Field(default=None, max_length=32)

    @field_validator("dose_value")
    @classmethod
    def validate_finite_dose(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not math.isfinite(float(value)):
            raise ValueError("dose_value must be finite")
        return value

    @model_validator(mode="after")
    def validate_dose_pair(self):
        if (self.dose_value is None) != (self.dose_unit is None):
            raise ValueError("dose_value and dose_unit must be provided together")
        if self.dose_unit is not None:
            self.dose_unit = _normalize_required(self.dose_unit, "dose_unit")
        return self


class MedicationCreateRequest(ClinicalCreateBase, DoseFields):
    display_name: str = Field(min_length=1, max_length=255)
    code_system: str | None = Field(default=None, max_length=64)
    code: str | None = Field(default=None, max_length=128)
    status: MedicationStatus = "active"
    frequency_text: str | None = Field(default=None, max_length=255)
    route: str | None = Field(default=None, max_length=64)
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    reason_text: str | None = Field(default=None, max_length=500)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _normalize_required(value, "display_name")

    @model_validator(mode="after")
    def validate_date_order(self):
        _validate_dates(self.start_date, self.end_date)
        return self


class MedicationPatchRequest(DoseFields):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    code_system: str | None = Field(default=None, max_length=64)
    code: str | None = Field(default=None, max_length=128)
    status: MedicationStatus | None = None
    frequency_text: str | None = Field(default=None, max_length=255)
    route: str | None = Field(default=None, max_length=64)
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    reason_text: str | None = Field(default=None, max_length=500)
    expected_updated_at: datetime.datetime

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_required(value, "display_name")

    @model_validator(mode="after")
    def validate_date_order(self):
        _validate_dates(self.start_date, self.end_date)
        return self


class SupplementCreateRequest(ClinicalCreateBase, DoseFields):
    display_name: str = Field(min_length=1, max_length=255)
    supplement_type: SupplementType = "unknown"
    code_system: str | None = Field(default=None, max_length=64)
    code: str | None = Field(default=None, max_length=128)
    status: MedicationStatus = "active"
    frequency_text: str | None = Field(default=None, max_length=255)
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _normalize_required(value, "display_name")

    @model_validator(mode="after")
    def validate_date_order(self):
        _validate_dates(self.start_date, self.end_date)
        return self


class SupplementPatchRequest(DoseFields):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    supplement_type: SupplementType | None = None
    code_system: str | None = Field(default=None, max_length=64)
    code: str | None = Field(default=None, max_length=128)
    status: MedicationStatus | None = None
    frequency_text: str | None = Field(default=None, max_length=255)
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    expected_updated_at: datetime.datetime

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_required(value, "display_name")

    @model_validator(mode="after")
    def validate_date_order(self):
        _validate_dates(self.start_date, self.end_date)
        return self


class SafetyFlagCreateRequest(ClinicalCreateBase):
    flag_type: SafetyFlagType
    status: SafetyFlagStatus = "active"
    source_entity_type: str | None = Field(default=None, max_length=64)
    source_entity_id: uuid.UUID | None = None
    explicit_user_confirmation: Literal[True]


class SafetyFlagPatchRequest(BaseModel):
    status: SafetyFlagStatus
    source_entity_type: str | None = Field(default=None, max_length=64)
    source_entity_id: uuid.UUID | None = None
    expected_updated_at: datetime.datetime
    explicit_user_confirmation: Literal[True]


class ClinicalVoidRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        return _normalize_required(value, "reason")


class ClinicalResponseBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    source_type: str
    confirmation_status: str
    created_by_user_id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
    voided_at: datetime.datetime | None = None
    voided_by_user_id: uuid.UUID | None = None
    void_reason: str | None = None


class ConditionResponse(ClinicalResponseBase):
    display_name: str
    code_system: str | None = None
    code: str | None = None
    clinical_status: str
    onset_date: datetime.date | None = None
    resolved_date: datetime.date | None = None
    notes: str | None = None


class AllergyResponse(ClinicalResponseBase):
    substance_name: str
    code_system: str | None = None
    code: str | None = None
    allergy_type: str
    reaction: str | None = None
    severity: str | None = None
    clinical_status: str


class MedicationResponse(ClinicalResponseBase):
    display_name: str
    code_system: str | None = None
    code: str | None = None
    status: str
    dose_value: Decimal | None = None
    dose_unit: str | None = None
    frequency_text: str | None = None
    route: str | None = None
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    reason_text: str | None = None


class SupplementResponse(ClinicalResponseBase):
    display_name: str
    supplement_type: str
    code_system: str | None = None
    code: str | None = None
    status: str
    dose_value: Decimal | None = None
    dose_unit: str | None = None
    frequency_text: str | None = None
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None


class SafetyFlagResponse(ClinicalResponseBase):
    flag_type: str
    status: str
    source_entity_type: str | None = None
    source_entity_id: uuid.UUID | None = None
