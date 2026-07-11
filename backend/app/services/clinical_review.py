"""Review-state lifecycle for Clinical Context sections."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_context import (
    ProfileAllergy,
    ProfileClinicalReview,
    ProfileCondition,
    ProfileMedication,
    ProfileSupplement,
)
from app.models.profile_audit_event import ProfileAuditEvent
from app.models.user import User
from app.services.health_profile import (
    get_visible_profile,
    require_health_data_consent,
    require_profile_edit_access,
)

SECTIONS = ("conditions", "allergies", "medications", "supplements")
MODEL_BY_SECTION = {
    "conditions": ProfileCondition,
    "allergies": ProfileAllergy,
    "medications": ProfileMedication,
    "supplements": ProfileSupplement,
}
ACTIVE_FIELD = {
    "conditions": ("clinical_status", "active"),
    "allergies": ("clinical_status", "active"),
    "medications": ("status", "active"),
    "supplements": ("status", "active"),
}
STORED_STATES = {"unknown", "deferred", "confirmed_none"}
ACTION_BY_STATE = {
    "unknown": "clinical_section.review_unknown",
    "deferred": "clinical_section.review_deferred",
    "confirmed_none": "clinical_section.confirmed_none",
}


async def _prepare_write(
    session: AsyncSession,
    profile_id: uuid.UUID,
    current_user: User,
) -> None:
    profile = await get_visible_profile(session, profile_id)
    await require_profile_edit_access(session, profile_id)
    await require_health_data_consent(session, profile.owner_user_id)


async def lock_section_review(
    session: AsyncSession,
    profile_id: uuid.UUID,
    section: str,
) -> None:
    """Serialize review-state transitions against record creation.

    ``confirmed_none`` must never be persisted while a concurrent transaction
    inserts the section's first record (CR-10). Both paths take the same
    transaction-scoped advisory lock, so the emptiness check and the review
    write happen atomically relative to record creation.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 8615))"),
        {"key": f"clinical-review:{profile_id}:{section}"},
    )


async def _record_counts(
    session: AsyncSession,
    profile_id: uuid.UUID,
    section: str,
) -> tuple[int, int]:
    model = MODEL_BY_SECTION[section]
    active_field, active_value = ACTIVE_FIELD[section]
    active_count = int(
        await session.scalar(
            select(func.count(model.id)).where(
                model.profile_id == profile_id,
                model.voided_at.is_(None),
                getattr(model, active_field) == active_value,
            )
        )
        or 0
    )
    history_count = int(
        await session.scalar(
            select(func.count(model.id)).where(model.profile_id == profile_id)
        )
        or 0
    )
    return active_count, history_count


async def clear_incompatible_review_state(
    session: AsyncSession,
    *,
    profile_id: uuid.UUID,
    section: str,
    actor_user_id: uuid.UUID,
    request_id: str | None,
) -> None:
    """Clear deferred/confirmed-none when the first clinical fact is created."""
    result = await session.execute(
        select(ProfileClinicalReview).where(
            ProfileClinicalReview.profile_id == profile_id,
            ProfileClinicalReview.section == section,
        )
    )
    review = result.scalar_one_or_none()
    if review is None or review.review_state == "unknown":
        return

    old_state = review.review_state
    now = datetime.datetime.now(datetime.UTC)
    review.review_state = "unknown"
    review.reviewed_at = now
    review.reviewed_by_user_id = actor_user_id
    review.updated_at = now
    session.add(
        ProfileAuditEvent(
            profile_id=profile_id,
            actor_user_id=actor_user_id,
            entity_type="clinical_context_review",
            entity_id=review.id,
            action="clinical_section.confirmed_none_cleared",
            changed_fields={
                "section": {"old": section, "new": section},
                "review_state": {"old": old_state, "new": "unknown"},
            },
            request_id=request_id,
        )
    )


async def review_section(
    session: AsyncSession,
    profile_id: uuid.UUID,
    section: str,
    review_state: str,
    expected_updated_at: datetime.datetime | None,
    current_user: User,
    request_id: str | None,
) -> ProfileClinicalReview:
    if section not in SECTIONS:
        raise HTTPException(status_code=422, detail="Unknown clinical section")
    if review_state not in STORED_STATES:
        raise HTTPException(status_code=422, detail="Unknown clinical review state")

    await _prepare_write(session, profile_id, current_user)
    await lock_section_review(session, profile_id, section)
    _, history_count = await _record_counts(session, profile_id, section)
    if review_state == "confirmed_none" and history_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="section_has_entries",
        )

    result = await session.execute(
        select(ProfileClinicalReview).where(
            ProfileClinicalReview.profile_id == profile_id,
            ProfileClinicalReview.section == section,
        )
    )
    review = result.scalar_one_or_none()
    now = datetime.datetime.now(datetime.UTC)

    if review is None:
        if expected_updated_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="review_state_conflict")
        review = ProfileClinicalReview(
            id=uuid.uuid4(),
            profile_id=profile_id,
            section=section,
            review_state=review_state,
            reviewed_at=now,
            reviewed_by_user_id=current_user.id,
            updated_at=now,
        )
        session.add(review)
        old_state = None
    else:
        if expected_updated_at is not None and review.updated_at != expected_updated_at:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="review_state_conflict")
        old_state = review.review_state
        review.review_state = review_state
        review.reviewed_at = now
        review.reviewed_by_user_id = current_user.id
        review.updated_at = now

    session.add(
        ProfileAuditEvent(
            profile_id=profile_id,
            actor_user_id=current_user.id,
            entity_type="clinical_context_review",
            entity_id=review.id,
            action=ACTION_BY_STATE[review_state],
            changed_fields={
                "section": {"old": section if old_state is not None else None, "new": section},
                "review_state": {"old": old_state, "new": review_state},
            },
            request_id=request_id,
        )
    )
    await session.flush()
    return review


async def get_summary(session: AsyncSession, profile_id: uuid.UUID) -> dict[str, Any]:
    await get_visible_profile(session, profile_id)
    result = await session.execute(
        select(ProfileClinicalReview).where(ProfileClinicalReview.profile_id == profile_id)
    )
    reviews = {row.section: row for row in result.scalars()}

    sections: dict[str, Any] = {}
    for section in SECTIONS:
        active_count, history_count = await _record_counts(session, profile_id, section)
        review = reviews.get(section)
        review_state = review.review_state if review else "unknown"
        effective_state = "has_entries" if history_count > 0 else review_state
        sections[section] = {
            "review_state": review_state,
            "effective_state": effective_state,
            "reviewed_at": review.reviewed_at if review else None,
            "updated_at": review.updated_at if review else None,
            "active_count": active_count,
            "history_count": history_count,
        }
    return {"profile_id": profile_id, "sections": sections}
