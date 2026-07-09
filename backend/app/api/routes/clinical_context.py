"""Manual allergies and medications endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.clinical_context import (
    AllergyCreateRequest,
    AllergyPatchRequest,
    AllergyResponse,
    ClinicalContextReviewRequest,
    ClinicalContextSummary,
    MedicationCreateRequest,
    MedicationPatchRequest,
    MedicationResponse,
)
from app.services.clinical_context import (
    create_allergy,
    create_medication,
    get_clinical_context_summary,
    list_allergies,
    list_medications,
    review_clinical_context_section,
    update_allergy,
    update_medication,
)

router = APIRouter(tags=["clinical-context"])


@router.get(
    "/profiles/{profile_id}/clinical-context",
    response_model=ClinicalContextSummary,
)
async def get_summary(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ClinicalContextSummary:
    return await get_clinical_context_summary(session, profile_id)


@router.post(
    "/profiles/{profile_id}/clinical-context/review",
    response_model=ClinicalContextSummary,
)
async def review_section(
    profile_id: uuid.UUID,
    payload: ClinicalContextReviewRequest,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ClinicalContextSummary:
    return await review_clinical_context_section(session, profile_id, payload.section)


@router.get(
    "/profiles/{profile_id}/allergies",
    response_model=list[AllergyResponse],
)
async def get_allergies(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    return await list_allergies(session, profile_id)


@router.post(
    "/profiles/{profile_id}/allergies",
    response_model=AllergyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_allergy(
    profile_id: uuid.UUID,
    payload: AllergyCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_allergy(session, profile_id, payload, current_user)


@router.patch(
    "/profiles/{profile_id}/allergies/{allergy_id}",
    response_model=AllergyResponse,
)
async def patch_allergy(
    profile_id: uuid.UUID,
    allergy_id: uuid.UUID,
    payload: AllergyPatchRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await update_allergy(session, profile_id, allergy_id, payload, current_user)


@router.get(
    "/profiles/{profile_id}/medications",
    response_model=list[MedicationResponse],
)
async def get_medications(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    return await list_medications(session, profile_id)


@router.post(
    "/profiles/{profile_id}/medications",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_medication(
    profile_id: uuid.UUID,
    payload: MedicationCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_medication(session, profile_id, payload, current_user)


@router.patch(
    "/profiles/{profile_id}/medications/{medication_id}",
    response_model=MedicationResponse,
)
async def patch_medication(
    profile_id: uuid.UUID,
    medication_id: uuid.UUID,
    payload: MedicationPatchRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await update_medication(session, profile_id, medication_id, payload, current_user)
