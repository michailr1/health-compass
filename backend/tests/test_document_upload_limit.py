"""Tests for the pre-parser document upload size boundary."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.core.document_upload_limit import DocumentUploadLimitMiddleware


def _app(max_body_bytes: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        DocumentUploadLimitMiddleware,
        max_body_bytes=max_body_bytes,
    )

    @app.post("/profiles/{profile_id}/documents")
    async def document_upload(profile_id: uuid.UUID, request: Request) -> dict[str, int]:
        body = await request.body()
        return {"bytes": len(body)}

    @app.post("/other")
    async def other(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"bytes": len(body)}

    return app


@pytest.mark.asyncio
async def test_content_length_rejected_before_endpoint_reads_body() -> None:
    app = _app(max_body_bytes=16)
    profile_id = uuid.uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/profiles/{profile_id}/documents",
            content=b"x" * 17,
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "document_request_too_large"


@pytest.mark.asyncio
async def test_chunked_body_is_counted_without_content_length() -> None:
    app = _app(max_body_bytes=16)
    profile_id = uuid.uuid4()

    async def chunks():
        yield b"x" * 10
        yield b"y" * 10

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/profiles/{profile_id}/documents",
            content=chunks(),
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "document_request_too_large"


@pytest.mark.asyncio
async def test_non_document_routes_are_not_affected() -> None:
    app = _app(max_body_bytes=16)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/other", content=b"x" * 32)

    assert response.status_code == 200
    assert response.json() == {"bytes": 32}
