"""Suggestion ranking for curated and personal Clinical Context dictionaries."""

from __future__ import annotations

import re
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
    return re.sub(r"\s+", " ", value.strip().casefold())


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
                 WHEN lower({display_column}) = :normalized THEN 0
                 WHEN lower({display_column}) LIKE :prefix THEN 1
                 ELSE 2
               END AS match_rank,
               max(updated_at) AS last_used_at
        FROM health_compass.{table_name}
        WHERE profile_id = :profile_id
          AND voided_at IS NULL
          AND lower({display_column}) LIKE :contains
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

    global_sql = text(
        """
        SELECT c.id,
               c.display_name AS display_text,
               c.qualifier,
               'global'::text AS source,
               c.id AS canonical_concept_id,
               COALESCE(a.alias_text, c.display_name) AS matched_text,
               1 AS source_rank,
               CASE
                 WHEN c.normalized_text = :normalized THEN 0
                 WHEN c.normalized_text LIKE :prefix THEN 1
                 WHEN a.normalized_text = :normalized THEN 1
                 WHEN a.normalized_text LIKE :prefix THEN 2
                 ELSE 3
               END AS match_rank,
               NULL::timestamptz AS last_used_at
        FROM health_compass.clinical_dictionary_concepts c
        LEFT JOIN health_compass.clinical_dictionary_aliases a ON a.concept_id = c.id
        WHERE c.domain = :domain
          AND c.is_active
          AND (
            c.normalized_text LIKE :contains
            OR a.normalized_text LIKE :contains
          )
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
            row["source_rank"],
            row["match_rank"],
            -(row["last_used_at"].timestamp() if row["last_used_at"] else 0),
            row["display_text"].casefold(),
        ),
    )
    items: list[dict[str, Any]] = []
    for row in ranked:
        key = (row["display_text"].casefold(), str(row["canonical_concept_id"]) if row["canonical_concept_id"] else None)
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
