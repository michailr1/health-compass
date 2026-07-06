"""Version endpoint — returns service metadata."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.version import VersionResponse

router = APIRouter(tags=["version"])

_REPO_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _get_git_commit() -> str:
    """Return the short SHA of the current Git commit."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=_REPO_DIR,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """Return service version and build metadata."""
    return VersionResponse(
        service=settings.service_name,
        version=settings.version,
        commit=_get_git_commit(),
        environment=settings.environment,
    )
