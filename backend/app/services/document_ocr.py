"""Service layer for HC-017 D1 OCR status and candidate reads."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_ocr import DocumentOCRCandidate, DocumentOCRRun
from app.schemas.document_ocr import DocumentOCRStatusResponse
from app.services.documents import get_document
from app.services.health_profile import require_profile_edit_access


async def get_document_ocr_status(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
) -> DocumentOCRStatusResponse:
    document = await get_document(session, profile_id, document_id)
    if document.current_ocr_run_id is None:
        return DocumentOCRStatusResponse(
            document_id=document.id,
            profile_id=document.profile_id,
            status=document.ocr_status,
            run_id=None,
            run_status=None,
            attempt=None,
            language_spec=None,
            psm=None,
            engine_name=None,
            engine_version=None,
            candidate_count=0,
            needs_review_count=0,
            completed_at=document.ocr_completed_at,
            safe_error_code=None,
        )

    run_result = await session.execute(
        select(DocumentOCRRun).where(
            DocumentOCRRun.id == document.current_ocr_run_id,
            DocumentOCRRun.document_id == document.id,
            DocumentOCRRun.profile_id == document.profile_id,
        )
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        return DocumentOCRStatusResponse(
            document_id=document.id,
            profile_id=document.profile_id,
            status="error",
            run_id=document.current_ocr_run_id,
            run_status=None,
            attempt=None,
            language_spec=None,
            psm=None,
            engine_name=None,
            engine_version=None,
            candidate_count=0,
            needs_review_count=0,
            completed_at=document.ocr_completed_at,
            safe_error_code="ocr_run_missing",
        )

    counts = await session.execute(
        select(
            func.count(DocumentOCRCandidate.id),
            func.count(DocumentOCRCandidate.id).filter(
                DocumentOCRCandidate.status == "needs_review"
            ),
        ).where(
            DocumentOCRCandidate.run_id == run.id,
            DocumentOCRCandidate.document_id == document.id,
            DocumentOCRCandidate.profile_id == document.profile_id,
        )
    )
    candidate_count, needs_review_count = counts.one()
    return DocumentOCRStatusResponse(
        document_id=document.id,
        profile_id=document.profile_id,
        status=document.ocr_status,
        run_id=run.id,
        run_status=run.status,
        attempt=run.attempt,
        language_spec=run.language_spec,
        psm=run.psm,
        engine_name=run.engine_name,
        engine_version=run.engine_version,
        candidate_count=int(candidate_count or 0),
        needs_review_count=int(needs_review_count or 0),
        completed_at=run.completed_at,
        safe_error_code=run.safe_error_code,
    )


async def list_document_ocr_candidates(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
) -> list[DocumentOCRCandidate]:
    document = await get_document(session, profile_id, document_id)
    await require_profile_edit_access(session, profile_id)
    if document.current_ocr_run_id is None:
        return []
    result = await session.execute(
        select(DocumentOCRCandidate)
        .where(
            DocumentOCRCandidate.run_id == document.current_ocr_run_id,
            DocumentOCRCandidate.document_id == document.id,
            DocumentOCRCandidate.profile_id == document.profile_id,
        )
        .order_by(
            DocumentOCRCandidate.page_number,
            DocumentOCRCandidate.candidate_index,
        )
    )
    return list(result.scalars().all())
