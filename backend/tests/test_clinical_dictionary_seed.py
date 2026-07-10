"""Tests for versioned Clinical Dictionaries v2 seed manifests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.clinical_dictionary_seed import concept_uuid, load_seed_manifest

SEED_PATH = Path(__file__).parents[1] / "data" / "clinical_dictionary" / "ru-RU-pilot-v1.json"


def test_russian_pilot_seed_is_valid_and_balanced() -> None:
    manifest = load_seed_manifest(SEED_PATH)

    assert manifest.version == "ru-RU-pilot-v1"
    assert len(manifest.concepts) == 32
    assert {concept.domain for concept in manifest.concepts} == {
        "condition_or_symptom",
        "allergy_or_intolerance",
        "medication",
        "supplement",
    }
    assert all(concept.locale == "ru-RU" for concept in manifest.concepts)
    assert all(concept.country == "RU" for concept in manifest.concepts)
    assert all(concept.display_name for concept in manifest.concepts)


def test_seed_concept_ids_are_deterministic() -> None:
    manifest = load_seed_manifest(SEED_PATH)
    concept = manifest.concepts[0]

    assert concept_uuid(concept) == concept_uuid(concept)


def test_seed_rejects_non_russian_primary_locale(tmp_path: Path) -> None:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    payload["concepts"][0]["locale"] = "en-US"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="primary display locale must be ru-RU"):
        load_seed_manifest(invalid_path)


def test_seed_rejects_duplicate_normalized_concepts(tmp_path: Path) -> None:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    duplicate = dict(payload["concepts"][0])
    duplicate["display_name"] = "  ГОЛОВНАЯ   БОЛЬ "
    payload["concepts"].append(duplicate)
    invalid_path = tmp_path / "duplicate.json"
    invalid_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate concept"):
        load_seed_manifest(invalid_path)
