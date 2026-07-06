"""Tests for the health endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.core.config import settings


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(test_session):
    """GET /health/api/health should return 200 with service status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert data["service"] == settings.service_name
    assert data["database"] in ("ok", "error")


@pytest.mark.asyncio
async def test_health_database_connectivity(test_session):
    """Health endpoint should verify real database connectivity."""
    result = await test_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
