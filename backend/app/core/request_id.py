"""Request ID middleware — trace each request through the system."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request.

    If the client sends a valid UUID in X-Request-ID, it is reused.
    Otherwise a new UUIDv4 is generated.
    The request ID is returned in the response header and stored in
    ``request.state.request_id`` for logging and audit.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        client_id = request.headers.get(REQUEST_ID_HEADER, "")
        try:
            request_id = str(uuid.UUID(client_id))
        except (ValueError, AttributeError):
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
