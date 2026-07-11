"""SQLAlchemy database session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

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


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield one database transaction for the complete request.

    RLS context is installed with PostgreSQL ``set_config(..., true)`` and is
    therefore transaction-local. Keeping a single explicit transaction around
    the request makes that lifetime visible and prevents later statements from
    silently running after an intermediate commit has cleared the context.
    """
    async with async_session_factory() as session:
        async with session.begin():
            yield session
