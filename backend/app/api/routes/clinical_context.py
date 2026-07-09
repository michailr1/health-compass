"""Clinical Context Slice 2 endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.clinical_context import (
    AllergyCreateRequest,
    AllergyPatchRequest,
    AllergyResponse,
    ClinicalVoidRequest,
    ConditionCreateRequest,
    ConditionPatchRequest,
    ConditionResponse,
    MedicationCreateRequest,
    MedicationPatchRequest,
    MedicationResponse,
    SafetyFlagCreateRequest,
    SafetyFlagPatchRequest,
    SafetyFlagResponse,
    SupplementCreateRequest,
    SupplementPatchRequest,
    SupplementResponse,
)
from app.schemas.clinical_context_summary import (
    ClinicalContextSummary,
    ClinicalSectionReviewRequest,
)
from app.services.clinical_context import (
    create_record,
    get_summary,
    list_records,
    review_section,
    update_record,
    void_record,
)

router = APIRouter(tags=["clinical-context"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/profiles/{profile_id}/clinical-context", response_model=ClinicalContextSummary)
async def clinical_context_summary(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await get_summary(session, profile_id)


@router.post("/profiles/{profile_id}/clinical-context/review", response_model=ClinicalContextSummary)
async def review_clinical_context(
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
        payload.confirmed_empty,
        current_user,
        _request_id(request),
    )
    return await get_summary(session, profile_id)


@router.get("/profiles/{profile_id}/conditions", response_model=list[ConditionResponse])
async def get_conditions(
    profile_id: uuid.UUID,
    include_voided: bool = Query(default=False),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_records(session, profile_id, "conditions", include_voided=include_voided)


@router.post("/profiles/{profile_id}/conditions", response_model=ConditionResponse, status_code=201)
async def add_condition(
    profile_id: uuid.UUID,
    payload: ConditionCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_record(session, profile_id, "conditions", payload, current_user, _request_id(request))


@router.patch("/profiles/{profile_id}/conditions/{record_id}", response_model=ConditionResponse)
async def patch_condition(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ConditionPatchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await update_record(session, profile_id, "conditions", record_id, payload, current_user, _request_id(request))


@router.post("/profiles/{profile_id}/conditions/{record_id}/void", response_model=ConditionResponse)
async def void_condition(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ClinicalVoidRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await void_record(session, profile_id, "conditions", record_id, payload.reason, current_user, _request_id(request))


@router.get("/profiles/{profile_id}/allergies", response_model=list[AllergyResponse])
async def get_allergies(
    profile_id: uuid.UUID,
    include_voided: bool = Query(default=False),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_records(session, profile_id, "allergies", include_voided=include_voided)


@router.post("/profiles/{profile_id}/allergies", response_model=AllergyResponse, status_code=201)
async def add_allergy(
    profile_id: uuid.UUID,
    payload: AllergyCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_record(session, profile_id, "allergies", payload, current_user, _request_id(request))


@router.patch("/profiles/{profile_id}/allergies/{record_id}", response_model=AllergyResponse)
async def patch_allergy(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: AllergyPatchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await update_record(session, profile_id, "allergies", record_id, payload, current_user, _request_id(request))


@router.post("/profiles/{profile_id}/allergies/{record_id}/void", response_model=AllergyResponse)
async def void_allergy(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ClinicalVoidRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await void_record(session, profile_id, "allergies", record_id, payload.reason, current_user, _request_id(request))


@router.get("/profiles/{profile_id}/medications", response_model=list[MedicationResponse])
async def get_medications(
    profile_id: uuid.UUID,
    include_voided: bool = Query(default=False),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_records(session, profile_id, "medications", include_voided=include_voided)


@router.post("/profiles/{profile_id}/medications", response_model=MedicationResponse, status_code=201)
async def add_medication(
    profile_id: uuid.UUID,
    payload: MedicationCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_record(session, profile_id, "medications", payload, current_user, _request_id(request))


@router.patch("/profiles/{profile_id}/medications/{record_id}", response_model=MedicationResponse)
async def patch_medication(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: MedicationPatchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await update_record(session, profile_id, "medications", record_id, payload, current_user, _request_id(request))


@router.post("/profiles/{profile_id}/medications/{record_id}/void", response_model=MedicationResponse)
async def void_medication(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ClinicalVoidRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await void_record(session, profile_id, "medications", record_id, payload.reason, current_user, _request_id(request))


@router.get("/profiles/{profile_id}/supplements", response_model=list[SupplementResponse])
async def get_supplements(
    profile_id: uuid.UUID,
    include_voided: bool = Query(default=False),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_records(session, profile_id, "supplements", include_voided=include_voided)


@router.post("/profiles/{profile_id}/supplements", response_model=SupplementResponse, status_code=201)
async def add_supplement(
    profile_id: uuid.UUID,
    payload: SupplementCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_record(session, profile_id, "supplements", payload, current_user, _request_id(request))


@router.patch("/profiles/{profile_id}/supplements/{record_id}", response_model=SupplementResponse)
async def patch_supplement(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: SupplementPatchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await update_record(session, profile_id, "supplements", record_id, payload, current_user, _request_id(request))


@router.post("/profiles/{profile_id}/supplements/{record_id}/void", response_model=SupplementResponse)
async def void_supplement(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ClinicalVoidRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await void_record(session, profile_id, "supplements", record_id, payload.reason, current_user, _request_id(request))


@router.get("/profiles/{profile_id}/clinical-safety-flags", response_model=list[SafetyFlagResponse])
async def get_safety_flags(
    profile_id: uuid.UUID,
    include_voided: bool = Query(default=False),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_records(session, profile_id, "clinical-safety-flags", include_voided=include_voided)


@router.post("/profiles/{profile_id}/clinical-safety-flags", response_model=SafetyFlagResponse, status_code=201)
async def add_safety_flag(
    profile_id: uuid.UUID,
    payload: SafetyFlagCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_record(session, profile_id, "clinical-safety-flags", payload, current_user, _request_id(request))


@router.patch("/profiles/{profile_id}/clinical-safety-flags/{record_id}", response_model=SafetyFlagResponse)
async def patch_safety_flag(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: SafetyFlagPatchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await update_record(session, profile_id, "clinical-safety-flags", record_id, payload, current_user, _request_id(request))


@router.post("/profiles/{profile_id}/clinical-safety-flags/{record_id}/void", response_model=SafetyFlagResponse)
async def void_safety_flag(
    profile_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: ClinicalVoidRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await void_record(session, profile_id, "clinical-safety-flags", record_id, payload.reason, current_user, _request_id(request))
