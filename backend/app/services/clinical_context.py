"""Business logic for manual clinical context."""

from __future__ import annotations

import datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_context import ProfileAllergy, ProfileMedication
from app.models.consent import UserConsent
from app.models.profile import HealthProfile
from app.models.user import User
from app.schemas.clinical_context import (
    AllergyCreateRequest,
    AllergyPatchRequest,
    ClinicalContextSummary,
    MedicationCreateRequest,
    MedicationPatchRequest,
)
from app.services.health_profile import require_profile_edit_access


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


async def _get_profile(session: AsyncSession, profile_id: uuid.UUID) -> HealthProfile:
    result = await session.execute(select(HealthProfile).where(HealthProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


async def _require_active_consent(session: AsyncSession, profile: HealthProfile) -> None:
    result = await session.execute(
        select(UserConsent.id)
        .where(
            UserConsent.user_id == profile.owner_user_id,
            UserConsent.consent_type == "health_data_processing",
            UserConsent.revoked_at.is_(None),
        )
        .order_by(UserConsent.accepted_at.desc())
        .limit(1)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active health data processing consent is required",
        )


async def _prepare_mutation(session: AsyncSession, profile_id: uuid.UUID) -> HealthProfile:
    profile = await _get_profile(session, profile_id)
    await require_profile_edit_access(session, profile_id)
    await _require_active_consent(session, profile)
    return profile


async def list_allergies(session: AsyncSession, profile_id: uuid.UUID) -> list[ProfileAllergy]:
    await _get_profile(session, profile_id)
    result = await session.execute(
        select(ProfileAllergy)
        .where(ProfileAllergy.profile_id == profile_id)
        .order_by(
            ProfileAllergy.status.asc(),
            ProfileAllergy.severity.desc(),
            ProfileAllergy.created_at.desc(),
        )
    )
    return list(result.scalars())


async def create_allergy(
    session: AsyncSession,
    profile_id: uuid.UUID,
    payload: AllergyCreateRequest,
    current_user: User,
) -> ProfileAllergy:
    profile = await _prepare_mutation(session, profile_id)
    allergy = ProfileAllergy(
        profile_id=profile_id,
        allergen=payload.allergen.strip(),
        reaction=_normalize_optional(payload.reaction),
        severity=payload.severity,
        status="active",
        onset_date=payload.onset_date,
        notes=_normalize_optional(payload.notes),
        source_kind="manual",
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    session.add(allergy)
    profile.allergies_reviewed_at = datetime.datetime.now(datetime.UTC)
    await session.flush()
    return allergy


async def update_allergy(
    session: AsyncSession,
    profile_id: uuid.UUID,
    allergy_id: uuid.UUID,
    payload: AllergyPatchRequest,
    current_user: User,
) -> ProfileAllergy:
    profile = await _prepare_mutation(session, profile_id)
    result = await session.execute(
        select(ProfileAllergy).where(
            ProfileAllergy.id == allergy_id,
            ProfileAllergy.profile_id == profile_id,
        )
    )
    allergy = result.scalar_one_or_none()
    if allergy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allergy not found")

    changes = payload.model_dump(exclude_unset=True)
    for field in ("allergen", "reaction", "notes"):
        if field in changes:
            value = changes[field]
            changes[field] = value.strip() if field == "allergen" and value is not None else _normalize_optional(value)
    for field, value in changes.items():
        setattr(allergy, field, value)
    allergy.updated_by_user_id = current_user.id
    allergy.updated_at = datetime.datetime.now(datetime.UTC)
    profile.allergies_reviewed_at = datetime.datetime.now(datetime.UTC)
    await session.flush()
    return allergy


async def list_medications(session: AsyncSession, profile_id: uuid.UUID) -> list[ProfileMedication]:
    await _get_profile(session, profile_id)
    result = await session.execute(
        select(ProfileMedication)
        .where(ProfileMedication.profile_id == profile_id)
        .order_by(ProfileMedication.status.asc(), ProfileMedication.created_at.desc())
    )
    return list(result.scalars())


async def create_medication(
    session: AsyncSession,
    profile_id: uuid.UUID,
    payload: MedicationCreateRequest,
    current_user: User,
) -> ProfileMedication:
    profile = await _prepare_mutation(session, profile_id)
    medication = ProfileMedication(
        profile_id=profile_id,
        medication_name=payload.medication_name.strip(),
        dose_text=_normalize_optional(payload.dose_text),
        schedule_text=_normalize_optional(payload.schedule_text),
        indication=_normalize_optional(payload.indication),
        status="active",
        started_on=payload.started_on,
        ended_on=payload.ended_on,
        notes=_normalize_optional(payload.notes),
        source_kind="manual",
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    session.add(medication)
    profile.medications_reviewed_at = datetime.datetime.now(datetime.UTC)
    await session.flush()
    return medication


async def update_medication(
    session: AsyncSession,
    profile_id: uuid.UUID,
    medication_id: uuid.UUID,
    payload: MedicationPatchRequest,
    current_user: User,
) -> ProfileMedication:
    profile = await _prepare_mutation(session, profile_id)
    result = await session.execute(
        select(ProfileMedication).where(
            ProfileMedication.id == medication_id,
            ProfileMedication.profile_id == profile_id,
        )
    )
    medication = result.scalar_one_or_none()
    if medication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

    changes = payload.model_dump(exclude_unset=True)
    for field in ("medication_name", "dose_text", "schedule_text", "indication", "notes"):
        if field in changes:
            value = changes[field]
            changes[field] = value.strip() if field == "medication_name" and value is not None else _normalize_optional(value)
    started_on = changes.get("started_on", medication.started_on)
    ended_on = changes.get("ended_on", medication.ended_on)
    if started_on and ended_on and ended_on < started_on:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ended_on cannot be before started_on",
        )
    for field, value in changes.items():
        setattr(medication, field, value)
    medication.updated_by_user_id = current_user.id
    medication.updated_at = datetime.datetime.now(datetime.UTC)
    profile.medications_reviewed_at = datetime.datetime.now(datetime.UTC)
    await session.flush()
    return medication


async def review_clinical_context_section(
    session: AsyncSession,
    profile_id: uuid.UUID,
    section: str,
) -> ClinicalContextSummary:
    profile = await _prepare_mutation(session, profile_id)
    now = datetime.datetime.now(datetime.UTC)
    if section == "allergies":
        profile.allergies_reviewed_at = now
    elif section == "medications":
        profile.medications_reviewed_at = now
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown section")
    await session.flush()
    return await get_clinical_context_summary(session, profile_id)


async def get_clinical_context_summary(
    session: AsyncSession,
    profile_id: uuid.UUID,
) -> ClinicalContextSummary:
    profile = await _get_profile(session, profile_id)
    allergy_counts = await session.execute(
        select(
            func.count(ProfileAllergy.id).filter(ProfileAllergy.status == "active"),
            func.count(ProfileAllergy.id).filter(
                ProfileAllergy.status == "active",
                ProfileAllergy.severity == "severe",
            ),
        ).where(ProfileAllergy.profile_id == profile_id)
    )
    active_allergies, severe_allergies = allergy_counts.one()
    medication_count = await session.execute(
        select(func.count(ProfileMedication.id)).where(
            ProfileMedication.profile_id == profile_id,
            ProfileMedication.status == "active",
        )
    )
    return ClinicalContextSummary(
        allergies_reviewed_at=profile.allergies_reviewed_at,
        medications_reviewed_at=profile.medications_reviewed_at,
        active_allergy_count=int(active_allergies or 0),
        severe_active_allergy_count=int(severe_allergies or 0),
        active_medication_count=int(medication_count.scalar_one() or 0),
    )
