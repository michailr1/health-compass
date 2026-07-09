"""Basic Health Profile, measurements, and consent endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.health_profile import (
    BodyMeasurementCreateRequest,
    BodyMeasurementResponse,
    ConsentAcceptRequest,
    ConsentResponse,
    MeasurementVoidRequest,
    ProfilePatchRequest,
)
from app.schemas.identity import ProfileResponse
from app.services.body_measurements import (
    create_measurement,
    list_measurements,
    void_measurement,
)
from app.services.consents import accept_consent, get_latest_consent, revoke_consent
from app.services.health_profile import build_readiness, patch_profile

router = APIRouter(tags=["health-profile"])


@router.patch("/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: uuid.UUID,
    payload: ProfilePatchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    profile = await patch_profile(
        session,
        profile_id,
        payload,
        current_user,
        getattr(request.state, "request_id", None),
    )
    readiness = await build_readiness(session, profile)
    return {
        "id": profile.id,
        "workspace_id": profile.workspace_id,
        "owner_user_id": profile.owner_user_id,
        "display_name": profile.display_name,
        "date_of_birth": profile.date_of_birth,
        "sex": profile.sex,
        "height_cm": profile.height_cm,
        "timezone": profile.timezone,
        "readiness": readiness,
    }


@router.get(
    "/profiles/{profile_id}/body-measurements",
    response_model=list[BodyMeasurementResponse],
)
async def get_body_measurements(
    profile_id: uuid.UUID,
    include_voided: bool = Query(default=False),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    return await list_measurements(session, profile_id, include_voided=include_voided)


@router.post(
    "/profiles/{profile_id}/body-measurements",
    response_model=BodyMeasurementResponse,
    status_code=201,
)
async def add_body_measurement(
    profile_id: uuid.UUID,
    payload: BodyMeasurementCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_measurement(
        session,
        profile_id,
        payload,
        current_user,
        getattr(request.state, "request_id", None),
    )


@router.post(
    "/profiles/{profile_id}/body-measurements/{measurement_id}/void",
    response_model=BodyMeasurementResponse,
)
async def void_body_measurement(
    profile_id: uuid.UUID,
    measurement_id: uuid.UUID,
    payload: MeasurementVoidRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await void_measurement(
        session,
        profile_id,
        measurement_id,
        payload.reason,
        current_user,
        getattr(request.state, "request_id", None),
    )


@router.get(
    "/consents/health-data-processing",
    response_model=ConsentResponse,
)
async def get_health_data_consent(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConsentResponse:
    consent = await get_latest_consent(session, current_user.id)
    if consent is None:
        return ConsentResponse(active=False)
    return ConsentResponse(
        id=consent.id,
        document_version=consent.document_version,
        accepted_at=consent.accepted_at,
        revoked_at=consent.revoked_at,
        active=consent.revoked_at is None,
    )


@router.post(
    "/consents/health-data-processing/accept",
    response_model=ConsentResponse,
)
async def accept_health_data_consent(
    payload: ConsentAcceptRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConsentResponse:
    consent = await accept_consent(session, current_user, payload.document_version)
    return ConsentResponse(
        id=consent.id,
        document_version=consent.document_version,
        accepted_at=consent.accepted_at,
        revoked_at=consent.revoked_at,
        active=True,
    )


@router.post(
    "/consents/health-data-processing/revoke",
    response_model=ConsentResponse,
)
async def revoke_health_data_consent(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConsentResponse:
    consent = await revoke_consent(session, current_user)
    if consent is None:
        return ConsentResponse(active=False)
    return ConsentResponse(
        id=consent.id,
        document_version=consent.document_version,
        accepted_at=consent.accepted_at,
        revoked_at=consent.revoked_at,
        active=False,
    )
