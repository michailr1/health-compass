"""Service layer for HC-017 E1 source-preserving laboratory drafts."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_ocr import (
    DocumentOCRCandidate,
    DocumentOCRPatientDecision,
    DocumentOCRRun,
)
from app.models.lab_observation import LabObservationDraft, LabObservationDraftSource
from app.schemas.document_ocr import DocumentOCRCandidateResponse
from app.schemas.lab_observation import (
    CreateLabDraftRequest,
    LabDraftContextResponse,
    LabDraftResponse,
    LabDraftSourceResponse,
    SetLabDraftSourcesRequest,
    SetLabDraftStatusRequest,
    UpdateLabDraftRequest,
)
from app.services.documents import get_document
from app.services.health_profile import require_profile_edit_access

_SQLSTATE_RESPONSE = {
    "HC404": (status.HTTP_404_NOT_FOUND, "Lab draft resource not found"),
    "HC409": (status.HTTP_409_CONFLICT, "Lab draft source changed or is incomplete"),
    "HC422": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid Lab draft request"),
    "HC428": (status.HTTP_428_PRECONDITION_REQUIRED, "Lab draft precondition is required"),
}


def _database_sqlstate(exc: DBAPIError) -> str:
    original = getattr(exc, "orig", None)
    return str(
        getattr(original, "sqlstate", None)
        or getattr(original, "pgcode", None)
        or ""
    )


def _translate_error(exc: DBAPIError) -> HTTPException | None:
    response = _SQLSTATE_RESPONSE.get(_database_sqlstate(exc))
    if response is None:
        return None
    status_code, detail = response
    return HTTPException(status_code=status_code, detail=detail)


async def _execute_scalar(
    session: AsyncSession,
    statement: Any,
    parameters: dict[str, Any],
) -> Any:
    try:
        result = await session.execute(statement, parameters)
        return result.scalar_one()
    except DBAPIError as exc:
        translated = _translate_error(exc)
        if translated is None:
            raise
        raise translated from exc


async def get_lab_draft_context(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
) -> LabDraftContextResponse:
    document = await get_document(session, profile_id, document_id)
    await require_profile_edit_access(session, profile_id)
    if document.status != "accepted" or document.ocr_status != "reviewed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Finalized OCR review is required",
        )
    if document.current_ocr_run_id is None:
        raise HTTPException(status_code=409, detail="Current OCR run is missing")

    run_result = await session.execute(
        select(DocumentOCRRun).where(
            DocumentOCRRun.id == document.current_ocr_run_id,
            DocumentOCRRun.document_id == document.id,
            DocumentOCRRun.profile_id == document.profile_id,
        )
    )
    run = run_result.scalar_one_or_none()
    if (
        run is None
        or run.status != "succeeded"
        or run.review_status != "finalized"
        or run.review_finalized_at is None
        or run.review_patient_decision_id is None
    ):
        raise HTTPException(status_code=409, detail="Finalized OCR review is required")

    decision_result = await session.execute(
        select(DocumentOCRPatientDecision).where(
            DocumentOCRPatientDecision.id == run.review_patient_decision_id,
            DocumentOCRPatientDecision.run_id == run.id,
            DocumentOCRPatientDecision.document_id == document.id,
            DocumentOCRPatientDecision.profile_id == document.profile_id,
        )
    )
    decision = decision_result.scalar_one_or_none()
    if decision is None or decision.decision not in {"match", "not_present"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient decision does not allow Lab drafts",
        )

    candidate_result = await session.execute(
        select(DocumentOCRCandidate)
        .where(
            DocumentOCRCandidate.run_id == run.id,
            DocumentOCRCandidate.document_id == document.id,
            DocumentOCRCandidate.profile_id == document.profile_id,
            DocumentOCRCandidate.status.in_(["accepted", "edited"]),
            DocumentOCRCandidate.reviewed_text.is_not(None),
        )
        .order_by(
            DocumentOCRCandidate.page_number,
            DocumentOCRCandidate.candidate_index,
        )
    )
    candidates = [
        DocumentOCRCandidateResponse.model_validate(item)
        for item in candidate_result.scalars().all()
    ]
    return LabDraftContextResponse(
        document_id=document.id,
        profile_id=document.profile_id,
        document_updated_at=document.updated_at,
        ocr_run_id=run.id,
        review_finalized_at=run.review_finalized_at,
        patient_decision_id=decision.id,
        patient_decision=decision.decision,
        patient_decision_updated_at=decision.updated_at,
        candidates=candidates,
    )


async def _sources_for_drafts(
    session: AsyncSession,
    draft_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[LabDraftSourceResponse]]:
    if not draft_ids:
        return {}
    result = await session.execute(
        select(LabObservationDraftSource)
        .where(LabObservationDraftSource.draft_id.in_(draft_ids))
        .order_by(
            LabObservationDraftSource.page_number,
            LabObservationDraftSource.candidate_id,
            LabObservationDraftSource.source_role,
        )
    )
    grouped: dict[uuid.UUID, list[LabDraftSourceResponse]] = {}
    for source in result.scalars().all():
        grouped.setdefault(source.draft_id, []).append(
            LabDraftSourceResponse.model_validate(source)
        )
    return grouped


def _draft_response(
    draft: LabObservationDraft,
    sources: list[LabDraftSourceResponse],
) -> LabDraftResponse:
    response = LabDraftResponse.model_validate(draft)
    return response.model_copy(update={"sources": sources})


async def list_lab_drafts(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
) -> list[LabDraftResponse]:
    await get_lab_draft_context(session, profile_id, document_id)
    result = await session.execute(
        select(LabObservationDraft)
        .where(
            LabObservationDraft.profile_id == profile_id,
            LabObservationDraft.document_id == document_id,
        )
        .order_by(LabObservationDraft.created_at, LabObservationDraft.id)
    )
    drafts = list(result.scalars().all())
    sources = await _sources_for_drafts(session, [draft.id for draft in drafts])
    return [_draft_response(draft, sources.get(draft.id, [])) for draft in drafts]


async def get_lab_draft(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    draft_id: uuid.UUID,
) -> LabDraftResponse:
    await require_profile_edit_access(session, profile_id)
    result = await session.execute(
        select(LabObservationDraft).where(
            LabObservationDraft.id == draft_id,
            LabObservationDraft.profile_id == profile_id,
            LabObservationDraft.document_id == document_id,
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Lab draft not found")
    sources = await _sources_for_drafts(session, [draft.id])
    return _draft_response(draft, sources.get(draft.id, []))


def _fields_json(payload: CreateLabDraftRequest | UpdateLabDraftRequest) -> str:
    return json.dumps(payload.fields.model_dump(mode="json", exclude_none=True))


async def create_lab_draft(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: CreateLabDraftRequest,
    request_id: str | None,
) -> LabDraftResponse:
    await get_lab_draft_context(session, profile_id, document_id)
    draft_id = uuid.uuid4()
    created_id = await _execute_scalar(
        session,
        text(
            """
            SELECT health_compass.app_create_lab_observation_draft(
              :draft_id, :document_id, :expected_document_updated_at,
              :expected_review_finalized_at,
              :expected_patient_decision_updated_at,
              CAST(:payload AS jsonb), :audit_event_id, :request_id
            )
            """
        ),
        {
            "draft_id": draft_id,
            "document_id": document_id,
            "expected_document_updated_at": payload.expected_document_updated_at,
            "expected_review_finalized_at": payload.expected_review_finalized_at,
            "expected_patient_decision_updated_at": (
                payload.expected_patient_decision_updated_at
            ),
            "payload": _fields_json(payload),
            "audit_event_id": uuid.uuid4(),
            "request_id": request_id,
        },
    )
    return await get_lab_draft(session, profile_id, document_id, created_id)


async def update_lab_draft(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    draft_id: uuid.UUID,
    payload: UpdateLabDraftRequest,
    request_id: str | None,
) -> LabDraftResponse:
    await get_lab_draft(session, profile_id, document_id, draft_id)
    await _execute_scalar(
        session,
        text(
            """
            SELECT health_compass.app_update_lab_observation_draft(
              :draft_id, :expected_updated_at, :expected_document_updated_at,
              :expected_review_finalized_at,
              :expected_patient_decision_updated_at,
              CAST(:payload AS jsonb), :audit_event_id, :request_id
            )
            """
        ),
        {
            "draft_id": draft_id,
            "expected_updated_at": payload.expected_updated_at,
            "expected_document_updated_at": payload.expected_document_updated_at,
            "expected_review_finalized_at": payload.expected_review_finalized_at,
            "expected_patient_decision_updated_at": (
                payload.expected_patient_decision_updated_at
            ),
            "payload": _fields_json(payload),
            "audit_event_id": uuid.uuid4(),
            "request_id": request_id,
        },
    )
    return await get_lab_draft(session, profile_id, document_id, draft_id)


async def set_lab_draft_sources(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    draft_id: uuid.UUID,
    payload: SetLabDraftSourcesRequest,
    request_id: str | None,
) -> LabDraftResponse:
    await get_lab_draft(session, profile_id, document_id, draft_id)
    manifest = [item.model_dump(mode="json") for item in payload.sources]
    await _execute_scalar(
        session,
        text(
            """
            SELECT health_compass.app_set_lab_draft_sources(
              :draft_id, :expected_updated_at,
              :expected_document_updated_at,
              :expected_review_finalized_at,
              :expected_patient_decision_updated_at,
              CAST(:sources AS jsonb), :audit_event_id, :request_id
            )
            """
        ),
        {
            "draft_id": draft_id,
            "expected_updated_at": payload.expected_updated_at,
            "expected_document_updated_at": payload.expected_document_updated_at,
            "expected_review_finalized_at": payload.expected_review_finalized_at,
            "expected_patient_decision_updated_at": (
                payload.expected_patient_decision_updated_at
            ),
            "sources": json.dumps(manifest),
            "audit_event_id": uuid.uuid4(),
            "request_id": request_id,
        },
    )
    return await get_lab_draft(session, profile_id, document_id, draft_id)


async def set_lab_draft_status(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    draft_id: uuid.UUID,
    payload: SetLabDraftStatusRequest,
    request_id: str | None,
) -> LabDraftResponse:
    await get_lab_draft(session, profile_id, document_id, draft_id)
    await _execute_scalar(
        session,
        text(
            """
            SELECT health_compass.app_set_lab_observation_draft_status(
              :draft_id, :status, :expected_updated_at,
              :expected_document_updated_at,
              :expected_review_finalized_at,
              :expected_patient_decision_updated_at,
              :audit_event_id, :request_id
            )
            """
        ),
        {
            "draft_id": draft_id,
            "status": payload.status,
            "expected_updated_at": payload.expected_updated_at,
            "expected_document_updated_at": payload.expected_document_updated_at,
            "expected_review_finalized_at": payload.expected_review_finalized_at,
            "expected_patient_decision_updated_at": (
                payload.expected_patient_decision_updated_at
            ),
            "audit_event_id": uuid.uuid4(),
            "request_id": request_id,
        },
    )
    return await get_lab_draft(session, profile_id, document_id, draft_id)
