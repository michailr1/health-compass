"""HC-017 D1 OCR status and review-candidate read endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.document_ocr import (
    DocumentOCRCandidateResponse,
    DocumentOCRStatusResponse,
)
from app.services.document_ocr import (
    get_document_ocr_status,
    list_document_ocr_candidates,
)

router = APIRouter(tags=["document-ocr"])


@router.get(
    "/profiles/{profile_id}/documents/{document_id}/ocr/status",
    response_model=DocumentOCRStatusResponse,
)
async def get_ocr_status(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentOCRStatusResponse:
    return await get_document_ocr_status(session, profile_id, document_id)


@router.get(
    "/profiles/{profile_id}/documents/{document_id}/ocr/candidates",
    response_model=list[DocumentOCRCandidateResponse],
)
async def get_ocr_candidates(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentOCRCandidateResponse]:
    candidates = await list_document_ocr_candidates(session, profile_id, document_id)
    return [DocumentOCRCandidateResponse.model_validate(item) for item in candidates]
