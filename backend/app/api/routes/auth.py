"""OIDC authentication routes."""

from __future__ import annotations

import datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.oidc import build_authorization_url, exchange_code, get_discovery, validate_id_token
from app.core.session_tokens import hash_token, new_session_token
from app.db.rls import apply_user_context
from app.db.session import get_session
from app.models.user import AuthSession, User, UserIdentity
from app.services.bootstrap import ensure_personal_workspace

router = APIRouter(prefix="/auth", tags=["auth"])
STATE_COOKIE = "hc_oidc_state"
NONCE_COOKIE = "hc_oidc_nonce"
VERIFIER_COOKIE = "hc_oidc_verifier"


def _redirect_uri() -> str:
    if not settings.oidc_redirect_uri:
        raise RuntimeError("OIDC_REDIRECT_URI is not configured")
    return settings.oidc_redirect_uri


def _set_short_cookie(response: RedirectResponse, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=600,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/health/api/auth",
    )


def _delete_oidc_cookies(response: RedirectResponse) -> None:
    response.delete_cookie(STATE_COOKIE, path="/health/api/auth")
    response.delete_cookie(NONCE_COOKIE, path="/health/api/auth")
    response.delete_cookie(VERIFIER_COOKIE, path="/health/api/auth")


@router.get("/login")
async def login() -> RedirectResponse:
    discovery = await get_discovery()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    location = build_authorization_url(discovery, _redirect_uri(), state, nonce, code_verifier)
    response = RedirectResponse(location)
    _set_short_cookie(response, STATE_COOKIE, state)
    _set_short_cookie(response, NONCE_COOKIE, nonce)
    _set_short_cookie(response, VERIFIER_COOKIE, code_verifier)
    return response


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if error:
        detail = error_description or error
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OIDC error: {detail}")
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OIDC code or state missing")

    expected_state = request.cookies.get(STATE_COOKIE)
    nonce = request.cookies.get(NONCE_COOKIE)
    code_verifier = request.cookies.get(VERIFIER_COOKIE)
    if not expected_state or not nonce or not code_verifier or not secrets.compare_digest(expected_state, state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OIDC state")

    discovery = await get_discovery()
    token_response = await exchange_code(discovery, code, _redirect_uri(), code_verifier)
    id_token = token_response.get("id_token")
    if not id_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OIDC id_token missing")
    claims = await validate_id_token(discovery, id_token, nonce)

    subject = str(claims.get("sub") or "")
    email = str(claims.get("email") or "")
    if not subject or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OIDC subject or email missing")

    identity_result = await session.execute(
        select(UserIdentity).where(UserIdentity.provider == "authentik", UserIdentity.subject == subject)
    )
    identity = identity_result.scalar_one_or_none()
    if identity is None:
        user = User(
            email=email.lower(),
            display_name=claims.get("name") or claims.get("preferred_username") or email,
            status="active",
        )
        session.add(user)
        await session.flush()
        identity = UserIdentity(
            user_id=user.id,
            provider="authentik",
            subject=subject,
            issuer=settings.oidc_issuer or "",
            claims=claims,
            last_seen_at=datetime.datetime.now(datetime.UTC),
        )
        session.add(identity)
    else:
        await apply_user_context(session, identity.user_id)
        user_result = await session.execute(select(User).where(User.id == identity.user_id))
        user = user_result.scalar_one()
        user.email = email.lower()
        user.display_name = claims.get("name") or user.display_name
        identity.claims = claims
        identity.last_seen_at = datetime.datetime.now(datetime.UTC)

    await ensure_personal_workspace(session, user)

    token = new_session_token()
    session.add(
        AuthSession(
            user_id=user.id,
            session_token_hash=hash_token(token),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(seconds=settings.session_ttl_seconds),
        )
    )

    response = RedirectResponse(settings.frontend_url)
    _delete_oidc_cookies(response)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/health/api",
    )
    return response


@router.post("/logout")
async def logout(request: Request, session: AsyncSession = Depends(get_session)) -> RedirectResponse:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await session.execute(
            update(AuthSession)
            .where(AuthSession.session_token_hash == hash_token(token))
            .values(revoked_at=datetime.datetime.now(datetime.UTC))
        )
    response = RedirectResponse(settings.frontend_url, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.session_cookie_name, path="/health/api")
    return response
