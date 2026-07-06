"""Pytest configuration and fixtures for Health Compass API tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Load .env file if present
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

# --- Safety guard: refuse to run against non-test databases ---
_db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://health_compass_test_app:test@127.0.0.1:5433/health_compass_test",
)
_db_name = _db_url.rsplit("/", 1)[-1].split("?")[0]

if not _db_name.endswith("_test"):
    raise RuntimeError(
        f"Refusing to run tests against database '{_db_name}'. "
        "Test database name must end with '_test'. "
        "Set DATABASE_URL environment variable to a test database."
    )


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def test_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session.

    Uses a separate test database. Each test gets a fresh session.
    """
    engine = create_async_engine(
        _db_url,
        echo=False,
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()
        await session.close()

    await engine.dispose()
