"""Read-only Clinical Context suggestion endpoints."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.clinical_dictionary import ClinicalSuggestionList
from app.services.clinical_dictionary import get_suggestions

router = APIRouter(tags=["clinical-context-dictionary"])
Section = Literal["conditions", "allergies", "medications", "supplements"]


@router.get(
    "/profiles/{profile_id}/clinical-context/suggestions",
    response_model=ClinicalSuggestionList,
)
async def clinical_context_suggestions(
    profile_id: uuid.UUID,
    section: Section,
    q: str = Query(min_length=1, max_length=255),
    limit: int = Query(default=8, ge=1, le=20),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await get_suggestions(
        session,
        profile_id=profile_id,
        section=section,
        query=q,
        limit=limit,
    )
