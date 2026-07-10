"""HC-013 active-session listing, revocation, and token rotation."""

from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.session_tokens import hash_token, new_session_token
from app.db.session import get_session
from app.models.user import AuthSession, User
from app.schemas.session_management import (
    AuthSessionSummary,
    SessionRevocationResponse,
    SessionRotationResponse,
)

router = APIRouter(prefix="/auth/sessions", tags=["auth-sessions"])


def _current_token_hash(session_cookie: str | None) -> str:
    if not session_cookie:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session management requires a browser session",
        )
    return hash_token(session_cookie)


@router.get("", response_model=list[AuthSessionSummary])
async def list_active_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
):
    current_hash = _current_token_hash(session_cookie)
    now = datetime.datetime.now(datetime.UTC)
    result = await session.execute(
        select(AuthSession)
        .where(
            AuthSession.user_id == current_user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .order_by(AuthSession.created_at.desc())
    )
    sessions = list(result.scalars())
    return [
        AuthSessionSummary(
            id=item.id,
            is_current=item.session_token_hash == current_hash,
            ip_address=item.ip_address,
            user_agent=item.user_agent,
            created_at=item.created_at,
            expires_at=item.expires_at,
        )
        for item in sessions
    ]


@router.delete("/{session_id}", response_model=SessionRevocationResponse)
async def revoke_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
):
    current_hash = _current_token_hash(session_cookie)
    result = await session.execute(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == current_user.id,
            AuthSession.revoked_at.is_(None),
        )
    )
    auth_session = result.scalar_one_or_none()
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    is_current = auth_session.session_token_hash == current_hash
    auth_session.revoked_at = datetime.datetime.now(datetime.UTC)
    await session.flush()

    payload = SessionRevocationResponse(
        session_id=auth_session.id,
        current_session=is_current,
    ).model_dump(mode="json")
    response = JSONResponse(payload)
    if is_current:
        response.delete_cookie(settings.session_cookie_name, path="/api")
    return response


@router.post("/current/rotate", response_model=SessionRotationResponse)
async def rotate_current_session(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
):
    current_hash = _current_token_hash(session_cookie)
    result = await session.execute(
        select(AuthSession).where(
            AuthSession.user_id == current_user.id,
            AuthSession.session_token_hash == current_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.datetime.now(datetime.UTC),
        )
    )
    auth_session = result.scalar_one_or_none()
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    new_token = new_session_token()
    auth_session.session_token_hash = hash_token(new_token)
    await session.flush()

    response = JSONResponse(
        SessionRotationResponse(session_id=auth_session.id).model_dump(mode="json")
    )
    remaining_seconds = max(
        1,
        int((auth_session.expires_at - datetime.datetime.now(datetime.UTC)).total_seconds()),
    )
    response.set_cookie(
        settings.session_cookie_name,
        new_token,
        max_age=remaining_seconds,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/api",
    )
    return response
