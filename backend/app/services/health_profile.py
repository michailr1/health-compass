"""Service layer for Basic Health Profile operations."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.body_measurement import BodyMeasurement
from app.models.consent import UserConsent
from app.models.profile import HealthProfile
from app.models.profile_audit_event import ProfileAuditEvent
from app.models.user import User
from app.schemas.health_profile import ProfilePatchRequest, ProfileReadiness

CONSENT_TYPE = "health_data_processing"
MEDICAL_FIELDS = {"date_of_birth", "sex", "height_cm", "timezone"}


def _serialize(value: Any) -> Any:
    if isinstance(value, (datetime.date, datetime.datetime, Decimal, uuid.UUID)):
        return str(value)
    return value


async def get_visible_profile(
    session: AsyncSession,
    profile_id: uuid.UUID,
) -> HealthProfile:
    result = await session.execute(select(HealthProfile).where(HealthProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


async def can_edit_profile(
    session: AsyncSession,
    profile_id: uuid.UUID,
) -> bool:
    result = await session.execute(
        text("SELECT health_compass.app_can_edit_profile(:profile_id)"),
        {"profile_id": profile_id},
    )
    return bool(result.scalar_one())


async def require_profile_edit_access(
    session: AsyncSession,
    profile_id: uuid.UUID,
) -> None:
    if not await can_edit_profile(session, profile_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")


async def has_active_health_data_consent(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> bool:
    result = await session.execute(
        select(UserConsent.id).where(
            UserConsent.user_id == user_id,
            UserConsent.consent_type == CONSENT_TYPE,
            UserConsent.revoked_at.is_(None),
        )
    )
    return result.scalar_one_or_none() is not None


async def require_health_data_consent(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> None:
    if not await has_active_health_data_consent(session, user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Health data processing consent is required",
        )


async def build_readiness(
    session: AsyncSession,
    profile: HealthProfile,
) -> ProfileReadiness:
    latest_weight = await session.execute(
        select(BodyMeasurement.id)
        .where(
            BodyMeasurement.profile_id == profile.id,
            BodyMeasurement.measurement_type == "weight",
            BodyMeasurement.voided_at.is_(None),
        )
        .order_by(desc(BodyMeasurement.measured_at))
        .limit(1)
    )
    has_weight = latest_weight.scalar_one_or_none() is not None

    age_references = profile.date_of_birth is not None
    sex_specific_references = profile.sex in {"male", "female"}
    bmi = profile.height_cm is not None and has_weight
    local_time_context = profile.timezone is not None

    missing: list[str] = []
    if not age_references:
        missing.append("date_of_birth")
    if not sex_specific_references:
        missing.append("sex")
    if profile.height_cm is None:
        missing.append("height_cm")
    if not has_weight:
        missing.append("weight")
    if not local_time_context:
        missing.append("timezone")

    return ProfileReadiness(
        age_references=age_references,
        sex_specific_references=sex_specific_references,
        bmi=bmi,
        local_time_context=local_time_context,
        missing_fields=missing,
    )


async def patch_profile(
    session: AsyncSession,
    profile_id: uuid.UUID,
    payload: ProfilePatchRequest,
    current_user: User,
    request_id: str | None,
) -> HealthProfile:
    profile = await get_visible_profile(session, profile_id)
    await require_profile_edit_access(session, profile_id)

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return profile
    if "display_name" in changes and changes["display_name"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="display_name cannot be null",
        )

    if MEDICAL_FIELDS.intersection(changes):
        await require_health_data_consent(session, current_user.id)

    changed_fields: dict[str, dict[str, Any]] = {}
    for field_name, new_value in changes.items():
        old_value = getattr(profile, field_name)
        if old_value == new_value:
            continue
        setattr(profile, field_name, new_value)
        changed_fields[field_name] = {
            "old": _serialize(old_value),
            "new": _serialize(new_value),
        }

    if not changed_fields:
        return profile

    profile.updated_at = datetime.datetime.now(datetime.UTC)
    session.add(
        ProfileAuditEvent(
            profile_id=profile.id,
            actor_user_id=current_user.id,
            entity_type="health_profile",
            entity_id=profile.id,
            action="profile.updated",
            changed_fields=changed_fields,
            request_id=request_id,
        )
    )
    await session.flush()
    return profile
