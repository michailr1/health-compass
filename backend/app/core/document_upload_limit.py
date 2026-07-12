"""ASGI request-size boundary for document uploads.

Starlette's ``UploadFile`` safely spools large multipart parts instead of loading
all bytes into memory, but parsing still happens before route-level validation.
This middleware bounds the complete request body, including chunked requests,
before the multipart parser can consume unbounded temporary-disk space.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import Message, Receive, Scope, Send

MULTIPART_OVERHEAD_BYTES = 1024 * 1024


class _DocumentRequestTooLarge(Exception):
    pass


def _is_document_upload(scope: Scope) -> bool:
    if scope.get("type") != "http" or scope.get("method") != "POST":
        return False
    parts = str(scope.get("path", "")).strip("/").split("/")
    return len(parts) == 3 and parts[0] == "profiles" and parts[2] == "documents"


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None
    return None


class DocumentUploadLimitMiddleware:
    """Reject oversized document requests before multipart parsing."""

    def __init__(
        self,
        app: Callable[[Scope, Receive, Send], Awaitable[None]],
        *,
        max_body_bytes: int,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not _is_document_upload(scope):
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared is not None and declared > self.max_body_bytes:
            await self._reject(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                received += len(body)
                if received > self.max_body_bytes:
                    raise _DocumentRequestTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _DocumentRequestTooLarge:
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        state: dict[str, Any] = scope.get("state", {})
        request_id = state.get("request_id")
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "document_request_too_large",
                    "message": "Document upload request exceeds the safe size limit",
                    "request_id": request_id,
                }
            },
        )
        await response(scope, receive, send)
