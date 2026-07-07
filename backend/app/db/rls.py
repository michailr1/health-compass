"""PostgreSQL row security context helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def apply_user_context(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        text("select set_config('app.current_user_id', :value, true)"),
        {"value": str(user_id)},
    )


async def apply_session_context(session: AsyncSession, session_hash: str) -> None:
    await session.execute(
        text("select set_config('app.current_session_hash', :value, true)"),
        {"value": session_hash},
    )
