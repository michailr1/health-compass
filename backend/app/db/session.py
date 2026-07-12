"""SQLAlchemy session management and rollback cleanup hooks."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

RollbackCleanup = Callable[[], Awaitable[None]]
_ROLLBACK_CLEANUPS_KEY = "health_compass.rollback_cleanups"

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    hide_parameters=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def register_rollback_cleanup(
    session: AsyncSession,
    cleanup: RollbackCleanup,
) -> str:
    """Register an async cleanup that runs only if the request transaction fails."""

    token = uuid.uuid4().hex
    callbacks = session.info.setdefault(_ROLLBACK_CLEANUPS_KEY, {})
    callbacks[token] = cleanup
    return token


def discard_rollback_cleanup(session: AsyncSession, token: str) -> None:
    """Discard a callback after the external artifact was already removed."""

    callbacks = session.info.get(_ROLLBACK_CLEANUPS_KEY)
    if not callbacks:
        return
    callbacks.pop(token, None)
    if not callbacks:
        session.info.pop(_ROLLBACK_CLEANUPS_KEY, None)


async def _run_rollback_cleanups(session: AsyncSession) -> None:
    callbacks = session.info.pop(_ROLLBACK_CLEANUPS_KEY, {})
    for cleanup in reversed(list(callbacks.values())):
        try:
            await cleanup()
        except Exception:  # pragma: no cover - cleanup implementations are tested separately
            # Do not leak paths, filenames or callback exception text into logs.
            logger.error("request_rollback_cleanup_failed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield one database transaction for the complete request.

    RLS context is installed with PostgreSQL ``set_config(..., true)`` and is
    therefore transaction-local. Keeping a single explicit transaction around
    the request makes that lifetime visible and prevents later statements from
    silently running after an intermediate commit has cleared the context.

    External side effects such as private quarantine objects can register an
    async rollback cleanup. The callback runs when route execution, request
    cancellation or the final database commit fails, preventing untracked
    orphan artifacts.
    """

    async with async_session_factory() as session:
        try:
            async with session.begin():
                yield session
        except BaseException:
            await _run_rollback_cleanups(session)
            raise
        else:
            session.info.pop(_ROLLBACK_CLEANUPS_KEY, None)
