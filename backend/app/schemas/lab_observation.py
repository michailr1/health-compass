"""API schemas for HC-017 E1 source-preserving laboratory drafts."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.document_ocr import DocumentOCRCandidateResponse

LabDraftStatus = Literal["draft", "ready", "rejected"]
LabValueKind = Literal["numeric", "text", "qualitative"]
LabComparator = Literal["<", "<=", "=", ">=", ">"]
ObservedPrecision = Literal["unknown", "date", "datetime"]
LabSourceRole = Literal[
    "analyte",
    "value",
    "unit",
    "reference_range",
    "observed_at",
    "specimen",
    "flag",
    "comment",
]


class LabDraftFields(BaseModel):
    source_analyte_text: str = Field(min_length=1, max_length=500)
    source_value_text: str = Field(min_length=1, max_length=500)
    value_kind: LabValueKind
    comparator: LabComparator | None = None
    numeric_value: Decimal | None = None
    text_value: str | None = Field(default=None, min_length=1, max_length=500)
    qualitative_value_text: str | None = Field(
        default=None, min_length=1, max_length=500
    )
    source_unit_text: str | None = Field(default=None, min_length=1, max_length=200)
    unit_not_present: bool
    source_reference_range_text: str | None = Field(
        default=None, min_length=1, max_length=500
    )
    reference_range_not_present: bool
    source_observed_at_text: str | None = Field(
        default=None, min_length=1, max_length=500
    )
    observed_time_unknown: bool
    observed_date: datetime.date | None = None
    observed_at: datetime.datetime | None = None
    observed_precision: ObservedPrecision
    source_specimen_text: str | None = Field(
        default=None, min_length=1, max_length=500
    )
    source_flag_text: str | None = Field(default=None, min_length=1, max_length=200)
    source_comment: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_explicit_source_contract(self) -> "LabDraftFields":
        if self.value_kind == "numeric":
            if (
                self.numeric_value is None
                or self.text_value is not None
                or self.qualitative_value_text is not None
            ):
                raise ValueError("numeric value requires only numeric_value")
        elif self.value_kind == "text":
            if (
                self.text_value is None
                or self.numeric_value is not None
                or self.qualitative_value_text is not None
            ):
                raise ValueError("text value requires only text_value")
            if self.comparator is not None:
                raise ValueError("text value cannot have comparator")
        else:
            if (
                self.qualitative_value_text is None
                or self.numeric_value is not None
                or self.text_value is not None
            ):
                raise ValueError(
                    "qualitative value requires only qualitative_value_text"
                )
            if self.comparator is not None:
                raise ValueError("qualitative value cannot have comparator")

        if self.unit_not_present == (self.source_unit_text is not None):
            raise ValueError(
                "unit text and unit_not_present must be explicit alternatives"
            )
        if self.reference_range_not_present == (
            self.source_reference_range_text is not None
        ):
            raise ValueError(
                "reference range text and absence flag must be explicit alternatives"
            )
        if self.observed_time_unknown == (self.source_observed_at_text is not None):
            raise ValueError(
                "observed source text and unknown flag must be explicit alternatives"
            )

        if self.observed_precision == "unknown":
            if self.observed_date is not None or self.observed_at is not None:
                raise ValueError("unknown precision cannot contain parsed time")
        elif self.observed_precision == "date":
            if self.observed_date is None or self.observed_at is not None:
                raise ValueError("date precision requires only observed_date")
        else:
            if self.observed_at is None or self.observed_date is not None:
                raise ValueError("datetime precision requires only observed_at")
        if self.observed_time_unknown and self.observed_precision != "unknown":
            raise ValueError("unknown source time requires unknown precision")
        return self


class LabDraftSourceVersion(BaseModel):
    candidate_id: uuid.UUID
    source_role: LabSourceRole
    expected_updated_at: datetime.datetime


class LabDraftSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: uuid.UUID
    source_role: LabSourceRole
    candidate_updated_at: datetime.datetime
    page_artifact_id: uuid.UUID
    page_number: int


class LabDraftResponse(LabDraftFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    document_id: uuid.UUID
    ocr_run_id: uuid.UUID
    patient_decision_id: uuid.UUID
    status: LabDraftStatus
    sources: list[LabDraftSourceResponse] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime


class LabDraftContextResponse(BaseModel):
    document_id: uuid.UUID
    profile_id: uuid.UUID
    document_updated_at: datetime.datetime
    ocr_run_id: uuid.UUID
    review_finalized_at: datetime.datetime
    patient_decision_id: uuid.UUID
    patient_decision: Literal["match", "not_present"]
    patient_decision_updated_at: datetime.datetime
    candidates: list[DocumentOCRCandidateResponse]


class CreateLabDraftRequest(BaseModel):
    expected_document_updated_at: datetime.datetime
    expected_review_finalized_at: datetime.datetime
    expected_patient_decision_updated_at: datetime.datetime
    fields: LabDraftFields


class UpdateLabDraftRequest(BaseModel):
    expected_updated_at: datetime.datetime
    expected_document_updated_at: datetime.datetime
    expected_review_finalized_at: datetime.datetime
    expected_patient_decision_updated_at: datetime.datetime
    fields: LabDraftFields


class LabDraftContextVersions(BaseModel):
    expected_document_updated_at: datetime.datetime
    expected_review_finalized_at: datetime.datetime
    expected_patient_decision_updated_at: datetime.datetime


class SetLabDraftSourcesRequest(LabDraftContextVersions):
    expected_updated_at: datetime.datetime
    sources: list[LabDraftSourceVersion] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_sources(self) -> "SetLabDraftSourcesRequest":
        keys = {(item.candidate_id, item.source_role) for item in self.sources}
        if len(keys) != len(self.sources):
            raise ValueError("duplicate candidate/source role pair")
        return self


class SetLabDraftStatusRequest(LabDraftContextVersions):
    status: Literal["ready", "rejected"]
    expected_updated_at: datetime.datetime
