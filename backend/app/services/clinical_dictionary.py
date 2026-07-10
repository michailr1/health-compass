"""Suggestion ranking for curated and personal Clinical Context dictionaries."""

from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.health_profile import get_visible_profile

SECTION_CONFIG = {
    "conditions": ("condition_or_symptom", "profile_conditions", "display_name"),
    "allergies": ("allergy_or_intolerance", "profile_allergies", "substance_name"),
    "medications": ("medication", "profile_medications", "display_name"),
    "supplements": ("supplement", "profile_supplements", "display_name"),
}


def normalize_search_text(value: str) -> str:
    """Normalize user-facing medical terms without changing their stored value."""
    compatible = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    characters = [
        character if character.isalnum() else " "
        for character in compatible
    ]
    return re.sub(r"\s+", " ", "".join(characters)).strip()


def _sql_normalized(column: str) -> str:
    """Return the PostgreSQL equivalent of ``normalize_search_text`` for search."""
    return (
        "trim(regexp_replace("
        f"replace(lower({column}), 'ё', 'е'), "
        "'[^[:alnum:]]+', ' ', 'g'))"
    )


async def get_suggestions(
    session: AsyncSession,
    *,
    profile_id: uuid.UUID,
    section: str,
    query: str,
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    await get_visible_profile(session, profile_id)
    domain, table_name, display_column = SECTION_CONFIG[section]
    normalized = normalize_search_text(query)
    if not normalized:
        return {"items": []}

    personal_normalized = _sql_normalized(display_column)
    personal_sql = text(
        f"""
        SELECT NULL::uuid AS id,
               {display_column} AS display_text,
               NULL::text AS qualifier,
               'personal'::text AS source,
               canonical_concept_id,
               {display_column} AS matched_text,
               0 AS source_rank,
               CASE
                 WHEN {personal_normalized} = :normalized THEN 0
                 WHEN {personal_normalized} LIKE :prefix THEN 1
                 ELSE 2
               END AS match_rank,
               max(updated_at) AS last_used_at
        FROM health_compass.{table_name}
        WHERE profile_id = :profile_id
          AND voided_at IS NULL
          AND {personal_normalized} LIKE :contains
        GROUP BY {display_column}, canonical_concept_id
        """
    )
    personal = (
        await session.execute(
            personal_sql,
            {
                "profile_id": profile_id,
                "normalized": normalized,
                "prefix": f"{normalized}%",
                "contains": f"%{normalized}%",
            },
        )
    ).mappings().all()

    concept_normalized = _sql_normalized("c.display_name")
    alias_normalized = _sql_normalized("a.alias_text")
    global_sql = text(
        f"""
        SELECT c.id,
               c.display_name AS display_text,
               c.qualifier,
               'global'::text AS source,
               c.id AS canonical_concept_id,
               c.display_name AS matched_text,
               2 AS source_rank,
               CASE
                 WHEN {concept_normalized} = :normalized THEN 0
                 WHEN {concept_normalized} LIKE :prefix THEN 1
                 ELSE 2
               END AS match_rank,
               NULL::timestamptz AS last_used_at
        FROM health_compass.clinical_dictionary_concepts c
        WHERE c.domain = :domain
          AND c.is_active
          AND {concept_normalized} LIKE :contains

        UNION ALL

        SELECT c.id,
               c.display_name AS display_text,
               c.qualifier,
               'global'::text AS source,
               c.id AS canonical_concept_id,
               a.alias_text AS matched_text,
               1 AS source_rank,
               CASE
                 WHEN {alias_normalized} = :normalized THEN 0
                 WHEN {alias_normalized} LIKE :prefix THEN 1
                 ELSE 2
               END AS match_rank,
               NULL::timestamptz AS last_used_at
        FROM health_compass.clinical_dictionary_concepts c
        JOIN health_compass.clinical_dictionary_aliases a ON a.concept_id = c.id
        WHERE c.domain = :domain
          AND c.is_active
          AND {alias_normalized} LIKE :contains
        """
    )
    global_rows = (
        await session.execute(
            global_sql,
            {
                "domain": domain,
                "normalized": normalized,
                "prefix": f"{normalized}%",
                "contains": f"%{normalized}%",
            },
        )
    ).mappings().all()

    seen: set[tuple[str, str | None]] = set()
    ranked = sorted(
        [*personal, *global_rows],
        key=lambda row: (
            row["match_rank"],
            row["source_rank"],
            -(row["last_used_at"].timestamp() if row["last_used_at"] else 0),
            row["display_text"].casefold(),
        ),
    )
    items: list[dict[str, Any]] = []
    for row in ranked:
        key = (
            normalize_search_text(row["display_text"]),
            str(row["canonical_concept_id"]) if row["canonical_concept_id"] else None,
        )
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "id": row["id"],
                "display_text": row["display_text"],
                "qualifier": row["qualifier"],
                "source": row["source"],
                "canonical_concept_id": row["canonical_concept_id"],
                "matched_text": row["matched_text"],
            }
        )
        if len(items) >= limit:
            break
    return {"items": items}
