"""Shared API dependencies."""

from __future__ import annotations

import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.rls import apply_user_context
from app.db.session import get_session
from app.models.user import User


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    dev_user_id: str | None = Header(default=None, alias="X-Health-Compass-User-Id"),
) -> User:
    """Return the current local user and apply DB row-security context.

    Production OIDC session support will replace the temporary header path.
    The header path is disabled unless ALLOW_DEV_AUTH=true.
    """
    if not settings.allow_dev_auth or not dev_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        user_id = uuid.UUID(dev_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user id") from exc

    await apply_user_context(session, user_id)
    result = await session.execute(select(User).where(User.id == user_id, User.status == "active"))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return user
