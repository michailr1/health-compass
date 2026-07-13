"""HC-017 E3 correction, void and owner-only Lab observation erasure."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lab_observation import LabObservation, LabObservationSource
from app.schemas.lab_observation import (
    EraseLabObservationRequest,
    EraseLabObservationResponse,
    LabObservationResponse,
    LabObservationSourceResponse,
    RequestDocumentLabErasureRequest,
    RequestDocumentLabErasureResponse,
    VoidLabObservationRequest,
)
from app.schemas.lab_observation_lifecycle import (
    CorrectLabObservationLifecycleRequest,
)
from app.services.documents import get_document
from app.services.health_profile import require_profile_edit_access

_SQLSTATE_RESPONSE = {
    "HC404": (status.HTTP_404_NOT_FOUND, "Lab observation not found"),
    "HC409": (status.HTTP_409_CONFLICT, "Lab observation lifecycle changed"),
    "HC422": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid Lab lifecycle request"),
    "HC428": (status.HTTP_428_PRECONDITION_REQUIRED, "Lab lifecycle precondition is required"),
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


async def _lifecycle_response(
    session: AsyncSession,
    profile_id: uuid.UUID,
    observation_id: uuid.UUID,
) -> LabObservationResponse:
    await require_profile_edit_access(session, profile_id)
    result = await session.execute(
        select(LabObservation).where(
            LabObservation.id == observation_id,
            LabObservation.profile_id == profile_id,
        )
    )
    observation = result.scalar_one_or_none()
    if observation is None:
        raise HTTPException(status_code=404, detail="Lab observation not found")
    source_result = await session.execute(
        select(LabObservationSource)
        .where(LabObservationSource.observation_id == observation.id)
        .order_by(
            LabObservationSource.page_number,
            LabObservationSource.candidate_id,
            LabObservationSource.source_role,
        )
    )
    sources = [
        LabObservationSourceResponse.model_validate(item)
        for item in source_result.scalars().all()
    ]
    response = LabObservationResponse.model_validate(observation)
    return response.model_copy(update={"sources": sources})


async def list_lab_observation_history(
    session: AsyncSession,
    profile_id: uuid.UUID,
) -> list[LabObservationResponse]:
    await require_profile_edit_access(session, profile_id)
    result = await session.execute(
        select(LabObservation)
        .where(LabObservation.profile_id == profile_id)
        .order_by(
            LabObservation.lifecycle_updated_at.desc(),
            LabObservation.created_at.desc(),
            LabObservation.id,
        )
    )
    observations = list(result.scalars().all())
    source_result = (
        await session.execute(
            select(LabObservationSource)
            .where(
                LabObservationSource.observation_id.in_(
                    [observation.id for observation in observations]
                )
            )
            .order_by(
                LabObservationSource.page_number,
                LabObservationSource.candidate_id,
                LabObservationSource.source_role,
            )
        )
        if observations
        else None
    )
    grouped: dict[uuid.UUID, list[LabObservationSourceResponse]] = {}
    if source_result is not None:
        for item in source_result.scalars().all():
            grouped.setdefault(item.observation_id, []).append(
                LabObservationSourceResponse.model_validate(item)
            )
    return [
        LabObservationResponse.model_validate(observation).model_copy(
            update={"sources": grouped.get(observation.id, [])}
        )
        for observation in observations
    ]


async def correct_lab_observation(
    session: AsyncSession,
    profile_id: uuid.UUID,
    observation_id: uuid.UUID,
    payload: CorrectLabObservationLifecycleRequest,
    request_id: str | None,
) -> LabObservationResponse:
    await _lifecycle_response(session, profile_id, observation_id)
    new_observation_id = uuid.uuid4()
    corrected_id = await _execute_scalar(
        session,
        text(
            """
            SELECT health_compass.app_correct_lab_observation(
              :new_observation_id, :observation_id,
              :expected_lifecycle_version, :idempotency_key, :reason,
              CAST(:payload AS jsonb),
              :acknowledge_source_matches,
              :acknowledge_unit_and_range,
              :acknowledge_observed_at,
              :acknowledge_profile,
              :acknowledge_structured_record,
              :acknowledge_not_present_assignment,
              :audit_event_id, :request_id
            )
            """
        ),
        {
            "new_observation_id": new_observation_id,
            "observation_id": observation_id,
            "expected_lifecycle_version": payload.expected_lifecycle_version,
            "idempotency_key": payload.idempotency_key,
            "reason": payload.reason,
            "payload": json.dumps(
                payload.fields.model_dump(mode="json", exclude_none=True)
            ),
            "acknowledge_source_matches": payload.acknowledge_source_matches,
            "acknowledge_unit_and_range": payload.acknowledge_unit_and_range,
            "acknowledge_observed_at": payload.acknowledge_observed_at,
            "acknowledge_profile": payload.acknowledge_profile,
            "acknowledge_structured_record": payload.acknowledge_structured_record,
            "acknowledge_not_present_assignment": (
                payload.acknowledge_not_present_assignment
            ),
            "audit_event_id": uuid.uuid4(),
            "request_id": request_id,
        },
    )
    return await _lifecycle_response(session, profile_id, corrected_id)


async def void_lab_observation(
    session: AsyncSession,
    profile_id: uuid.UUID,
    observation_id: uuid.UUID,
    payload: VoidLabObservationRequest,
    request_id: str | None,
) -> LabObservationResponse:
    await _lifecycle_response(session, profile_id, observation_id)
    await _execute_scalar(
        session,
        text(
            """
            SELECT health_compass.app_void_lab_observation(
              :observation_id, :expected_lifecycle_version, :reason,
              :audit_event_id, :request_id
            )
            """
        ),
        {
            "observation_id": observation_id,
            "expected_lifecycle_version": payload.expected_lifecycle_version,
            "reason": payload.reason,
            "audit_event_id": uuid.uuid4(),
            "request_id": request_id,
        },
    )
    return await _lifecycle_response(session, profile_id, observation_id)


async def erase_lab_observation(
    session: AsyncSession,
    profile_id: uuid.UUID,
    observation_id: uuid.UUID,
    payload: EraseLabObservationRequest,
    request_id: str | None,
) -> EraseLabObservationResponse:
    await _lifecycle_response(session, profile_id, observation_id)
    deleted_count = int(
        await _execute_scalar(
            session,
            text(
                """
                SELECT health_compass.app_erase_lab_observation(
                  :observation_id, :expected_lifecycle_version,
                  :confirm_permanent_deletion, :audit_event_id, :request_id
                )
                """
            ),
            {
                "observation_id": observation_id,
                "expected_lifecycle_version": payload.expected_lifecycle_version,
                "confirm_permanent_deletion": payload.confirm_permanent_deletion,
                "audit_event_id": uuid.uuid4(),
                "request_id": request_id,
            },
        )
    )
    return EraseLabObservationResponse(
        deleted=True,
        deleted_observation_count=deleted_count,
        observation_id=observation_id,
    )


async def request_document_lab_erasure(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: RequestDocumentLabErasureRequest,
    request_id: str | None,
) -> RequestDocumentLabErasureResponse:
    document = await get_document(session, profile_id, document_id)
    deleted_count = int(
        await _execute_scalar(
            session,
            text(
                """
                SELECT health_compass.app_request_document_lab_erasure(
                  :document_id, :expected_document_updated_at,
                  :confirm_permanent_deletion, :audit_event_id, :request_id
                )
                """
            ),
            {
                "document_id": document.id,
                "expected_document_updated_at": payload.expected_document_updated_at,
                "confirm_permanent_deletion": payload.confirm_permanent_deletion,
                "audit_event_id": uuid.uuid4(),
                "request_id": request_id,
            },
        )
    )
    return RequestDocumentLabErasureResponse(
        deletion_requested=True,
        deleted_observation_count=deleted_count,
        document_id=document_id,
    )
