"""Tests for versioned Clinical Dictionaries v2 seed manifests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.clinical_dictionary import normalize_search_text
from app.services.clinical_dictionary_seed import concept_uuid, load_seed_manifest

SEED_DIR = Path(__file__).parents[1] / "data" / "clinical_dictionary"
PILOT_SEED_PATH = SEED_DIR / "ru-RU-pilot-v1.json"
COMMON_SEED_PATH = SEED_DIR / "ru-RU-common-conditions-allergens-v1.json"
MEDICATIONS_SUPPLEMENTS_SEED_PATH = (
    SEED_DIR / "ru-RU-common-medications-supplements-v1.json"
)
ALL_SEED_PATHS = (
    PILOT_SEED_PATH,
    COMMON_SEED_PATH,
    MEDICATIONS_SUPPLEMENTS_SEED_PATH,
)


@pytest.mark.parametrize(
    ("path", "version", "count"),
    [
        (PILOT_SEED_PATH, "ru-RU-pilot-v1", 16),
        (
            COMMON_SEED_PATH,
            "ru-RU-common-conditions-allergens-v1",
            25,
        ),
        (
            MEDICATIONS_SUPPLEMENTS_SEED_PATH,
            "ru-RU-common-medications-supplements-v1",
            24,
        ),
    ],
)
def test_russian_seed_manifests_are_valid(path: Path, version: str, count: int) -> None:
    manifest = load_seed_manifest(path)

    assert manifest.version == version
    assert len(manifest.concepts) == count
    assert all(concept.locale == "ru-RU" for concept in manifest.concepts)
    assert all(concept.country == "RU" for concept in manifest.concepts)


def test_pilot_seed_covers_all_current_domains() -> None:
    manifest = load_seed_manifest(PILOT_SEED_PATH)
    assert {concept.domain for concept in manifest.concepts} == {
        "condition_or_symptom",
        "allergy_or_intolerance",
        "medication",
        "supplement",
    }


def test_common_seed_covers_conditions_and_allergens() -> None:
    manifest = load_seed_manifest(COMMON_SEED_PATH)
    assert {concept.domain for concept in manifest.concepts} == {
        "condition_or_symptom",
        "allergy_or_intolerance",
    }
    assert sum(concept.domain == "condition_or_symptom" for concept in manifest.concepts) == 12
    assert sum(concept.domain == "allergy_or_intolerance" for concept in manifest.concepts) == 13


def test_medications_supplements_seed_is_balanced() -> None:
    manifest = load_seed_manifest(MEDICATIONS_SUPPLEMENTS_SEED_PATH)
    assert {concept.domain for concept in manifest.concepts} == {
        "medication",
        "supplement",
    }
    assert sum(concept.domain == "medication" for concept in manifest.concepts) == 12
    assert sum(concept.domain == "supplement" for concept in manifest.concepts) == 12


def test_seed_batches_have_no_cross_file_duplicate_concepts() -> None:
    seen: set[tuple[str, str]] = set()
    for path in ALL_SEED_PATHS:
        for concept in load_seed_manifest(path).concepts:
            key = (concept.domain, normalize_search_text(concept.display_name))
            assert key not in seen
            seen.add(key)


def test_seed_concept_ids_are_deterministic() -> None:
    concept = load_seed_manifest(PILOT_SEED_PATH).concepts[0]
    assert concept_uuid(concept) == concept_uuid(concept)


def test_seed_rejects_non_russian_primary_locale(tmp_path: Path) -> None:
    payload = json.loads(PILOT_SEED_PATH.read_text(encoding="utf-8"))
    payload["concepts"][0]["locale"] = "en-US"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="primary display locale must be ru-RU"):
        load_seed_manifest(invalid_path)


def test_seed_rejects_duplicate_normalized_concepts(tmp_path: Path) -> None:
    payload = json.loads(PILOT_SEED_PATH.read_text(encoding="utf-8"))
    duplicate = dict(payload["concepts"][0])
    duplicate["display_name"] = "  ГОЛОВНАЯ   БОЛЬ "
    payload["concepts"].append(duplicate)
    invalid_path = tmp_path / "duplicate.json"
    invalid_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate concept"):
        load_seed_manifest(invalid_path)
