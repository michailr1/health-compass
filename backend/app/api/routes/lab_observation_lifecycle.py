"""HC-017 E3 lifecycle endpoints for confirmed laboratory observations."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.lab_observation import (
    EraseLabObservationRequest,
    EraseLabObservationResponse,
    LabObservationResponse,
    RequestDocumentLabErasureRequest,
    RequestDocumentLabErasureResponse,
    VoidLabObservationRequest,
)
from app.schemas.lab_observation_lifecycle import (
    CorrectLabObservationLifecycleRequest,
)
from app.services.lab_observation_lifecycle import (
    correct_lab_observation,
    erase_lab_observation,
    list_lab_observation_history,
    request_document_lab_erasure,
    void_lab_observation,
)

router = APIRouter(tags=["lab-observations"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get(
    "/profiles/{profile_id}/labs/observations/history",
    response_model=list[LabObservationResponse],
)
async def get_observation_history(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LabObservationResponse]:
    return await list_lab_observation_history(session, profile_id)


@router.post(
    "/profiles/{profile_id}/labs/observations/{observation_id}/correct",
    response_model=LabObservationResponse,
)
async def post_correction(
    profile_id: uuid.UUID,
    observation_id: uuid.UUID,
    payload: CorrectLabObservationLifecycleRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabObservationResponse:
    return await correct_lab_observation(
        session,
        profile_id,
        observation_id,
        payload,
        _request_id(request),
    )


@router.post(
    "/profiles/{profile_id}/labs/observations/{observation_id}/void",
    response_model=LabObservationResponse,
)
async def post_void(
    profile_id: uuid.UUID,
    observation_id: uuid.UUID,
    payload: VoidLabObservationRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabObservationResponse:
    return await void_lab_observation(
        session,
        profile_id,
        observation_id,
        payload,
        _request_id(request),
    )


@router.delete(
    "/profiles/{profile_id}/labs/observations/{observation_id}",
    response_model=EraseLabObservationResponse,
)
async def delete_observation(
    profile_id: uuid.UUID,
    observation_id: uuid.UUID,
    payload: EraseLabObservationRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EraseLabObservationResponse:
    return await erase_lab_observation(
        session,
        profile_id,
        observation_id,
        payload,
        _request_id(request),
    )


@router.delete(
    "/profiles/{profile_id}/documents/{document_id}/lab-data",
    response_model=RequestDocumentLabErasureResponse,
)
async def delete_document_lab_data(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: RequestDocumentLabErasureRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RequestDocumentLabErasureResponse:
    return await request_document_lab_erasure(
        session,
        profile_id,
        document_id,
        payload,
        _request_id(request),
    )
