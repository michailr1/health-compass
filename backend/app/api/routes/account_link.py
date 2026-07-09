"""Account-link confirmation routes."""

from __future__ import annotations

import datetime
import uuid
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.account_linking import hash_secret
from app.core.config import settings
from app.core.magic_links import (
    hash_magic_token,
    new_magic_token,
    send_account_link_email,
)
from app.core.session_tokens import hash_token, new_session_token
from app.db.rls import apply_session_context, apply_user_context
from app.db.session import get_session
from app.models.user import AuthSession, User

router = APIRouter(prefix="/auth/link", tags=["auth"])


class LinkEmailRequest(BaseModel):
    intent_id: uuid.UUID


class LinkEmailAccepted(BaseModel):
    message: str


def _frontend_url(path: str, query: dict[str, str] | None = None) -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query or {}), ""))


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


@router.post(
    "/email/request",
    response_model=LinkEmailAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_link_email(
    payload: LinkEmailRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> LinkEmailAccepted:
    if not settings.account_linking_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    browser_binding = request.cookies.get(settings.account_link_cookie_name)
    if not browser_binding:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Link session is missing")

    token = new_magic_token()
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        seconds=settings.account_link_intent_ttl_seconds
    )
    result = await session.execute(
        text(
            "select health_compass.app_issue_link_email_token("
            ":intent_id, :browser_hash, :token_hash, :expires_at, :ip, :user_agent)"
        ),
        {
            "intent_id": payload.intent_id,
            "browser_hash": hash_secret(browser_binding),
            "token_hash": hash_magic_token(token),
            "expires_at": expires_at,
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    )
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Link request is unavailable or expired",
        )

    try:
        await send_account_link_email(recipient, token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is temporarily unavailable",
        ) from exc

    return LinkEmailAccepted(
        message="A confirmation link has been sent to the verified email address."
    )


@router.get("/email/consume")
async def consume_link_email(
    request: Request,
    token: str = Query(min_length=32, max_length=256),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not settings.account_linking_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    browser_binding = request.cookies.get(settings.account_link_cookie_name)
    if not browser_binding:
        return RedirectResponse(
            _frontend_url("/auth/link-account", {"status": "invalid-browser"}),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    result = await session.execute(
        text(
            "select health_compass.app_consume_link_email_token("
            ":token_hash, :browser_hash, :issuer)"
        ),
        {
            "token_hash": hash_magic_token(token),
            "browser_hash": hash_secret(browser_binding),
            "issuer": settings.oidc_issuer or "https://accounts.google.com",
        },
    )
    user_id = result.scalar_one_or_none()
    if user_id is None:
        return RedirectResponse(
            _frontend_url("/auth/link-account", {"status": "invalid-or-expired"}),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    await apply_user_context(session, user_id)
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Linked account is unavailable")

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
    response.delete_cookie(settings.account_link_cookie_name, path="/api/auth")
    return response
