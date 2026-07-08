"""Pytest configuration and fixtures for Health Compass API tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Load .env file if present, without overriding explicitly supplied test values.
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

# Unit tests must be importable without a developer .env. Database-dependent
# tests run only when TEST_DATABASE_URL is supplied explicitly.
_test_db_url = os.environ.get("TEST_DATABASE_URL")
_import_db_url = _test_db_url or (
    "postgresql+asyncpg://health_compass_test_app:test@127.0.0.1:5433/"
    "health_compass_test"
)
os.environ.setdefault("DATABASE_URL", _import_db_url)
os.environ.setdefault(
    "DATABASE_MIGRATOR_URL",
    "postgresql+psycopg://health_compass_test_migrator:test@127.0.0.1:5433/"
    "health_compass_test",
)

_db_name = _import_db_url.rsplit("/", 1)[-1].split("?", 1)[0]
if not _db_name.endswith("_test"):
    raise RuntimeError(
        f"Refusing to run tests against database '{_db_name}'. "
        "Test database name must end with '_test'."
    )


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def test_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a session for explicitly configured PostgreSQL integration tests."""
    if not _test_db_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(
        _test_db_url,
        echo=False,
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with async_session() as session:
            yield session
            await session.rollback()
    finally:
        await engine.dispose()
