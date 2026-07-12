"""HC-017 OCR status, candidates and human-review endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.document_ocr import (
    DocumentOCRCandidateResponse,
    DocumentOCRCandidateReviewRequest,
    DocumentOCRFinalizeRequest,
    DocumentOCRPatientDecisionRequest,
    DocumentOCRReviewResponse,
    DocumentOCRStatusResponse,
)
from app.services.document_ocr import (
    finalize_document_ocr_review,
    get_document_ocr_review,
    get_document_ocr_status,
    list_document_ocr_candidates,
    review_document_ocr_candidate,
    set_document_ocr_patient_decision,
)

router = APIRouter(tags=["document-ocr"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


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


@router.get(
    "/profiles/{profile_id}/documents/{document_id}/ocr/review",
    response_model=DocumentOCRReviewResponse,
)
async def get_ocr_review(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentOCRReviewResponse:
    return await get_document_ocr_review(session, profile_id, document_id)


@router.patch(
    "/profiles/{profile_id}/documents/{document_id}/ocr/candidates/{candidate_id}",
    response_model=DocumentOCRReviewResponse,
)
async def patch_ocr_candidate(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    candidate_id: uuid.UUID,
    payload: DocumentOCRCandidateReviewRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentOCRReviewResponse:
    return await review_document_ocr_candidate(
        session,
        profile_id,
        document_id,
        candidate_id,
        payload,
        _request_id(request),
    )


@router.put(
    "/profiles/{profile_id}/documents/{document_id}/ocr/patient-match",
    response_model=DocumentOCRReviewResponse,
)
async def put_ocr_patient_match(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentOCRPatientDecisionRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentOCRReviewResponse:
    return await set_document_ocr_patient_decision(
        session,
        profile_id,
        document_id,
        payload,
        _request_id(request),
    )


@router.post(
    "/profiles/{profile_id}/documents/{document_id}/ocr/finalize",
    response_model=DocumentOCRReviewResponse,
)
async def post_ocr_finalize(
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentOCRFinalizeRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentOCRReviewResponse:
    return await finalize_document_ocr_review(
        session,
        profile_id,
        document_id,
        payload,
        _request_id(request),
    )
