"""HC-017 E1 source-preserving laboratory draft endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.lab_observation import (
    CreateLabDraftRequest,
    LabDraftContextResponse,
    LabDraftResponse,
    SetLabDraftSourcesRequest,
    SetLabDraftStatusRequest,
    UpdateLabDraftRequest,
)
from app.services.lab_observation import (
    create_lab_draft,
    get_lab_draft,
    get_lab_draft_context,
    list_lab_drafts,
    set_lab_draft_sources,
    set_lab_draft_status,
    update_lab_draft,
)

router = APIRouter(tags=["lab-drafts"])


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
