"""Business logic for explicit Contextual Intake decisions."""

from __future__ import annotations

import uuid

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contextual_intake import ProfileIntakeDecision
from app.models.user import User
from app.schemas.clinical_context import (
    AllergyCreateRequest,
    MedicationCreateRequest,
    SupplementCreateRequest,
)
from app.schemas.clinical_questions import ConditionCreateWithQuestions
from app.schemas.contextual_intake import ContextualIntakeDecisionRequest
from app.services.clinical_context import create_record
from app.services.clinical_review import clear_incompatible_review_state
from app.services.health_profile import get_visible_profile, require_profile_edit_access

SCHEMA_BY_SECTION: dict[str, type[BaseModel]] = {
    "conditions": ConditionCreateWithQuestions,
    "allergies": AllergyCreateRequest,
    "medications": MedicationCreateRequest,
    "supplements": SupplementCreateRequest,
}


async def apply_contextual_intake_decision(
    session: AsyncSession,
    *,
    profile_id: uuid.UUID,
    payload: ContextualIntakeDecisionRequest,
    current_user: User,
    request_id: str | None,
) -> tuple[ProfileIntakeDecision, uuid.UUID | None]:
    await get_visible_profile(session, profile_id)
    await require_profile_edit_access(session, profile_id)

    record_id: uuid.UUID | None = None
    if payload.decision == "save_to_profile":
        assert payload.proposed_section is not None
        assert payload.record_payload is not None
        request_model = SCHEMA_BY_SECTION[payload.proposed_section].model_validate(payload.record_payload)
        record = await create_record(
            session,
            profile_id,
            payload.proposed_section,
            request_model,
            current_user,
            request_id,
        )
        await clear_incompatible_review_state(
            session,
            profile_id=profile_id,
            section=payload.proposed_section,
            actor_user_id=current_user.id,
            request_id=request_id,
        )
        record_id = record.id

    decision = ProfileIntakeDecision(
        id=uuid.uuid4(),
        profile_id=profile_id,
        prompt_key=payload.prompt_key,
        context_type=payload.context_type,
        decision=payload.decision,
        proposed_section=payload.proposed_section,
        analysis_scope_id=payload.analysis_scope_id,
        decided_by_user_id=current_user.id,
        request_id=request_id,
    )
    session.add(decision)
    await session.flush()
    return decision, record_id
