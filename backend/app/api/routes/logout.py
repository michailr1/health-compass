"""Browser logout route that clears the app session and upstream SSO session."""

from __future__ import annotations

import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import NONCE_COOKIE, STATE_COOKIE, VERIFIER_COOKIE
from app.core.config import settings
from app.core.oidc import get_discovery
from app.core.session_tokens import hash_token
from app.db.session import get_session
from app.models.user import AuthSession

router = APIRouter(prefix="/auth", tags=["auth"])


def _authentik_logout_url(discovery: dict) -> str:
    endpoint = discovery.get("end_session_endpoint")
    if not endpoint:
        return settings.frontend_url
    query = urlencode(
        {
            "client_id": settings.oidc_client_id,
            "post_logout_redirect_uri": settings.frontend_url,
        }
    )
    return f"{endpoint}?{query}"


@router.get("/logout")
async def browser_logout(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await session.execute(
            update(AuthSession)
            .where(AuthSession.session_token_hash == hash_token(token))
            .values(revoked_at=datetime.datetime.now(datetime.UTC))
        )
    discovery = await get_discovery()
    response = RedirectResponse(
        _authentik_logout_url(discovery),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie(settings.session_cookie_name, path="/health/api")
    response.delete_cookie(STATE_COOKIE, path="/health/api/auth")
    response.delete_cookie(NONCE_COOKIE, path="/health/api/auth")
    response.delete_cookie(VERIFIER_COOKIE, path="/health/api/auth")
    return response
