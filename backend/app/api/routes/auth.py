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

router = APIRouter(prefix="/auth", tags=["auth"])
STATE_COOKIE = "hc_oidc_state"
NONCE_COOKIE = "hc_oidc_nonce"


def _redirect_uri(request: Request) -> str:
    return str(request.url_for("auth_callback"))


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


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    discovery = await get_discovery()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    location = build_authorization_url(discovery, _redirect_uri(request), state, nonce)
    response = RedirectResponse(location)
    _set_short_cookie(response, STATE_COOKIE, state)
    _set_short_cookie(response, NONCE_COOKIE, nonce)
    return response


@router.get("/callback", name="auth_callback")
async def callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    expected_state = request.cookies.get(STATE_COOKIE)
    nonce = request.cookies.get(NONCE_COOKIE)
    if not expected_state or not nonce or not secrets.compare_digest(expected_state, state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OIDC state")

    discovery = await get_discovery()
    token_response = await exchange_code(discovery, code, _redirect_uri(request))
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
    response.delete_cookie(STATE_COOKIE, path="/health/api/auth")
    response.delete_cookie(NONCE_COOKIE, path="/health/api/auth")
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
