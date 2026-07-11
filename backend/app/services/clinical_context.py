"""Business logic for Clinical Context Slice 2."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_context import (
    ProfileAllergy,
    ProfileClinicalSafetyFlag,
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

MODEL_BY_SECTION = {
    "conditions": ProfileCondition,
    "allergies": ProfileAllergy,
    "medications": ProfileMedication,
    "supplements": ProfileSupplement,
    "clinical-safety-flags": ProfileClinicalSafetyFlag,
}
ACTION_PREFIX = {
    "conditions": "condition",
    "allergies": "allergy",
    "medications": "medication",
    "supplements": "supplement",
    "clinical-safety-flags": "clinical_safety_flag",
}


def _serialize(value: Any) -> Any:
    if isinstance(value, (datetime.date, datetime.datetime, Decimal, uuid.UUID)):
        return str(value)
    return value


def _changed_fields(old_values: dict[str, Any], new_values: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for field, new_value in new_values.items():
        old_value = old_values.get(field)
        if old_value != new_value:
            result[field] = {"old": _serialize(old_value), "new": _serialize(new_value)}
    return result


def _audit(
    *,
    profile_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    changed_fields: dict[str, Any],
    request_id: str | None,
) -> ProfileAuditEvent:
    return ProfileAuditEvent(
        profile_id=profile_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changed_fields=changed_fields,
        request_id=request_id,
    )


async def _prepare_write(
    session: AsyncSession,
    profile_id: uuid.UUID,
    current_user: User,
) -> None:
    profile = await get_visible_profile(session, profile_id)
    await require_profile_edit_access(session, profile_id)
    await require_health_data_consent(session, profile.owner_user_id)


# SQLSTATEs raised by health_compass.sync_clinical_dictionary_concept when a
# client submits an impossible canonical coding (migration 0047).
_CONCEPT_ERROR_BY_SQLSTATE = {
    "HC422": "invalid_concept_id",
    "HC404": "unknown_concept",
    "HC409": "concept_domain_mismatch",
}


async def _flush_clinical_write(session: AsyncSession) -> None:
    """Flush, translating dictionary integrity violations into a 422."""
    try:
        await session.flush()
    except DBAPIError as exc:
        original = getattr(exc, "orig", None)
        sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
        detail = _CONCEPT_ERROR_BY_SQLSTATE.get(str(sqlstate or ""))
        if detail is None:
            raise
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        ) from exc


async def list_records(
    session: AsyncSession,
    profile_id: uuid.UUID,
    section: str,
    *,
    include_voided: bool = False,
) -> list[Any]:
    await get_visible_profile(session, profile_id)
    model = MODEL_BY_SECTION[section]
    query = select(model).where(model.profile_id == profile_id)
    if not include_voided:
        query = query.where(model.voided_at.is_(None))
    query = query.order_by(model.updated_at.desc())
    result = await session.execute(query)
    return list(result.scalars())


async def create_record(
    session: AsyncSession,
    profile_id: uuid.UUID,
    section: str,
    payload: BaseModel,
    current_user: User,
    request_id: str | None,
) -> Any:
    await _prepare_write(session, profile_id, current_user)
    model = MODEL_BY_SECTION[section]
    values = payload.model_dump(exclude={"explicit_user_confirmation"})
    values.update(
        id=uuid.uuid4(),
        profile_id=profile_id,
        created_by_user_id=current_user.id,
    )
    record = model(**values)
    session.add(record)
    session.add(
        _audit(
            profile_id=profile_id,
            actor_user_id=current_user.id,
            entity_type=ACTION_PREFIX[section],
            entity_id=record.id,
            action=f"{ACTION_PREFIX[section]}.created",
            changed_fields={
                key: {"old": None, "new": _serialize(value)}
                for key, value in values.items()
                if key not in {"id", "profile_id", "created_by_user_id"}
            },
            request_id=request_id,
        )
    )
    await _flush_clinical_write(session)
    return record


async def update_record(
    session: AsyncSession,
    profile_id: uuid.UUID,
    section: str,
    record_id: uuid.UUID,
    payload: BaseModel,
    current_user: User,
    request_id: str | None,
) -> Any:
    await _prepare_write(session, profile_id, current_user)
    model = MODEL_BY_SECTION[section]
    result = await session.execute(
        select(model).where(
            model.id == record_id,
            model.profile_id == profile_id,
            model.voided_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinical record not found")

    values = payload.model_dump(
        exclude_unset=True,
        exclude={"expected_updated_at", "explicit_user_confirmation"},
    )
    expected_updated_at = getattr(payload, "expected_updated_at", None)
    if expected_updated_at is not None and record.updated_at != expected_updated_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clinical record was updated elsewhere",
        )

    if section == "conditions":
        onset = values.get("onset_date", record.onset_date)
        resolved = values.get("resolved_date", record.resolved_date)
        if onset and resolved and resolved < onset:
            raise HTTPException(status_code=422, detail="resolved_date cannot be before onset_date")
    if section in {"medications", "supplements"}:
        start = values.get("start_date", record.start_date)
        end = values.get("end_date", record.end_date)
        if start and end and end < start:
            raise HTTPException(status_code=422, detail="end_date cannot be before start_date")

    old_values = {field: getattr(record, field) for field in values}
    changed = _changed_fields(old_values, values)
    if not changed:
        return record

    for field, value in values.items():
        setattr(record, field, value)
    record.updated_at = datetime.datetime.now(datetime.UTC)
    session.add(
        _audit(
            profile_id=profile_id,
            actor_user_id=current_user.id,
            entity_type=ACTION_PREFIX[section],
            entity_id=record.id,
            action=f"{ACTION_PREFIX[section]}.updated",
            changed_fields=changed,
            request_id=request_id,
        )
    )
    await _flush_clinical_write(session)
    return record


async def void_record(
    session: AsyncSession,
    profile_id: uuid.UUID,
    section: str,
    record_id: uuid.UUID,
    reason: str,
    current_user: User,
    request_id: str | None,
    expected_updated_at: datetime.datetime | None = None,
) -> Any:
    await _prepare_write(session, profile_id, current_user)
    model = MODEL_BY_SECTION[section]
    result = await session.execute(
        select(model).where(model.id == record_id, model.profile_id == profile_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clinical record not found")
    if record.voided_at is not None:
        return record
    if expected_updated_at is not None and record.updated_at != expected_updated_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clinical record was updated elsewhere",
        )

    now = datetime.datetime.now(datetime.UTC)
    record.voided_at = now
    record.voided_by_user_id = current_user.id
    record.void_reason = reason
    record.updated_at = now
    session.add(
        _audit(
            profile_id=profile_id,
            actor_user_id=current_user.id,
            entity_type=ACTION_PREFIX[section],
            entity_id=record.id,
            action=f"{ACTION_PREFIX[section]}.voided",
            changed_fields={
                "voided_at": {"old": None, "new": str(now)},
                "void_reason": {"old": None, "new": reason},
            },
            request_id=request_id,
        )
    )
    await session.flush()
    return record


# The legacy summary/review implementations (``get_summary``/``review_section``
# with the ``reviewed``/``confirmed_empty``/``total_count`` response shape) were
# removed in HC-015 Slice A. ``app.services.clinical_review`` is the only owner
# of summary and review-state logic.
