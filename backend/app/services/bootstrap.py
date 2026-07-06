"""Initial personal workspace/profile bootstrap."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.rls import apply_user_context
from app.models.profile import DashboardSnapshot, HealthProfile, ProfileAccess
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_access import WorkspaceAccess

INITIAL_SUMMARY = {
    "observationIndex": 72,
    "avgSleep": {"hours": 6, "minutes": 39},
    "shortNightsPct": 60,
    "activeDays": 288,
    "geneticPositions": 630790,
}

INITIAL_PRIORITIES = [
    {
        "id": "fvl",
        "title": "Подтвердить предполагаемый Factor V Leiden",
        "description": "Маркер F5 rs6025 требует клинического подтверждения.",
        "priority": "high",
    },
    {
        "id": "sleep",
        "title": "Улучшить продолжительность и регулярность сна",
        "description": "60% ночей короче 7 часов.",
        "priority": "medium",
    },
    {
        "id": "activity",
        "title": "Вернуть повседневную активность",
        "description": "Шаги снижены за последние 30 дней.",
        "priority": "medium",
    },
]


def _slug_from_email(email: str) -> str:
    left = email.split("@", 1)[0].lower()
    safe = "".join(ch if ch.isalnum() else "-" for ch in left).strip("-")
    return safe or "user"


async def ensure_personal_workspace(session: AsyncSession, user: User) -> None:
    """Create the first personal workspace/profile/dashboard if user has none."""
    await apply_user_context(session, user.id)
    existing = await session.execute(select(WorkspaceAccess).where(WorkspaceAccess.user_id == user.id).limit(1))
    if existing.scalar_one_or_none() is not None:
        return

    workspace = Workspace(
        name=f"{user.display_name or user.email} — Health Compass",
        slug=f"{_slug_from_email(user.email)}-{str(user.id)[:8]}",
        created_by_user_id=user.id,
    )
    session.add(workspace)
    await session.flush()

    session.add(WorkspaceAccess(workspace_id=workspace.id, user_id=user.id, access_level="owner"))

    profile = HealthProfile(
        workspace_id=workspace.id,
        owner_user_id=user.id,
        display_name=user.display_name or user.email,
    )
    session.add(profile)
    await session.flush()

    session.add(ProfileAccess(profile_id=profile.id, user_id=user.id, access_level="owner"))
    session.add(
        DashboardSnapshot(
            profile_id=profile.id,
            summary=INITIAL_SUMMARY,
            priorities=INITIAL_PRIORITIES,
            source_label="initial-dashboard",
        )
    )
