"""Shared API dependencies."""

from __future__ import annotations

import datetime
import uuid

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.session_tokens import hash_token
from app.db.rls import apply_session_context, apply_user_context
from app.db.session import get_session
from app.models.user import AuthSession, User


async def _load_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    await apply_user_context(session, user_id)
    result = await session.execute(select(User).where(User.id == user_id, User.status == "active"))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return user


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    dev_user_id: str | None = Header(default=None, alias="X-Health-Compass-User-Id"),
) -> User:
    """Return the current local user and apply DB row-security context."""
    if session_cookie:
        token_hash = hash_token(session_cookie)
        await apply_session_context(session, token_hash)
        result = await session.execute(
            select(AuthSession).where(
                AuthSession.session_token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.datetime.now(datetime.UTC),
            )
        )
        auth_session = result.scalar_one_or_none()
        if auth_session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
        return await _load_user(session, auth_session.user_id)

    if settings.allow_dev_auth and settings.is_development and request.client:
        if request.client.host not in {"127.0.0.1", "::1", "localhost"}:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Dev auth is local only")
        if dev_user_id:
            try:
                user_id = uuid.UUID(dev_user_id)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user id") from exc
            return await _load_user(session, user_id)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
