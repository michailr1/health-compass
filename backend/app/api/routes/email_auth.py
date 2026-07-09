"""Email magic-link authentication routes."""

from __future__ import annotations

import datetime
import uuid
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_linking import hash_secret, new_browser_binding
from app.core.config import settings
from app.core.magic_links import hash_magic_token, new_magic_token, normalize_email, send_magic_link
from app.core.session_tokens import hash_token, new_session_token
from app.db.rls import apply_session_context, apply_user_context
from app.db.session import get_session
from app.models.user import AuthSession, User, UserIdentity
from app.services.account_linking import create_account_link_intent, lookup_verified_email_candidate
from app.services.bootstrap import ensure_personal_workspace

router = APIRouter(prefix="/auth/email", tags=["auth"])
EMAIL_PROVIDER = "email"
GOOGLE_PROVIDER = "google"
EMAIL_ISSUER = "health-compass-email"


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkAccepted(BaseModel):
    message: str


def _frontend_url(path: str, query: dict[str, str] | None = None) -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query or {}), ""))


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


def _set_session_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_seconds,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/api",
    )


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


@router.post("/request", response_model=MagicLinkAccepted, status_code=status.HTTP_202_ACCEPTED)
async def request_magic_link(
    payload: MagicLinkRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> MagicLinkAccepted:
    if not settings.email_auth_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    email = normalize_email(str(payload.email))
    token = new_magic_token()
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        seconds=settings.magic_link_ttl_seconds
    )
    result = await session.execute(
        text(
            "select health_compass.app_issue_email_login_token("
            ":email, :token_hash, :expires_at, :ip, :user_agent)"
        ),
        {
            "email": email,
            "token_hash": hash_magic_token(token),
            "expires_at": expires_at,
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    )
    if bool(result.scalar_one()):
        try:
            await send_magic_link(email, token)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery is temporarily unavailable",
            ) from exc

    return MagicLinkAccepted(
        message="If the address can receive email, a sign-in link will arrive shortly."
    )


@router.get("/consume")
async def consume_magic_link(
    request: Request,
    token: str = Query(min_length=32, max_length=256),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not settings.email_auth_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    result = await session.execute(
        text("select health_compass.app_consume_email_login_token(:token_hash)"),
        {"token_hash": hash_magic_token(token)},
    )
    email = result.scalar_one_or_none()
    if not email:
        return RedirectResponse(
            _frontend_url("/auth-link", {"status": "invalid"}),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    user_id = await _lookup_identity_user_id(session, EMAIL_PROVIDER, email)
    if user_id is None and settings.account_linking_enabled:
        candidate = await lookup_verified_email_candidate(session, email)
        if candidate.has_existing_duplicates:
            return RedirectResponse(
                _frontend_url(
                    "/auth/link-account",
                    {"status": "existing-duplicates", "required": GOOGLE_PROVIDER},
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
        if candidate.has_single_candidate:
            browser_binding = new_browser_binding()
            intent_id = await create_account_link_intent(
                session,
                flow_type="email_first_google_existing",
                normalized_email=email,
                candidate_user_id=candidate.user_id,
                initiating_provider=EMAIL_PROVIDER,
                initiating_subject=email,
                required_provider=GOOGLE_PROVIDER,
                browser_binding_hash=hash_secret(browser_binding),
                expires_at=datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(seconds=settings.account_link_intent_ttl_seconds),
                initiating_claims={"email": email, "email_verified": True},
                created_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            response = RedirectResponse(
                _frontend_url(
                    "/auth/link-account",
                    {"intent": str(intent_id), "required": GOOGLE_PROVIDER},
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
            _set_account_link_cookie(response, browser_binding)
            return response

    if user_id is None:
        user_id = uuid.uuid4()
        await apply_user_context(session, user_id)
        user = User(
            id=user_id,
            email=email,
            display_name=email.split("@", 1)[0],
            status="active",
        )
        session.add(user)
        await session.flush()
        session.add(
            UserIdentity(
                user_id=user.id,
                provider=EMAIL_PROVIDER,
                subject=email,
                issuer=EMAIL_ISSUER,
                claims={"email": email, "email_verified": True},
                last_seen_at=datetime.datetime.now(datetime.UTC),
            )
        )
    else:
        await apply_user_context(session, user_id)
        user_result = await session.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one()
        identity_result = await session.execute(
            select(UserIdentity).where(
                UserIdentity.provider == EMAIL_PROVIDER,
                UserIdentity.subject == email,
            )
        )
        identity = identity_result.scalar_one()
        identity.last_seen_at = datetime.datetime.now(datetime.UTC)

    await ensure_personal_workspace(session, user)

    session_token = new_session_token()
    session_token_hash = hash_token(session_token)
    await apply_session_context(session, session_token_hash)
    session.add(
        AuthSession(
            user_id=user.id,
            session_token_hash=session_token_hash,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(seconds=settings.session_ttl_seconds),
        )
    )

    response = RedirectResponse(settings.frontend_url, status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookie(response, session_token)
    return response
