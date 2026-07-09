"""Initial personal workspace/profile bootstrap."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.rls import apply_user_context
from app.models.profile import HealthProfile, ProfileAccess
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_access import WorkspaceAccess


def _slug_from_email(email: str) -> str:
    left = email.split("@", 1)[0].lower()
    safe = "".join(ch if ch.isalnum() else "-" for ch in left).strip("-")
    return safe or "user"


async def ensure_personal_workspace(session: AsyncSession, user: User) -> None:
    """Create the first personal workspace and empty health profile if the user has none.

    Bootstrap must never insert synthetic medical observations, priorities, diagnoses,
    genetic findings, or measurements into a real user profile.
    """
    await apply_user_context(session, user.id)
    existing = await session.execute(
        select(WorkspaceAccess).where(WorkspaceAccess.user_id == user.id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return

    await apply_user_context(session, user.id)
    workspace = Workspace(
        name=f"{user.display_name or user.email} — Health Compass",
        slug=f"{_slug_from_email(user.email)}-{str(user.id)[:8]}",
        created_by_user_id=user.id,
    )
    session.add(workspace)
    await session.flush()

    await apply_user_context(session, user.id)
    session.add(
        WorkspaceAccess(
            workspace_id=workspace.id,
            user_id=user.id,
            access_level="owner",
        )
    )
    await session.flush()

    await apply_user_context(session, user.id)
    profile = HealthProfile(
        workspace_id=workspace.id,
        owner_user_id=user.id,
        display_name=user.display_name or user.email,
    )
    session.add(profile)
    await session.flush()

    await apply_user_context(session, user.id)
    session.add(
        ProfileAccess(
            profile_id=profile.id,
            user_id=user.id,
            access_level="owner",
        )
    )
    await session.flush()
