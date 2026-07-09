"""Direct Google OIDC authentication and Google-confirmed linking routes."""

from __future__ import annotations

import datetime
import json
import secrets
import uuid
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_linking import hash_secret, new_browser_binding
from app.core.config import settings
from app.core.magic_links import normalize_email, send_account_linked_notifications
from app.core.oidc import build_authorization_url, exchange_code, get_discovery, validate_id_token
from app.core.session_tokens import hash_token, new_session_token
from app.db.rls import apply_session_context, apply_user_context
from app.db.session import get_session
from app.models.user import AuthSession, User, UserIdentity
from app.services.account_linking import (
    create_account_link_intent,
    lookup_verified_email_candidate,
    verified_notification_emails,
)
from app.services.bootstrap import ensure_personal_workspace

router = APIRouter(prefix="/auth", tags=["auth"])
STATE_COOKIE = "hc_oidc_state"
NONCE_COOKIE = "hc_oidc_nonce"
VERIFIER_COOKIE = "hc_oidc_verifier"
PURPOSE_COOKIE = "hc_oidc_purpose"
LINK_INTENT_COOKIE = "hc_oidc_link_intent"
GOOGLE_PROVIDER = "google"
EMAIL_PROVIDER = "email"
LOGIN_PURPOSE = "login"
LINK_PURPOSE = "account_link"


def _redirect_uri() -> str:
    if not settings.oidc_redirect_uri:
        raise RuntimeError("OIDC_REDIRECT_URI is not configured")
    return settings.oidc_redirect_uri


def _frontend_url(path: str, query: dict[str, str] | None = None) -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query or {}), ""))


def _set_short_cookie(response: RedirectResponse, name: str, value: str) -> None:
    response.set_cookie(name, value, max_age=600, secure=True, httponly=True, samesite="lax", path="/api/auth")


def _set_account_link_cookie(response: RedirectResponse, value: str) -> None:
    response.set_cookie(
        settings.account_link_cookie_name,
        value,
        max_age=settings.account_link_intent_ttl_seconds,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/api/auth",
    )


def _delete_oidc_cookies(response: RedirectResponse) -> None:
    for name in (STATE_COOKIE, NONCE_COOKIE, VERIFIER_COOKIE, PURPOSE_COOKIE, LINK_INTENT_COOKIE):
        response.delete_cookie(name, path="/api/auth")


async def _build_google_authorization() -> tuple[str, str, str, str]:
    discovery = await get_discovery()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    location = build_authorization_url(discovery, _redirect_uri(), state, nonce, code_verifier)
    return location, state, nonce, code_verifier


async def _start_google_login() -> RedirectResponse:
    try:
        location, state, nonce, code_verifier = await _build_google_authorization()
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Google authentication is temporarily unavailable") from exc
    response = RedirectResponse(location)
    _set_short_cookie(response, STATE_COOKIE, state)
    _set_short_cookie(response, NONCE_COOKIE, nonce)
    _set_short_cookie(response, VERIFIER_COOKIE, code_verifier)
    _set_short_cookie(response, PURPOSE_COOKIE, LOGIN_PURPOSE)
    return response


async def _lookup_identity_user_id(session: AsyncSession, provider: str, subject: str) -> uuid.UUID | None:
    result = await session.execute(
        text("select health_compass.app_lookup_identity_user_id(:provider, :subject)"),
        {"provider": provider, "subject": subject},
    )
    return result.scalar_one_or_none()


async def _record_link_audit(
    session: AsyncSession,
    request: Request,
    *,
    event_type: str,
    result: str,
    intent_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> None:
    await session.execute(
        text(
            "select health_compass.app_record_account_link_audit("
            ":event_type, :result, :intent_id, :actor_user_id, :ip, :user_agent, cast(:metadata as jsonb))"
        ),
        {
            "event_type": event_type,
            "result": result,
            "intent_id": intent_id,
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "metadata": json.dumps(metadata or {}),
        },
    )


async def _create_session_response(session: AsyncSession, request: Request, user_id: uuid.UUID) -> RedirectResponse:
    await apply_user_context(session, user_id)
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=409, detail="Account is unavailable")
    token = new_session_token()
    token_hash = hash_token(token)
    await apply_session_context(session, token_hash)
    session.add(
        AuthSession(
            user_id=user.id,
            session_token_hash=token_hash,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=settings.session_ttl_seconds),
        )
    )
    response = RedirectResponse(settings.frontend_url, status_code=303)
    _delete_oidc_cookies(response)
    response.delete_cookie(settings.account_link_cookie_name, path="/api/auth")
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


async def _notify_linked_addresses(
    session: AsyncSession,
    request: Request,
    *,
    user: User,
    intent_id: uuid.UUID,
) -> None:
    recipients = await verified_notification_emails(session, user)
    failures = await send_account_linked_notifications(
        recipients,
        ("Google", "Email Magic Link"),
    )
    if failures:
        await _record_link_audit(
            session,
            request,
            event_type="identity.link_notification_failed",
            result="partial" if len(failures) < len(recipients) else "error",
            intent_id=intent_id,
            actor_user_id=user.id,
            metadata={
                "recipient_count": len(recipients),
                "failure_count": len(failures),
            },
        )


@router.get("/login")
async def login() -> RedirectResponse:
    return await _start_google_login()


@router.get("/provider/google")
async def login_google() -> RedirectResponse:
    return await _start_google_login()


@router.get("/link/google/start")
async def start_google_link(
    request: Request,
    intent_id: uuid.UUID = Query(),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not settings.account_linking_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    browser_binding = request.cookies.get(settings.account_link_cookie_name)
    if not browser_binding:
        raise HTTPException(status_code=400, detail="Link session is missing")
    try:
        location, state, nonce, code_verifier = await _build_google_authorization()
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Google authentication is temporarily unavailable") from exc
    prepared = await session.execute(
        text(
            "select health_compass.app_prepare_google_link("
            ":intent_id, :browser_hash, :state_hash, :nonce_hash, :pkce_hash)"
        ),
        {
            "intent_id": intent_id,
            "browser_hash": hash_secret(browser_binding),
            "state_hash": hash_secret(state),
            "nonce_hash": hash_secret(nonce),
            "pkce_hash": hash_secret(code_verifier),
        },
    )
    if not bool(prepared.scalar_one()):
        raise HTTPException(status_code=409, detail="Link request is unavailable or expired")
    response = RedirectResponse(location)
    _set_short_cookie(response, STATE_COOKIE, state)
    _set_short_cookie(response, NONCE_COOKIE, nonce)
    _set_short_cookie(response, VERIFIER_COOKIE, code_verifier)
    _set_short_cookie(response, PURPOSE_COOKIE, LINK_PURPOSE)
    _set_short_cookie(response, LINK_INTENT_COOKIE, str(intent_id))
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
        raise HTTPException(status_code=400, detail=f"OIDC error: {error_description or error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="OIDC code or state missing")
    expected_state = request.cookies.get(STATE_COOKIE)
    nonce = request.cookies.get(NONCE_COOKIE)
    code_verifier = request.cookies.get(VERIFIER_COOKIE)
    purpose = request.cookies.get(PURPOSE_COOKIE) or LOGIN_PURPOSE
    if not expected_state or not nonce or not code_verifier or not secrets.compare_digest(expected_state, state):
        raise HTTPException(status_code=400, detail="Invalid OIDC state")
    try:
        discovery = await get_discovery()
        token_response = await exchange_code(discovery, code, _redirect_uri(), code_verifier)
        id_token = token_response.get("id_token")
        if not id_token:
            raise ValueError("OIDC id_token missing")
        claims = await validate_id_token(discovery, id_token, nonce)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Google authentication response is invalid") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google authentication provider request failed") from exc

    subject = str(claims.get("sub") or "")
    email = normalize_email(str(claims.get("email") or ""))
    if not subject or not email:
        raise HTTPException(status_code=401, detail="OIDC subject or email missing")
    if claims.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="OIDC email is not verified")

    if purpose == LINK_PURPOSE:
        browser_binding = request.cookies.get(settings.account_link_cookie_name)
        intent_cookie = request.cookies.get(LINK_INTENT_COOKIE)
        if not browser_binding or not intent_cookie:
            raise HTTPException(status_code=400, detail="Link session is missing")
        try:
            intent_id = uuid.UUID(intent_cookie)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid link intent") from exc
        completed = await session.execute(
            text(
                "select health_compass.app_complete_google_link_result("
                ":intent_id, :browser_hash, :state_hash, :nonce_hash, :pkce_hash, :google_subject, :google_email)"
            ),
            {
                "intent_id": intent_id,
                "browser_hash": hash_secret(browser_binding),
                "state_hash": hash_secret(state),
                "nonce_hash": hash_secret(nonce),
                "pkce_hash": hash_secret(code_verifier),
                "google_subject": subject,
                "google_email": email,
            },
        )
        completion = completed.scalar_one_or_none()
        if not completion:
            response = RedirectResponse(
                _frontend_url("/auth/link-account", {"status": "confirmation-failed"}),
                status_code=303,
            )
            _delete_oidc_cookies(response)
            return response
        linked_user_id = uuid.UUID(str(completion["user_id"]))
        real_intent_id = uuid.UUID(str(completion["intent_id"]))
        replayed = bool(completion.get("replayed"))
        await _record_link_audit(
            session,
            request,
            event_type="identity.link_completed",
            result="success",
            intent_id=real_intent_id,
            actor_user_id=linked_user_id,
            metadata={"confirmation": "google", "replayed": replayed},
        )
        if not replayed:
            await apply_user_context(session, linked_user_id)
            linked_user_result = await session.execute(select(User).where(User.id == linked_user_id))
            linked_user = linked_user_result.scalar_one_or_none()
            if linked_user is not None:
                await _notify_linked_addresses(
                    session,
                    request,
                    user=linked_user,
                    intent_id=real_intent_id,
                )
        return await _create_session_response(session, request, linked_user_id)

    identity_user_id = await _lookup_identity_user_id(session, GOOGLE_PROVIDER, subject)
    if identity_user_id is None and settings.account_linking_enabled:
        candidate = await lookup_verified_email_candidate(session, email)
        if candidate.has_existing_duplicates:
            response = RedirectResponse(
                _frontend_url("/auth/link-account", {"status": "existing-duplicates", "required": EMAIL_PROVIDER}),
                status_code=303,
            )
            _delete_oidc_cookies(response)
            return response
        if candidate.has_single_candidate:
            browser_binding = new_browser_binding()
            intent_id = await create_account_link_intent(
                session,
                flow_type="google_first_email_existing",
                normalized_email=email,
                candidate_user_id=candidate.user_id,
                initiating_provider=GOOGLE_PROVIDER,
                initiating_subject=subject,
                required_provider=EMAIL_PROVIDER,
                browser_binding_hash=hash_secret(browser_binding),
                expires_at=datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(seconds=settings.account_link_intent_ttl_seconds),
                initiating_claims=claims,
                created_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            response = RedirectResponse(
                _frontend_url("/auth/link-account", {"intent": str(intent_id), "required": EMAIL_PROVIDER}),
                status_code=303,
            )
            _delete_oidc_cookies(response)
            _set_account_link_cookie(response, browser_binding)
            return response

    if identity_user_id is None:
        user_id = uuid.uuid4()
        await apply_user_context(session, user_id)
        user = User(
            id=user_id,
            email=email,
            display_name=claims.get("name") or claims.get("preferred_username") or email,
            status="active",
        )
        session.add(user)
        await session.flush()
        session.add(
            UserIdentity(
                user_id=user.id,
                provider=GOOGLE_PROVIDER,
                subject=subject,
                issuer=settings.oidc_issuer or "",
                claims=claims,
                last_seen_at=datetime.datetime.now(datetime.UTC),
            )
        )
    else:
        await apply_user_context(session, identity_user_id)
        user_result = await session.execute(select(User).where(User.id == identity_user_id))
        user = user_result.scalar_one()
        identity_result = await session.execute(
            select(UserIdentity).where(UserIdentity.provider == GOOGLE_PROVIDER, UserIdentity.subject == subject)
        )
        identity = identity_result.scalar_one()
        user.display_name = claims.get("name") or user.display_name
        identity.claims = claims
        identity.last_seen_at = datetime.datetime.now(datetime.UTC)

    await ensure_personal_workspace(session, user)
    return await _create_session_response(session, request, user.id)


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
    response = RedirectResponse(settings.frontend_url, status_code=303)
    response.delete_cookie(settings.session_cookie_name, path="/api")
    response.delete_cookie(settings.account_link_cookie_name, path="/api/auth")
    _delete_oidc_cookies(response)
    return response


@router.get("/logout")
async def logout_get(request: Request, session: AsyncSession = Depends(get_session)) -> RedirectResponse:
    return await _logout_response(request, session)


@router.post("/logout")
async def logout_post(request: Request, session: AsyncSession = Depends(get_session)) -> RedirectResponse:
    return await _logout_response(request, session)
