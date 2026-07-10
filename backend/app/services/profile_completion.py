"""Derived profile-questionnaire completion state."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.clinical_review import get_summary as get_clinical_summary
from app.services.health_profile import build_readiness, get_visible_profile

SECTION_TITLES = {
    "basic": "Основные сведения",
    "conditions": "Состояния и симптомы",
    "allergies": "Аллергии и непереносимости",
    "medications": "Лекарства",
    "supplements": "Добавки",
}


async def get_profile_completion(
    session: AsyncSession,
    profile_id: uuid.UUID,
) -> dict:
    profile = await get_visible_profile(session, profile_id)
    readiness = await build_readiness(session, profile)
    clinical = await get_clinical_summary(session, profile_id)

    basic_missing = list(readiness.missing_fields)
    sections: list[dict] = [
        {
            "key": "basic",
            "title": SECTION_TITLES["basic"],
            "state": "complete" if not basic_missing else "incomplete",
            "missing_fields": basic_missing,
            "next_action": "#basic-profile",
        }
    ]

    for key in ("conditions", "allergies", "medications", "supplements"):
        section = clinical["sections"][key]
        effective_state = section["effective_state"]
        if effective_state in {"has_entries", "confirmed_none"}:
            state = "complete"
        elif effective_state == "deferred":
            state = "deferred"
        else:
            state = "incomplete"
        sections.append(
            {
                "key": key,
                "title": SECTION_TITLES[key],
                "state": state,
                "missing_fields": [] if state != "incomplete" else ["review_required"],
                "next_action": f"#clinical-{key}",
            }
        )

    completed_sections = sum(1 for item in sections if item["state"] == "complete")
    next_section = next(
        (item["key"] for item in sections if item["state"] == "incomplete"),
        None,
    )
    return {
        "completed_sections": completed_sections,
        "total_sections": len(sections),
        "progress_percent": round(completed_sections / len(sections) * 100),
        "next_section": next_section,
        "sections": sections,
    }
