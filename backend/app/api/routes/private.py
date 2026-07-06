"""Private endpoints — require authentication.

On this stage all private endpoints return 401 Unauthorized.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_authentication

router = APIRouter(tags=["private"])


@router.get("/private/ping")
async def private_ping(
    _: str = Depends(require_authentication),
) -> None:
    """Test endpoint for authenticated access.

    Currently always returns 401 Unauthorized.
    """
    # This code is never reached because require_authentication raises 401
