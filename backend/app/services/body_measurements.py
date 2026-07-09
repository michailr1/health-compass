"""Service layer for body measurement history."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.body_measurement import BodyMeasurement
from app.models.profile_audit_event import ProfileAuditEvent
from app.models.user import User
from app.schemas.health_profile import BodyMeasurementCreateRequest
from app.services.health_profile import get_visible_profile, require_health_data_consent

WEIGHT_WARNING_MIN_KG = Decimal("20")
WEIGHT_WARNING_MAX_KG = Decimal("400")


async def list_measurements(
    session: AsyncSession,
    profile_id: uuid.UUID,
    *,
    include_voided: bool,
) -> list[BodyMeasurement]:
    await get_visible_profile(session, profile_id)
    statement = select(BodyMeasurement).where(
        BodyMeasurement.profile_id == profile_id,
        BodyMeasurement.measurement_type == "weight",
    )
    if not include_voided:
        statement = statement.where(BodyMeasurement.voided_at.is_(None))
    statement = statement.order_by(
        desc(BodyMeasurement.measured_at),
        desc(BodyMeasurement.created_at),
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def create_measurement(
    session: AsyncSession,
    profile_id: uuid.UUID,
    payload: BodyMeasurementCreateRequest,
    current_user: User,
    request_id: str | None,
) -> BodyMeasurement:
    await get_visible_profile(session, profile_id)
    await require_health_data_consent(session, current_user.id)

    unusual = payload.value < WEIGHT_WARNING_MIN_KG or payload.value > WEIGHT_WARNING_MAX_KG
    if unusual and not payload.confirm_unusual_value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unusual weight value requires explicit confirmation",
        )

    measurement = BodyMeasurement(
        profile_id=profile_id,
        measurement_type="weight",
        value=payload.value,
        unit="kg",
        measured_at=payload.measured_at,
        source_type="manual",
        confirmation_status="confirmed",
        created_by_user_id=current_user.id,
    )
    session.add(measurement)
    await session.flush()
    session.add(
        ProfileAuditEvent(
            profile_id=profile_id,
            actor_user_id=current_user.id,
            entity_type="body_measurement",
            entity_id=measurement.id,
            action="body_measurement.created",
            changed_fields={
                "measurement_type": "weight",
                "source_type": "manual",
            },
            request_id=request_id,
        )
    )
    await session.flush()
    return measurement


async def void_measurement(
    session: AsyncSession,
    profile_id: uuid.UUID,
    measurement_id: uuid.UUID,
    reason: str,
    current_user: User,
    request_id: str | None,
) -> BodyMeasurement:
    await get_visible_profile(session, profile_id)
    result = await session.execute(
        select(BodyMeasurement).where(
            BodyMeasurement.id == measurement_id,
            BodyMeasurement.profile_id == profile_id,
        )
    )
    measurement = result.scalar_one_or_none()
    if measurement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Measurement not found")
    if measurement.voided_at is not None:
        return measurement

    measurement.voided_at = datetime.datetime.now(datetime.UTC)
    measurement.voided_by_user_id = current_user.id
    measurement.void_reason = reason
    session.add(
        ProfileAuditEvent(
            profile_id=profile_id,
            actor_user_id=current_user.id,
            entity_type="body_measurement",
            entity_id=measurement.id,
            action="body_measurement.voided",
            changed_fields={"void_reason": reason},
            request_id=request_id,
        )
    )
    await session.flush()
    return measurement
