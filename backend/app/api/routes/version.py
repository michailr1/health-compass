"""Version endpoint — returns service metadata."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.version import VersionResponse

router = APIRouter(tags=["version"])

# Compute commit once at startup from BUILD_COMMIT env var
_BUILD_COMMIT = settings.build_commit or "unknown"


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """Return service version and build metadata."""
    return VersionResponse(
        service=settings.service_name,
        version=settings.version,
        commit=_BUILD_COMMIT,
        environment=settings.environment,
    )
