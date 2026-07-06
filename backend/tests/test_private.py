"""Tests for the private/ping endpoint (must return 401)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.request_id import REQUEST_ID_HEADER
from app.main import app


@pytest.mark.asyncio
async def test_private_ping_returns_401(test_session):
    """GET /health/api/private/ping should return 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/api/private/ping")
    assert response.status_code == 401
    data = response.json()
    # FastAPI wraps HTTPException detail under 'detail' key
    assert "detail" in data
    assert data["detail"]["error"]["code"] == "unauthorized"
    assert data["detail"]["error"]["message"] == "Authentication required"
    assert REQUEST_ID_HEADER in response.headers
    body = response.text
    assert "Traceback" not in body
    assert "File \"" not in body
