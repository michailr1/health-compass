"""Direct Google OIDC authentication routes."""

from __future__ import annotations

import datetime
import secrets
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.oidc import build_authorization_url, exchange_code, get_discovery, validate_id_token
from app.core.session_tokens import hash_token, new_session_token
from app.db.rls import apply_session_context, apply_user_context
from app.db.session import get_session
from app.models.user import AuthSession, User, UserIdentity
from app.services.bootstrap import ensure_personal_workspace

router = APIRouter(prefix="/auth", tags=["auth"])
STATE_COOKIE = "hc_oidc_state"
NONCE_COOKIE = "hc_oidc_nonce"
VERIFIER_COOKIE = "hc_oidc_verifier"
GOOGLE_PROVIDER = "google"


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
        path="/api/auth",
    )


def _delete_oidc_cookies(response: RedirectResponse) -> None:
    response.delete_cookie(STATE_COOKIE, path="/api/auth")
    response.delete_cookie(NONCE_COOKIE, path="/api/auth")
    response.delete_cookie(VERIFIER_COOKIE, path="/api/auth")


async def _start_google_login() -> RedirectResponse:
    try:
        discovery = await get_discovery()
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        location = build_authorization_url(discovery, _redirect_uri(), state, nonce, code_verifier)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google authentication is temporarily unavailable",
        ) from exc

    response = RedirectResponse(location)
    _set_short_cookie(response, STATE_COOKIE, state)
    _set_short_cookie(response, NONCE_COOKIE, nonce)
    _set_short_cookie(response, VERIFIER_COOKIE, code_verifier)
    return response


async def _lookup_identity_user_id(
    session: AsyncSession,
    provider: str,
    subject: str,
) -> uuid.UUID | None:
    result = await session.execute(
        text("select health_compass.app_lookup_identity_user_id(:provider, :subject)"),
        {"provider": provider, "subject": subject},
    )
    return result.scalar_one_or_none()


@router.get("/login")
async def login() -> RedirectResponse:
    return await _start_google_login()


@router.get("/provider/google")
async def login_google() -> RedirectResponse:
    return await _start_google_login()


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

    try:
        discovery = await get_discovery()
        token_response = await exchange_code(discovery, code, _redirect_uri(), code_verifier)
        id_token = token_response.get("id_token")
        if not id_token:
            raise ValueError("OIDC id_token missing")
        claims = await validate_id_token(discovery, id_token, nonce)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication response is invalid",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google authentication provider request failed",
        ) from exc

    subject = str(claims.get("sub") or "")
    email = str(claims.get("email") or "")
    if not subject or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OIDC subject or email missing")
    if claims.get("email_verified") is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OIDC email is not verified")

    identity_user_id = await _lookup_identity_user_id(session, GOOGLE_PROVIDER, subject)
    if identity_user_id is None:
        user_id = uuid.uuid4()
        await apply_user_context(session, user_id)
        user = User(
            id=user_id,
            email=email.strip().lower(),
            display_name=claims.get("name") or claims.get("preferred_username") or email,
            status="active",
        )
        session.add(user)
        await session.flush()
        identity = UserIdentity(
            user_id=user.id,
            provider=GOOGLE_PROVIDER,
            subject=subject,
            issuer=settings.oidc_issuer or "",
            claims=claims,
            last_seen_at=datetime.datetime.now(datetime.UTC),
        )
        session.add(identity)
    else:
        await apply_user_context(session, identity_user_id)
        user_result = await session.execute(select(User).where(User.id == identity_user_id))
        user = user_result.scalar_one()
        identity_result = await session.execute(
            select(UserIdentity).where(UserIdentity.provider == GOOGLE_PROVIDER, UserIdentity.subject == subject)
        )
        identity = identity_result.scalar_one()
        user.email = email.strip().lower()
        user.display_name = claims.get("name") or user.display_name
        identity.claims = claims
        identity.last_seen_at = datetime.datetime.now(datetime.UTC)

    await ensure_personal_workspace(session, user)

    token = new_session_token()
    token_hash = hash_token(token)
    await apply_session_context(session, token_hash)
    session.add(
        AuthSession(
            user_id=user.id,
            session_token_hash=token_hash,
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
        path="/api",
    )
    return response


async def _logout_response(request: Request, session: AsyncSession) -> RedirectResponse:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        token_hash = hash_token(token)
        await apply_session_context(session, token_hash)
        await session.execute(
            update(AuthSession)
            .where(AuthSession.session_token_hash == token_hash)
            .values(revoked_at=datetime.datetime.now(datetime.UTC))
        )
    response = RedirectResponse(settings.frontend_url, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.session_cookie_name, path="/api")
    _delete_oidc_cookies(response)
    return response


@router.get("/logout")
async def logout_get(request: Request, session: AsyncSession = Depends(get_session)) -> RedirectResponse:
    return await _logout_response(request, session)


@router.post("/logout")
async def logout_post(request: Request, session: AsyncSession = Depends(get_session)) -> RedirectResponse:
    return await _logout_response(request, session)
