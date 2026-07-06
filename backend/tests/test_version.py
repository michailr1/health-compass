"""Tests for the version endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings


@pytest.mark.asyncio
async def test_version_endpoint_returns_200(test_session):
    """GET /health/api/version should return 200 with service metadata."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/api/version")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == settings.service_name
    assert data["version"] == settings.version
    assert data["commit"] != ""
    assert data["environment"] == settings.environment
