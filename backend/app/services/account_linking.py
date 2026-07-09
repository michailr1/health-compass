"""Pre-bootstrap account-linking orchestration.

This service intentionally exposes only scalar candidate information and opaque
intent identifiers. A verified-email match never links identities by itself.
"""

from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.magic_links import normalize_email
from app.models.user import User, UserIdentity


@dataclass(frozen=True, slots=True)
class VerifiedEmailCandidate:
    count: int
    user_id: uuid.UUID | None

    @property
    def has_single_candidate(self) -> bool:
        return self.count == 1 and self.user_id is not None

    @property
    def has_existing_duplicates(self) -> bool:
        return self.count > 1


@dataclass(frozen=True, slots=True)
class NotificationIdentity:
    provider: str
    subject: str
    claims: dict[str, Any]


def collect_verified_notification_emails(
    canonical_email: str,
    identities: Iterable[NotificationIdentity],
) -> tuple[str, ...]:
    """Return unique canonical and verified identity emails in stable order."""
    recipients: set[str] = set()
    canonical = normalize_email(canonical_email)
    if canonical:
        recipients.add(canonical)

    for identity in identities:
        claims = identity.claims or {}
        if claims.get("email_verified") is not True:
            continue
        address = identity.subject if identity.provider == "email" else str(claims.get("email") or "")
        normalized = normalize_email(address)
        if normalized:
            recipients.add(normalized)
    return tuple(sorted(recipients))


async def lookup_verified_email_candidate(
    session: AsyncSession,
    normalized_email: str,
) -> VerifiedEmailCandidate:
    count_result = await session.execute(
        text("select health_compass.app_count_verified_email_users(:email)"),
        {"email": normalized_email},
    )
    count = int(count_result.scalar_one())
    if count != 1:
        return VerifiedEmailCandidate(count=count, user_id=None)

    user_result = await session.execute(
        text("select health_compass.app_lookup_single_verified_email_user(:email)"),
        {"email": normalized_email},
    )
    return VerifiedEmailCandidate(count=count, user_id=user_result.scalar_one_or_none())


async def verified_notification_emails(
    session: AsyncSession,
    user: User,
) -> tuple[str, ...]:
    """Load identities and return every unique verified notification address."""
    result = await session.execute(select(UserIdentity).where(UserIdentity.user_id == user.id))
    identities = (
        NotificationIdentity(
            provider=identity.provider,
            subject=identity.subject,
            claims=dict(identity.claims or {}),
        )
        for identity in result.scalars().all()
    )
    return collect_verified_notification_emails(user.email, identities)


async def create_account_link_intent(
    session: AsyncSession,
    *,
    flow_type: str,
    normalized_email: str,
    candidate_user_id: uuid.UUID,
    initiating_provider: str,
    initiating_subject: str,
    required_provider: str,
    browser_binding_hash: str,
    expires_at: datetime.datetime,
    initiating_claims: dict[str, Any] | None,
    created_ip: str | None,
    user_agent: str | None,
) -> uuid.UUID:
    result = await session.execute(
        text(
            "select health_compass.app_create_account_link_intent("
            ":flow_type, :normalized_email, :candidate_user_id, "
            ":initiating_provider, :initiating_subject, :required_provider, "
            ":browser_binding_hash, :expires_at, cast(:initiating_claims as jsonb), "
            ":created_ip, :user_agent)"
        ),
        {
            "flow_type": flow_type,
            "normalized_email": normalized_email,
            "candidate_user_id": candidate_user_id,
            "initiating_provider": initiating_provider,
            "initiating_subject": initiating_subject,
            "required_provider": required_provider,
            "browser_binding_hash": browser_binding_hash,
            "expires_at": expires_at,
            "initiating_claims": json.dumps(initiating_claims) if initiating_claims is not None else None,
            "created_ip": created_ip,
            "user_agent": user_agent,
        },
    )
    return result.scalar_one()
