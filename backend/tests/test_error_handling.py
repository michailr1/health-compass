"""Tests for error handling and request ID."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.request_id import REQUEST_ID_HEADER
from app.main import app


@pytest.mark.asyncio
async def test_unknown_route_returns_404(test_session):
    """GET /nonexistent should return structured 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/nonexistent")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_request_id_is_returned(test_session):
    """Response should include X-Request-ID header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert REQUEST_ID_HEADER in response.headers
    assert len(response.headers[REQUEST_ID_HEADER]) == 36  # UUID length


@pytest.mark.asyncio
async def test_client_request_id_is_respected(test_session):
    """If client sends a valid UUID as X-Request-ID, it should be reused."""
    client_id = "550e8400-e29b-41d4-a716-446655440000"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health",
            headers={REQUEST_ID_HEADER: client_id},
        )
    assert response.headers[REQUEST_ID_HEADER] == client_id


@pytest.mark.asyncio
async def test_no_stack_trace_in_production(test_session):
    """Production should not expose stack traces."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/private/ping")
    assert response.status_code == 401
    body = response.text
    assert "Traceback" not in body
    assert "File \"" not in body
