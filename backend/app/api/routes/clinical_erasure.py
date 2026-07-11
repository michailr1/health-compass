"""Owner-only permanent-erasure endpoints for Clinical Context records."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.clinical_erasure import (
    ClinicalEraseRequest,
    ClinicalEraseResponse,
    ClinicalEraseSection,
)
from app.services.clinical_erasure import erase_clinical_record

router = APIRouter(tags=["clinical-context"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def _erase(
    *,
    profile_id: uuid.UUID,
    section: ClinicalEraseSection,
    record_id: uuid.UUID,
    payload: ClinicalEraseRequest,
    request: Request,
    session: AsyncSession,
) -> dict[str, object]:
    return await erase_clinical_record(
        session,
        profile_id=profile_id,
        section=section,
        record_id=record_id,
        expected_updated_at=payload.expected_updated_at,
        request_id=_request_id(request),
    )


@router.delete(
    "/profiles/{profile_id}/conditions/{record_id}",
    response_model=ClinicalEraseResponse,
)
async def erase_condition(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ClinicalEraseRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _erase(
        profile_id=profile_id,
        section="conditions",
        record_id=record_id,
        payload=payload,
        request=request,
        session=session,
    )


@router.delete(
    "/profiles/{profile_id}/allergies/{record_id}",
    response_model=ClinicalEraseResponse,
)
async def erase_allergy(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ClinicalEraseRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _erase(
        profile_id=profile_id,
        section="allergies",
        record_id=record_id,
        payload=payload,
        request=request,
        session=session,
    )


@router.delete(
    "/profiles/{profile_id}/medications/{record_id}",
    response_model=ClinicalEraseResponse,
)
async def erase_medication(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ClinicalEraseRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _erase(
        profile_id=profile_id,
        section="medications",
        record_id=record_id,
        payload=payload,
        request=request,
        session=session,
    )


@router.delete(
    "/profiles/{profile_id}/supplements/{record_id}",
    response_model=ClinicalEraseResponse,
)
async def erase_supplement(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ClinicalEraseRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _erase(
        profile_id=profile_id,
        section="supplements",
        record_id=record_id,
        payload=payload,
        request=request,
        session=session,
    )


@router.delete(
    "/profiles/{profile_id}/clinical-safety-flags/{record_id}",
    response_model=ClinicalEraseResponse,
)
async def erase_safety_flag(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ClinicalEraseRequest,
    request: Request,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _erase(
        profile_id=profile_id,
        section="clinical-safety-flags",
        record_id=record_id,
        payload=payload,
        request=request,
        session=session,
    )
