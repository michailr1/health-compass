"""Health check endpoint — verifies service and database connectivity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_session
from app.schemas.errors import ErrorDetail, ErrorResponse
from app.schemas.health import HealthResponse

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=None)
async def health_check(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Return service health status.

    Verifies database connectivity with a simple query.
    Returns 503 if the database is unreachable.
    """
    db_status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "Health check database failure",
            extra={"request_id": request_id},
        )
        db_status = "error"

    if db_status == "error":
        request_id = getattr(request.state, "request_id", None)
        detail = ErrorDetail(
            code="service_unavailable",
            message="Database is unavailable",
            request_id=request_id,
        )
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(error=detail).model_dump(),
        )

    return JSONResponse(
        status_code=200,
        content=HealthResponse(
            status="ok",
            service=settings.service_name,
            database="ok",
        ).model_dump(),
    )
