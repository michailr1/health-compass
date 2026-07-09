"""Service layer for the minimal health-data consent gate."""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import UserConsent
from app.models.user import User
from app.services.health_profile import CONSENT_TYPE


async def get_latest_consent(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> UserConsent | None:
    result = await session.execute(
        select(UserConsent)
        .where(
            UserConsent.user_id == user_id,
            UserConsent.consent_type == CONSENT_TYPE,
        )
        .order_by(desc(UserConsent.accepted_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def accept_consent(
    session: AsyncSession,
    current_user: User,
    document_version: str,
) -> UserConsent:
    existing = await get_latest_consent(session, current_user.id)
    if existing is not None and existing.revoked_at is None:
        if existing.document_version == document_version:
            return existing
        existing.revoked_at = datetime.datetime.now(datetime.UTC)
        await session.flush()

    consent = UserConsent(
        user_id=current_user.id,
        consent_type=CONSENT_TYPE,
        document_version=document_version,
        accepted_at=datetime.datetime.now(datetime.UTC),
    )
    session.add(consent)
    await session.flush()
    return consent


async def revoke_consent(
    session: AsyncSession,
    current_user: User,
) -> UserConsent | None:
    existing = await get_latest_consent(session, current_user.id)
    if existing is None or existing.revoked_at is not None:
        return existing
    existing.revoked_at = datetime.datetime.now(datetime.UTC)
    await session.flush()
    return existing
