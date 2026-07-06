"""Tests for the health endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.core.request_id import REQUEST_ID_HEADER
from app.main import app


@pytest.mark.asyncio
async def test_health_healthy_database(test_session):
    """GET /health/api/health should return 200 with ok status when DB is up."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == settings.service_name
    assert data["database"] == "ok"


@pytest.mark.asyncio
async def test_health_database_connectivity(test_session):
    """Health endpoint should verify real database connectivity."""
    result = await test_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_health_db_failure_returns_503():
    """When database is unreachable, health should return 503 degraded."""

    from app.db.session import get_session
    from app.main import app as main_app

    class BrokenSession:
        """A session that fails on any execute call."""

        def __init__(self):
            self._closed = False

        async def execute(self, *args, **kwargs):
            raise ConnectionError("Simulated database failure")

        async def close(self):
            self._closed = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            await self.close()

    async def broken_get_session():
        yield BrokenSession()  # type: ignore

    main_app.dependency_overrides[get_session] = broken_get_session

    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/api/health")

    main_app.dependency_overrides.clear()

    assert response.status_code == 503
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "service_unavailable"
    assert data["error"]["message"] == "Database is unavailable"
    assert REQUEST_ID_HEADER in response.headers
    body = response.text
    assert "Traceback" not in body
    assert "File \"" not in body
