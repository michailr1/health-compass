"""Tests for versioned Clinical Dictionaries v2 seed manifests."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql

from app.services.clinical_dictionary import normalize_search_text
from app.services.clinical_dictionary_seed import (
    SeedAlias,
    SeedConcept,
    SeedManifest,
    concept_uuid,
    load_seed_manifest,
    upsert_seed_manifest,
)

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
            25,
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
    assert sum(concept.domain == "supplement" for concept in manifest.concepts) == 13


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


@pytest.mark.asyncio
async def test_upsert_uses_business_key_and_existing_concept_id_for_aliases() -> None:
    existing_id = uuid.uuid4()
    concept = SeedConcept(
        domain="condition_or_symptom",
        display_name="Головная боль",
        source_system="health_compass_ru_curated",
        source_code="condition-headache",
        qualifier="симптом",
        locale="ru-RU",
        country="RU",
        aliases=(SeedAlias(text="Headache", language="en", kind="international"),),
    )
    manifest = SeedManifest(version="test", source_label="test", concepts=(concept,))

    class Result:
        def scalar_one(self) -> uuid.UUID:
            return existing_id

    class Session:
        def __init__(self) -> None:
            self.statements: list[object] = []

        async def execute(self, statement: object) -> Result:
            self.statements.append(statement)
            return Result()

    session = Session()
    result = await upsert_seed_manifest(session, manifest)  # type: ignore[arg-type]

    assert result == {"concepts": 1, "aliases": 1}
    assert len(session.statements) == 2

    concept_sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (domain, normalized_text) DO UPDATE" in concept_sql
    assert "RETURNING health_compass.clinical_dictionary_concepts.id" in concept_sql

    alias_compiled = session.statements[1].compile(dialect=postgresql.dialect())
    assert existing_id in alias_compiled.params.values()


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
