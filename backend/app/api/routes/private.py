"""Private endpoints — require authentication.

On this stage all private endpoints return 401 Unauthorized.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.security import require_authentication
from app.schemas.errors import ErrorDetail, ErrorResponse

router = APIRouter(tags=["private"])


@router.get("/private/ping")
async def private_ping(
    request: Request,
    _: str = Depends(require_authentication),
) -> JSONResponse:
    """Test endpoint for authenticated access.

    Currently always returns 401 Unauthorized.
    The require_authentication dependency raises HTTPException(401)
    before this handler is reached.
    """
    # This code is never reached — require_authentication raises 401
    request_id = getattr(request.state, "request_id", None)
    detail = ErrorDetail(
        code="unauthorized",
        message="Authentication required",
        request_id=request_id,
    )
    return JSONResponse(
        status_code=401,
        content=ErrorResponse(error=detail).model_dump(),
    )
