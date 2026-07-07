"""Provider-specific OIDC login entrypoint."""

from __future__ import annotations

import secrets

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.api.routes.auth import NONCE_COOKIE, STATE_COOKIE, VERIFIER_COOKIE, _redirect_uri, _set_short_cookie
from app.core.oidc import build_authorization_url, get_discovery

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/provider/google")
async def provider_login() -> RedirectResponse:
    discovery = await get_discovery()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    location = build_authorization_url(discovery, _redirect_uri(), state, nonce, verifier)
    location = location + "&" + "source" + "=" + "google"
    response = RedirectResponse(location)
    _set_short_cookie(response, STATE_COOKIE, state)
    _set_short_cookie(response, NONCE_COOKIE, nonce)
    _set_short_cookie(response, VERIFIER_COOKIE, verifier)
    return response
