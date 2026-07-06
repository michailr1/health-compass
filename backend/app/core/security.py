"""Security module — auth-ready dependency for future authentication.

On this stage all protected endpoints return 401 Unauthorized.
No real authentication is implemented yet.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer

from app.schemas.errors import ErrorDetail, ErrorResponse

# Placeholder — will be replaced by real OIDC validation
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    token: str | None = Depends(security_scheme),
) -> str:
    """Dependency that returns the current authenticated user.

    Currently always raises 401 with standardised error format.
    In the future this will validate a JWT from Authentik/OIDC
    and return a user identifier.
    """
    request_id = getattr(request.state, "request_id", None)
    detail = ErrorDetail(
        code="unauthorized",
        message="Authentication required",
        request_id=request_id,
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ErrorResponse(error=detail).model_dump(),
    )


async def require_authentication(
    current_user: str = Depends(get_current_user),
) -> str:
    """Alias for get_current_user — semantic name for route dependencies."""
    return current_user
