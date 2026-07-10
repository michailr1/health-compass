"""Explicit Contextual Intake decision endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.contextual_intake import (
    ContextualIntakeDecisionRequest,
    ContextualIntakeDecisionResponse,
)
from app.services.contextual_intake import apply_contextual_intake_decision

router = APIRouter(tags=["contextual-intake"])


@router.post(
    "/profiles/{profile_id}/contextual-intake/decisions",
    response_model=ContextualIntakeDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_contextual_intake_decision(
    profile_id: uuid.UUID,
    payload: ContextualIntakeDecisionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    decision, record_id = await apply_contextual_intake_decision(
        session,
        profile_id=profile_id,
        payload=payload,
        current_user=current_user,
        request_id=getattr(request.state, "request_id", None),
    )
    return ContextualIntakeDecisionResponse(
        decision_id=decision.id,
        decision=payload.decision,
        record_id=record_id,
    )
