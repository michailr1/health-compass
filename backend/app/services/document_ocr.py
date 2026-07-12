"""Service layer for HC-017 OCR status, candidates and human review."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_ocr import (
    DocumentOCRCandidate,
    DocumentOCRPatientDecision,
    DocumentOCRRun,
)
from app.schemas.document_ocr import (
    DocumentOCRCandidateReviewRequest,
    DocumentOCRCandidateResponse,
    DocumentOCRFinalizeRequest,
    DocumentOCRPatientDecisionRequest,
    DocumentOCRPatientDecisionResponse,
    DocumentOCRReviewResponse,
    DocumentOCRStatusResponse,
    OCRCandidateVersion,
)
from app.services.documents import get_document
from app.services.health_profile import require_profile_edit_access

_SQLSTATE_RESPONSE = {
    "HC404": (status.HTTP_404_NOT_FOUND, "OCR review resource not found"),
    "HC409": (status.HTTP_409_CONFLICT, "OCR review was updated elsewhere or is incomplete"),
    "HC422": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid OCR review request"),
    "HC428": (status.HTTP_428_PRECONDITION_REQUIRED, "OCR review precondition is required"),
}


def _database_sqlstate(exc: DBAPIError) -> str:
    original = getattr(exc, "orig", None)
    return str(
        getattr(original, "sqlstate", None)
        or getattr(original, "pgcode", None)
        or ""
    )


def _translate_review_error(exc: DBAPIError) -> HTTPException | None:
    response = _SQLSTATE_RESPONSE.get(_database_sqlstate(exc))
    if response is None:
        return None
    status_code, detail = response
    return HTTPException(status_code=status_code, detail=detail)


async def _execute_review_statement(
    session: AsyncSession,
    statement: Any,
    parameters: dict[str, Any],
) -> None:
    try:
        result = await session.execute(statement, parameters)
        if result.scalar_one() is not True:
            raise RuntimeError("OCR review operation was not confirmed")
    except DBAPIError as exc:
        translated = _translate_review_error(exc)
        if translated is None:
            raise
        raise translated from exc


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
            review_status=None,
            attempt=None,
            language_spec=None,
            psm=None,
            engine_name=None,
            engine_version=None,
            candidate_count=0,
            needs_review_count=0,
            completed_at=document.ocr_completed_at,
            review_finalized_at=None,
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
            review_status=None,
            attempt=None,
            language_spec=None,
            psm=None,
            engine_name=None,
            engine_version=None,
            candidate_count=0,
            needs_review_count=0,
            completed_at=document.ocr_completed_at,
            review_finalized_at=None,
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
        review_status=run.review_status,
        attempt=run.attempt,
        language_spec=run.language_spec,
        psm=run.psm,
        engine_name=run.engine_name,
        engine_version=run.engine_version,
        candidate_count=int(candidate_count or 0),
        needs_review_count=int(needs_review_count or 0),
        completed_at=run.completed_at,
        review_finalized_at=run.review_finalized_at,
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


async def get_document_ocr_review(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
) -> DocumentOCRReviewResponse:
    document = await get_document(session, profile_id, document_id)
    await require_profile_edit_access(session, profile_id)
    if document.current_ocr_run_id is None or document.ocr_status not in {
        "review_required",
        "reviewed",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="OCR review is not available",
        )

    run_result = await session.execute(
        select(DocumentOCRRun).where(
            DocumentOCRRun.id == document.current_ocr_run_id,
            DocumentOCRRun.document_id == document.id,
            DocumentOCRRun.profile_id == document.profile_id,
        )
    )
    run = run_result.scalar_one_or_none()
    if run is None or run.status != "succeeded":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="OCR review is not available",
        )

    candidates = await list_document_ocr_candidates(session, profile_id, document_id)
    decision_result = await session.execute(
        select(DocumentOCRPatientDecision).where(
            DocumentOCRPatientDecision.run_id == run.id,
            DocumentOCRPatientDecision.document_id == document.id,
            DocumentOCRPatientDecision.profile_id == document.profile_id,
        )
    )
    patient_decision = decision_result.scalar_one_or_none()

    unresolved_count = sum(
        candidate.status in {"needs_review", "deferred"} for candidate in candidates
    )
    deferred_count = sum(candidate.status == "deferred" for candidate in candidates)
    decision_allows_finalization = (
        patient_decision is not None
        and patient_decision.decision in {"match", "not_present"}
    )
    can_finalize = (
        document.ocr_status == "review_required"
        and run.review_status != "finalized"
        and unresolved_count == 0
        and decision_allows_finalization
    )

    candidate_responses = [
        DocumentOCRCandidateResponse.model_validate(candidate) for candidate in candidates
    ]
    candidate_versions = [
        OCRCandidateVersion(id=candidate.id, updated_at=candidate.updated_at)
        for candidate in candidates
    ]
    return DocumentOCRReviewResponse(
        document_id=document.id,
        profile_id=document.profile_id,
        run_id=run.id,
        document_updated_at=document.updated_at,
        ocr_status=document.ocr_status,
        review_status=run.review_status,
        candidates=candidate_responses,
        candidate_versions=candidate_versions,
        patient_decision=(
            DocumentOCRPatientDecisionResponse.model_validate(patient_decision)
            if patient_decision is not None
            else None
        ),
        unresolved_count=unresolved_count,
        deferred_count=deferred_count,
        can_finalize=can_finalize,
        finalized_at=run.review_finalized_at,
    )


async def review_document_ocr_candidate(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    candidate_id: uuid.UUID,
    payload: DocumentOCRCandidateReviewRequest,
    request_id: str | None,
) -> DocumentOCRReviewResponse:
    document = await get_document(session, profile_id, document_id)
    await require_profile_edit_access(session, profile_id)
    await _execute_review_statement(
        session,
        text(
            """
            SELECT health_compass.app_review_document_ocr_candidate(
              :candidate_id, :action, :reviewed_text, :review_note,
              :expected_updated_at, :audit_event_id, :request_id
            )
            """
        ),
        {
            "candidate_id": candidate_id,
            "action": payload.action,
            "reviewed_text": payload.reviewed_text,
            "review_note": payload.review_note,
            "expected_updated_at": payload.expected_updated_at,
            "audit_event_id": uuid.uuid4(),
            "request_id": request_id,
        },
    )
    if document.id != document_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return await get_document_ocr_review(session, profile_id, document_id)


async def set_document_ocr_patient_decision(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentOCRPatientDecisionRequest,
    request_id: str | None,
) -> DocumentOCRReviewResponse:
    review = await get_document_ocr_review(session, profile_id, document_id)
    decision_id = (
        review.patient_decision.id
        if review.patient_decision is not None
        else uuid.uuid4()
    )
    await _execute_review_statement(
        session,
        text(
            """
            SELECT health_compass.app_set_document_ocr_patient_decision(
              :document_id, :decision_id, :decision, :note,
              :expected_document_updated_at, :expected_decision_updated_at,
              :audit_event_id, :request_id
            )
            """
        ),
        {
            "document_id": document_id,
            "decision_id": decision_id,
            "decision": payload.decision,
            "note": payload.note,
            "expected_document_updated_at": payload.expected_document_updated_at,
            "expected_decision_updated_at": payload.expected_decision_updated_at,
            "audit_event_id": uuid.uuid4(),
            "request_id": request_id,
        },
    )
    return await get_document_ocr_review(session, profile_id, document_id)


async def finalize_document_ocr_review(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentOCRFinalizeRequest,
    request_id: str | None,
) -> DocumentOCRReviewResponse:
    await get_document_ocr_review(session, profile_id, document_id)
    candidate_versions = [
        {
            "id": str(item.id),
            "updated_at": item.updated_at.isoformat(),
        }
        for item in payload.candidate_versions
    ]
    await _execute_review_statement(
        session,
        text(
            """
            SELECT health_compass.app_finalize_document_ocr_review(
              :document_id, :expected_document_updated_at,
              CAST(:candidate_versions AS jsonb),
              :expected_patient_decision_updated_at,
              :audit_event_id, :request_id
            )
            """
        ),
        {
            "document_id": document_id,
            "expected_document_updated_at": payload.expected_document_updated_at,
            "candidate_versions": json.dumps(candidate_versions),
            "expected_patient_decision_updated_at": (
                payload.expected_patient_decision_updated_at
            ),
            "audit_event_id": uuid.uuid4(),
            "request_id": request_id,
        },
    )
    return await get_document_ocr_review(session, profile_id, document_id)
