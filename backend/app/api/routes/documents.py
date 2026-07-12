"""HC-017 Slice B document metadata and quarantine-upload endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.document import DocumentIntakeCapabilities, DocumentResponse
from app.services.documents import (
    create_document,
    document_capabilities,
    get_document,
    list_documents,
)

router = APIRouter(tags=["documents"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get(
    "/profiles/{profile_id}/document-intake/capabilities",
    response_model=DocumentIntakeCapabilities,
)
async def get_document_intake_capabilities(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentIntakeCapabilities:
    return await document_capabilities(session, profile_id)


@router.post(
    "/profiles/{profile_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    profile_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    document = await create_document(
        session,
        profile_id,
        file,
        current_user,
        _request_id(request),
    )
    return DocumentResponse.model_validate(document)


@router.get(
    "/profiles/{profile_id}/documents",
    response_model=list[DocumentResponse],
)
async def get_documents(
    profile_id: uuid.UUID,
    include_voided: bool = Query(default=False),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentResponse]:
    documents = await list_documents(
        session,
        profile_id,
        include_voided=include_voided,
    )
    return [DocumentResponse.model_validate(item) for item in documents]


@router.get(
    "/profiles/{profile_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
async def get_document_detail(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    document = await get_document(session, profile_id, document_id)
    return DocumentResponse.model_validate(document)
