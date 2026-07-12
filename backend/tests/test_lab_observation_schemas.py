"""Unit tests for HC-017 E1 laboratory draft request contracts."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.lab_observation import LabDraftFields


def _numeric_fields() -> dict[str, object]:
    return {
        "source_analyte_text": "Глюкоза",
        "source_value_text": "5.4",
        "value_kind": "numeric",
        "numeric_value": Decimal("5.4"),
        "source_unit_text": "ммоль/л",
        "unit_not_present": False,
        "source_reference_range_text": "3.9–6.1",
        "reference_range_not_present": False,
        "source_observed_at_text": "12.07.2026",
        "observed_time_unknown": False,
        "observed_date": datetime.date(2026, 7, 12),
        "observed_precision": "date",
    }


def test_numeric_source_preserving_payload_is_valid() -> None:
    fields = LabDraftFields.model_validate(_numeric_fields())
    assert fields.numeric_value == Decimal("5.4")
    assert fields.source_value_text == "5.4"
    assert fields.source_unit_text == "ммоль/л"


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {"unit_not_present": True},
            "unit text and unit_not_present must be explicit alternatives",
        ),
        (
            {"source_unit_text": None, "unit_not_present": False},
            "unit text and unit_not_present must be explicit alternatives",
        ),
        (
            {"reference_range_not_present": True},
            "reference range text and absence flag must be explicit alternatives",
        ),
        (
            {"observed_time_unknown": True},
            "observed source text and unknown flag must be explicit alternatives",
        ),
        (
            {"observed_precision": "unknown"},
            "unknown precision cannot contain parsed time",
        ),
        (
            {"value_kind": "text", "text_value": "5.4"},
            "text value requires only text_value",
        ),
    ],
)
def test_invalid_or_ambiguous_payload_is_rejected(
    updates: dict[str, object],
    message: str,
) -> None:
    payload = _numeric_fields()
    payload.update(updates)
    with pytest.raises(ValidationError, match=message):
        LabDraftFields.model_validate(payload)


def test_qualitative_value_preserves_source_wording() -> None:
    fields = LabDraftFields.model_validate(
        {
            "source_analyte_text": "Антитела",
            "source_value_text": "не обнаружено",
            "value_kind": "qualitative",
            "qualitative_value_text": "не обнаружено",
            "source_unit_text": None,
            "unit_not_present": True,
            "source_reference_range_text": None,
            "reference_range_not_present": True,
            "source_observed_at_text": None,
            "observed_time_unknown": True,
            "observed_precision": "unknown",
        }
    )
    assert fields.qualitative_value_text == "не обнаружено"
    assert fields.source_value_text == "не обнаружено"
