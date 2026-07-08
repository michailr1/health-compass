"""Email magic-link authentication routes."""

from __future__ import annotations

import datetime
import uuid
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.magic_links import hash_magic_token, new_magic_token, normalize_email, send_magic_link
from app.core.session_tokens import hash_token, new_session_token
from app.db.rls import apply_session_context, apply_user_context
from app.db.session import get_session
from app.models.user import AuthSession, User, UserIdentity
from app.services.bootstrap import ensure_personal_workspace

router = APIRouter(prefix="/auth/email", tags=["auth"])
EMAIL_PROVIDER = "email"
EMAIL_ISSUER = "health-compass-email"


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkAccepted(BaseModel):
    message: str


def _frontend_url(path: str, query: str = "") -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


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
            _frontend_url("/auth-link", "status=invalid"),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    user_id = await _lookup_identity_user_id(session, EMAIL_PROVIDER, email)
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
        user.email = email
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
