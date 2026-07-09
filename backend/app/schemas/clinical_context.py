"""Schemas for manual allergies and medications."""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AllergySeverity = Literal["unknown", "mild", "moderate", "severe"]
AllergyStatus = Literal["active", "resolved", "entered_in_error"]
MedicationStatus = Literal["active", "paused", "stopped", "entered_in_error"]


def _strip_required(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be blank")
    return normalized


class AllergyCreateRequest(BaseModel):
    allergen: str = Field(min_length=1, max_length=255)
    reaction: str | None = Field(default=None, max_length=2000)
    severity: AllergySeverity = "unknown"
    onset_date: datetime.date | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("allergen")
    @classmethod
    def validate_allergen(cls, value: str) -> str:
        return _strip_required(value, "allergen") or ""


class AllergyPatchRequest(BaseModel):
    allergen: str | None = Field(default=None, min_length=1, max_length=255)
    reaction: str | None = Field(default=None, max_length=2000)
    severity: AllergySeverity | None = None
    status: AllergyStatus | None = None
    onset_date: datetime.date | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("allergen")
    @classmethod
    def validate_allergen(cls, value: str | None) -> str | None:
        return _strip_required(value, "allergen")

    @model_validator(mode="after")
    def reject_explicit_null_name(self):
        if "allergen" in self.model_fields_set and self.allergen is None:
            raise ValueError("allergen cannot be null")
        return self


class AllergyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    allergen: str
    reaction: str | None
    severity: str
    status: str
    onset_date: datetime.date | None
    notes: str | None
    source_kind: str
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime


class MedicationCreateRequest(BaseModel):
    medication_name: str = Field(min_length=1, max_length=255)
    dose_text: str | None = Field(default=None, max_length=255)
    schedule_text: str | None = Field(default=None, max_length=255)
    indication: str | None = Field(default=None, max_length=2000)
    started_on: datetime.date | None = None
    ended_on: datetime.date | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("medication_name")
    @classmethod
    def validate_medication_name(cls, value: str) -> str:
        return _strip_required(value, "medication_name") or ""

    @model_validator(mode="after")
    def validate_dates(self):
        if self.started_on and self.ended_on and self.ended_on < self.started_on:
            raise ValueError("ended_on cannot be before started_on")
        return self


class MedicationPatchRequest(BaseModel):
    medication_name: str | None = Field(default=None, min_length=1, max_length=255)
    dose_text: str | None = Field(default=None, max_length=255)
    schedule_text: str | None = Field(default=None, max_length=255)
    indication: str | None = Field(default=None, max_length=2000)
    status: MedicationStatus | None = None
    started_on: datetime.date | None = None
    ended_on: datetime.date | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("medication_name")
    @classmethod
    def validate_medication_name(cls, value: str | None) -> str | None:
        return _strip_required(value, "medication_name")

    @model_validator(mode="after")
    def validate_payload(self):
        if "medication_name" in self.model_fields_set and self.medication_name is None:
            raise ValueError("medication_name cannot be null")
        if self.started_on and self.ended_on and self.ended_on < self.started_on:
            raise ValueError("ended_on cannot be before started_on")
        return self


class MedicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    medication_name: str
    dose_text: str | None
    schedule_text: str | None
    indication: str | None
    status: str
    started_on: datetime.date | None
    ended_on: datetime.date | None
    notes: str | None
    source_kind: str
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ClinicalContextReviewRequest(BaseModel):
    section: Literal["allergies", "medications"]


class ClinicalContextSummary(BaseModel):
    allergies_reviewed_at: datetime.datetime | None
    medications_reviewed_at: datetime.datetime | None
    active_allergy_count: int
    severe_active_allergy_count: int
    active_medication_count: int
