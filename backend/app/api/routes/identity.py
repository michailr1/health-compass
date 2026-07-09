"""Identity, workspace, profile, and connected sign-in method APIs."""

from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.profile import DashboardSnapshot, HealthProfile
from app.models.user import User, UserIdentity
from app.models.workspace import Workspace
from app.schemas.identity import (
    DashboardSnapshotResponse,
    ProfileResponse,
    UserResponse,
    WorkspaceResponse,
)
from app.services.health_profile import build_readiness

router = APIRouter(tags=["identity"])


class SignInMethodResponse(BaseModel):
    id: uuid.UUID
    provider: str
    label: str
    verified: bool
    connected_at: datetime.datetime
    last_seen_at: datetime.datetime | None
    can_remove: bool


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/auth/identities", response_model=list[SignInMethodResponse])
async def list_sign_in_methods(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SignInMethodResponse]:
    result = await session.execute(
        select(UserIdentity)
        .where(UserIdentity.user_id == current_user.id)
        .order_by(UserIdentity.created_at)
    )
    identities = list(result.scalars().all())
    can_remove = len(identities) > 1
    response: list[SignInMethodResponse] = []
    for identity in identities:
        claims = identity.claims or {}
        if identity.provider == "google":
            label = str(claims.get("email") or "Google")
            verified = claims.get("email_verified") is True
        elif identity.provider == "email":
            label = identity.subject
            verified = claims.get("email_verified") is True
        else:
            label = identity.provider
            verified = False
        response.append(
            SignInMethodResponse(
                id=identity.id,
                provider=identity.provider,
                label=label,
                verified=verified,
                connected_at=identity.created_at,
                last_seen_at=identity.last_seen_at,
                can_remove=can_remove,
            )
        )
    return response


@router.get("/workspaces", response_model=list[WorkspaceResponse])
async def list_workspaces(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Workspace]:
    result = await session.execute(select(Workspace).order_by(Workspace.name))
    return list(result.scalars().all())


@router.get("/profiles", response_model=list[ProfileResponse])
async def list_profiles(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[HealthProfile]:
    result = await session.execute(select(HealthProfile).order_by(HealthProfile.display_name))
    return list(result.scalars().all())


@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(select(HealthProfile).where(HealthProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    readiness = await build_readiness(session, profile)
    return {
        "id": profile.id,
        "workspace_id": profile.workspace_id,
        "owner_user_id": profile.owner_user_id,
        "display_name": profile.display_name,
        "date_of_birth": profile.date_of_birth,
        "sex": profile.sex,
        "height_cm": profile.height_cm,
        "timezone": profile.timezone,
        "readiness": readiness,
    }


@router.get("/profiles/{profile_id}/dashboard", response_model=DashboardSnapshotResponse)
async def get_profile_dashboard(
    profile_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DashboardSnapshot:
    result = await session.execute(
        select(DashboardSnapshot)
        .where(DashboardSnapshot.profile_id == profile_id)
        .order_by(desc(DashboardSnapshot.created_at))
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
    return snapshot
