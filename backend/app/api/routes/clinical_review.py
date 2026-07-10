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
from app.schemas.clinical_context_summary import ClinicalContextSummary
from app.services.clinical_review import get_summary, review_section

router = APIRouter(tags=["clinical-context-review"])
Section = Literal["conditions", "allergies", "medications", "supplements"]
ReviewState = Literal["unknown", "deferred", "confirmed_none"]


class ReviewStatePatch(BaseModel):
    review_state: ReviewState
    expected_updated_at: datetime.datetime | None = None


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


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
