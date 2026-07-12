"""HC-017 E1 draft and E2 confirmed laboratory observation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.lab_observation import (
    ConfirmLabObservationRequest,
    CreateLabDraftRequest,
    LabDraftContextResponse,
    LabDraftResponse,
    LabObservationConfirmationPreview,
    LabObservationResponse,
    SetLabDraftSourcesRequest,
    SetLabDraftStatusRequest,
    UpdateLabDraftRequest,
)
from app.services.lab_observation import (
    confirm_lab_observation,
    create_lab_draft,
    get_lab_draft,
    get_lab_draft_context,
    get_lab_observation,
    get_lab_observation_confirmation_preview,
    list_lab_drafts,
    list_lab_observations,
    set_lab_draft_sources,
    set_lab_draft_status,
    update_lab_draft,
)

router = APIRouter(tags=["lab-observations"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get(
    "/profiles/{profile_id}/documents/{document_id}/lab-drafts/context",
    response_model=LabDraftContextResponse,
)
async def get_context(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabDraftContextResponse:
    return await get_lab_draft_context(session, profile_id, document_id)


@router.get(
    "/profiles/{profile_id}/documents/{document_id}/lab-drafts",
    response_model=list[LabDraftResponse],
)
async def get_drafts(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LabDraftResponse]:
    return await list_lab_drafts(session, profile_id, document_id)


@router.get(
    "/profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}",
    response_model=LabDraftResponse,
)
async def get_draft(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    draft_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabDraftResponse:
    return await get_lab_draft(session, profile_id, document_id, draft_id)


@router.post(
    "/profiles/{profile_id}/documents/{document_id}/lab-drafts",
    response_model=LabDraftResponse,
    status_code=201,
)
async def post_draft(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: CreateLabDraftRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabDraftResponse:
    return await create_lab_draft(
        session,
        profile_id,
        document_id,
        payload,
        _request_id(request),
    )


@router.patch(
    "/profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}",
    response_model=LabDraftResponse,
)
async def patch_draft(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    draft_id: uuid.UUID,
    payload: UpdateLabDraftRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabDraftResponse:
    return await update_lab_draft(
        session,
        profile_id,
        document_id,
        draft_id,
        payload,
        _request_id(request),
    )


@router.put(
    "/profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/sources",
    response_model=LabDraftResponse,
)
async def put_sources(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    draft_id: uuid.UUID,
    payload: SetLabDraftSourcesRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabDraftResponse:
    return await set_lab_draft_sources(
        session,
        profile_id,
        document_id,
        draft_id,
        payload,
        _request_id(request),
    )


@router.post(
    "/profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/status",
    response_model=LabDraftResponse,
)
async def post_status(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    draft_id: uuid.UUID,
    payload: SetLabDraftStatusRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabDraftResponse:
    return await set_lab_draft_status(
        session,
        profile_id,
        document_id,
        draft_id,
        payload,
        _request_id(request),
    )


@router.get(
    "/profiles/{profile_id}/documents/{document_id}/lab-drafts/"
    "{draft_id}/confirmation",
    response_model=LabObservationConfirmationPreview,
)
async def get_confirmation_preview(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    draft_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabObservationConfirmationPreview:
    return await get_lab_observation_confirmation_preview(
        session,
        profile_id,
        document_id,
        draft_id,
    )


@router.post(
    "/profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/confirm",
    response_model=LabObservationResponse,
    status_code=201,
)
async def post_confirmation(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    draft_id: uuid.UUID,
    payload: ConfirmLabObservationRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabObservationResponse:
    return await confirm_lab_observation(
        session,
        profile_id,
        document_id,
        draft_id,
        payload,
        _request_id(request),
    )


@router.get(
    "/profiles/{profile_id}/lab-observations",
    response_model=list[LabObservationResponse],
)
async def get_observations(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LabObservationResponse]:
    return await list_lab_observations(session, profile_id)


@router.get(
    "/profiles/{profile_id}/lab-observations/{observation_id}",
    response_model=LabObservationResponse,
)
async def get_observation(
    profile_id: uuid.UUID,
    observation_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabObservationResponse:
    return await get_lab_observation(session, profile_id, observation_id)
