"""Validated, idempotent seed loading for Clinical Dictionaries v2."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_dictionary import ClinicalDictionaryAlias, ClinicalDictionaryConcept
from app.services.clinical_dictionary import normalize_search_text

ALLOWED_DOMAINS = {
    "condition_or_symptom",
    "allergy_or_intolerance",
    "medication",
    "supplement",
}
SEED_NAMESPACE = uuid.UUID("bb06b0b4-43b9-43ff-a4e3-2c39f9d6498e")


@dataclass(frozen=True)
class SeedAlias:
    text: str
    language: str
    kind: str


@dataclass(frozen=True)
class SeedConcept:
    domain: str
    display_name: str
    source_system: str
    source_code: str | None
    qualifier: str | None
    locale: str
    country: str
    aliases: tuple[SeedAlias, ...]


@dataclass(frozen=True)
class SeedManifest:
    version: str
    source_label: str
    concepts: tuple[SeedConcept, ...]


def _required(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _required(value, field_name)


def load_seed_manifest(path: str | Path) -> SeedManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("seed manifest root must be an object")

    version = _required(payload.get("version"), "version")
    source_label = _required(payload.get("source_label"), "source_label")
    raw_concepts = payload.get("concepts")
    if not isinstance(raw_concepts, list) or not raw_concepts:
        raise ValueError("concepts must be a non-empty array")

    concepts: list[SeedConcept] = []
    seen_concepts: set[tuple[str, str]] = set()
    for index, raw in enumerate(raw_concepts):
        if not isinstance(raw, dict):
            raise ValueError(f"concepts[{index}] must be an object")

        domain = _required(raw.get("domain"), f"concepts[{index}].domain")
        if domain not in ALLOWED_DOMAINS:
            raise ValueError(f"unsupported domain: {domain}")

        display_name = _required(raw.get("display_name"), f"concepts[{index}].display_name")
        locale = _required(raw.get("locale"), f"concepts[{index}].locale")
        country = _required(raw.get("country"), f"concepts[{index}].country")
        if locale != "ru-RU":
            raise ValueError("primary display locale must be ru-RU")
        if country not in {"RU", "EAEU", "INTL"}:
            raise ValueError(f"unsupported country scope: {country}")

        concept_key = (domain, normalize_search_text(display_name))
        if concept_key in seen_concepts:
            raise ValueError(f"duplicate concept: {domain}/{display_name}")
        seen_concepts.add(concept_key)

        raw_aliases = raw.get("aliases", [])
        if not isinstance(raw_aliases, list):
            raise ValueError(f"concepts[{index}].aliases must be an array")

        aliases: list[SeedAlias] = []
        seen_aliases: set[str] = {normalize_search_text(display_name)}
        for alias_index, raw_alias in enumerate(raw_aliases):
            if not isinstance(raw_alias, dict):
                raise ValueError(f"concepts[{index}].aliases[{alias_index}] must be an object")
            alias_text = _required(raw_alias.get("text"), f"concepts[{index}].aliases[{alias_index}].text")
            alias_key = normalize_search_text(alias_text)
            if alias_key in seen_aliases:
                continue
            seen_aliases.add(alias_key)
            aliases.append(
                SeedAlias(
                    text=alias_text,
                    language=_required(
                        raw_alias.get("language"),
                        f"concepts[{index}].aliases[{alias_index}].language",
                    ),
                    kind=_required(raw_alias.get("kind"), f"concepts[{index}].aliases[{alias_index}].kind"),
                )
            )

        concepts.append(
            SeedConcept(
                domain=domain,
                display_name=display_name,
                source_system=_required(raw.get("source_system"), f"concepts[{index}].source_system"),
                source_code=_optional(raw.get("source_code"), f"concepts[{index}].source_code"),
                qualifier=_optional(raw.get("qualifier"), f"concepts[{index}].qualifier"),
                locale=locale,
                country=country,
                aliases=tuple(aliases),
            )
        )

    return SeedManifest(version=version, source_label=source_label, concepts=tuple(concepts))


def concept_uuid(concept: SeedConcept) -> uuid.UUID:
    identity = "|".join(
        [
            concept.domain,
            concept.source_system,
            concept.source_code or "",
            normalize_search_text(concept.display_name),
        ]
    )
    return uuid.uuid5(SEED_NAMESPACE, identity)


def alias_uuid(concept_id: uuid.UUID, alias: SeedAlias) -> uuid.UUID:
    identity = f"{concept_id}|{alias.language}|{alias.kind}|{normalize_search_text(alias.text)}"
    return uuid.uuid5(SEED_NAMESPACE, identity)


async def upsert_seed_manifest(session: AsyncSession, manifest: SeedManifest) -> dict[str, int]:
    concept_count = 0
    alias_count = 0

    for concept in manifest.concepts:
        normalized_text = normalize_search_text(concept.display_name)
        concept_insert = insert(ClinicalDictionaryConcept).values(
            {
                "id": concept_uuid(concept),
                "domain": concept.domain,
                "display_name": concept.display_name,
                "normalized_text": normalized_text,
                "qualifier": concept.qualifier,
                "source_system": concept.source_system,
                "source_code": concept.source_code,
                "is_active": True,
            }
        )
        concept_result = await session.execute(
            concept_insert.on_conflict_do_update(
                index_elements=[
                    ClinicalDictionaryConcept.domain,
                    ClinicalDictionaryConcept.normalized_text,
                ],
                set_={
                    "display_name": concept_insert.excluded.display_name,
                    "qualifier": concept_insert.excluded.qualifier,
                    "source_system": concept_insert.excluded.source_system,
                    "source_code": concept_insert.excluded.source_code,
                    "is_active": True,
                },
            ).returning(ClinicalDictionaryConcept.id)
        )
        actual_concept_id = concept_result.scalar_one()
        concept_count += 1

        for alias in concept.aliases:
            alias_insert = insert(ClinicalDictionaryAlias).values(
                {
                    "id": alias_uuid(actual_concept_id, alias),
                    "concept_id": actual_concept_id,
                    "alias_text": alias.text,
                    "normalized_text": normalize_search_text(alias.text),
                }
            )
            await session.execute(
                alias_insert.on_conflict_do_update(
                    index_elements=[ClinicalDictionaryAlias.id],
                    set_={
                        "concept_id": actual_concept_id,
                        "alias_text": alias_insert.excluded.alias_text,
                        "normalized_text": alias_insert.excluded.normalized_text,
                    },
                )
            )
            alias_count += 1

    return {"concepts": concept_count, "aliases": alias_count}
