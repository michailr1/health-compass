"""First-class review-state endpoints for Clinical Context sections."""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.clinical_context import (
    AllergyCreateRequest,
    AllergyResponse,
    ConditionResponse,
    MedicationCreateRequest,
    MedicationResponse,
    SupplementCreateRequest,
    SupplementResponse,
)
from app.schemas.clinical_context_summary import (
    ClinicalContextSummary,
    ClinicalSectionReviewRequest,
)
from app.schemas.clinical_questions import ConditionCreateWithQuestions
from app.services.clinical_context import create_record
from app.services.clinical_review import (
    clear_incompatible_review_state,
    get_summary,
    lock_section_review,
    review_section,
)

router = APIRouter(tags=["clinical-context-review"])
Section = Literal["conditions", "allergies", "medications", "supplements"]
ReviewState = Literal["unknown", "deferred", "confirmed_none"]


class ReviewStatePatch(BaseModel):
    review_state: ReviewState
    expected_updated_at: datetime.datetime | None = None


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get(
    "/profiles/{profile_id}/clinical-context",
    response_model=ClinicalContextSummary,
)
@router.get(
    "/profiles/{profile_id}/clinical-context/state",
    response_model=ClinicalContextSummary,
)
async def clinical_context_state(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await get_summary(session, profile_id)


@router.post(
    "/profiles/{profile_id}/clinical-context/review",
    response_model=ClinicalContextSummary,
)
async def legacy_review_clinical_context(
    profile_id: uuid.UUID,
    payload: ClinicalSectionReviewRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await review_section(
        session,
        profile_id,
        payload.section,
        payload.review_state,
        payload.expected_updated_at,
        current_user,
        _request_id(request),
    )
    return await get_summary(session, profile_id)


@router.patch(
    "/profiles/{profile_id}/clinical-context/sections/{section}/review",
    response_model=ClinicalContextSummary,
)
async def patch_clinical_section_review(
    profile_id: uuid.UUID,
    section: Section,
    payload: ReviewStatePatch,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await review_section(
        session,
        profile_id,
        section,
        payload.review_state,
        payload.expected_updated_at,
        current_user,
        _request_id(request),
    )
    return await get_summary(session, profile_id)


async def _create_and_clear_review(
    *,
    session: AsyncSession,
    profile_id: uuid.UUID,
    section: Section,
    payload: BaseModel,
    current_user: User,
    request: Request,
):
    # Serialize against a concurrent confirmed_none review of this section
    # (CR-10): the same advisory lock is taken by review_section.
    await lock_section_review(session, profile_id, section)
    record = await create_record(
        session,
        profile_id,
        section,
        payload,
        current_user,
        _request_id(request),
    )
    await clear_incompatible_review_state(
        session,
        profile_id=profile_id,
        section=section,
        actor_user_id=current_user.id,
        request_id=_request_id(request),
    )
    await session.flush()
    return record


@router.post("/profiles/{profile_id}/conditions", response_model=ConditionResponse, status_code=201)
async def add_condition_with_review_state(
    profile_id: uuid.UUID,
    payload: ConditionCreateWithQuestions,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _create_and_clear_review(
        session=session,
        profile_id=profile_id,
        section="conditions",
        payload=payload,
        current_user=current_user,
        request=request,
    )


@router.post("/profiles/{profile_id}/allergies", response_model=AllergyResponse, status_code=201)
async def add_allergy_with_review_state(
    profile_id: uuid.UUID,
    payload: AllergyCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _create_and_clear_review(
        session=session,
        profile_id=profile_id,
        section="allergies",
        payload=payload,
        current_user=current_user,
        request=request,
    )


@router.post("/profiles/{profile_id}/medications", response_model=MedicationResponse, status_code=201)
async def add_medication_with_review_state(
    profile_id: uuid.UUID,
    payload: MedicationCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _create_and_clear_review(
        session=session,
        profile_id=profile_id,
        section="medications",
        payload=payload,
        current_user=current_user,
        request=request,
    )


@router.post("/profiles/{profile_id}/supplements", response_model=SupplementResponse, status_code=201)
async def add_supplement_with_review_state(
    profile_id: uuid.UUID,
    payload: SupplementCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _create_and_clear_review(
        session=session,
        profile_id=profile_id,
        section="supplements",
        payload=payload,
        current_user=current_user,
        request=request,
    )
