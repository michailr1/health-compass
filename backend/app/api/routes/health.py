"""Health check endpoint — verifies service and database connectivity."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    session: AsyncSession = Depends(get_session),
) -> HealthResponse:
    """Return service health status.

    Verifies database connectivity with a simple query.
    """
    db_status = "ok"
    try:
        result = await session.execute(text("SELECT 1"))
        await result.fetchone()
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        service=settings.service_name,
        database=db_status,
    )
