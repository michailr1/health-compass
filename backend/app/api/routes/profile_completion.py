"""Derived profile-questionnaire completion endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.profile_completion import ProfileCompletionSummary
from app.services.profile_completion import get_profile_completion

router = APIRouter(tags=["profile-completion"])


@router.get(
    "/profiles/{profile_id}/completion",
    response_model=ProfileCompletionSummary,
)
async def profile_completion(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await get_profile_completion(session, profile_id)
