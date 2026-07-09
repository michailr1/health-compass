"""Account-link confirmation, decline and separate-account routes."""

from __future__ import annotations

import datetime
import json
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
    send_account_linked_notification,
)
from app.core.session_tokens import hash_token, new_session_token
from app.db.rls import apply_session_context, apply_user_context
from app.db.session import get_session
from app.models.user import AuthSession, User, UserIdentity
from app.services.bootstrap import ensure_personal_workspace

router = APIRouter(prefix="/auth/link", tags=["auth"])
SEPARATE_ACCOUNT_CONFIRMATION = "CREATE_SEPARATE_ACCOUNT"


class LinkEmailRequest(BaseModel):
    intent_id: uuid.UUID


class LinkEmailAccepted(BaseModel):
    message: str


class DeclineLinkRequest(BaseModel):
    intent_id: uuid.UUID


class CreateSeparateAccountRequest(BaseModel):
    intent_id: uuid.UUID
    confirmation: str


def _frontend_url(path: str, query: dict[str, str] | None = None) -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query or {}), ""))


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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
            ":event_type, :result, :intent_id, :actor_user_id, :ip, :user_agent, "
            "cast(:metadata as jsonb))"
        ),
        {
            "event_type": event_type,
            "result": result,
            "intent_id": intent_id,
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "ip": _client_ip(request),
            "user_agent": request.headers.get("user-agent"),
            "metadata": json.dumps(metadata or {}),
        },
    )


async def _create_authenticated_response(
    session: AsyncSession,
    request: Request,
    user: User,
) -> RedirectResponse:
    session_token = new_session_token()
    session_token_hash = hash_token(session_token)
    await apply_session_context(session, session_token_hash)
    session.add(
        AuthSession(
            user_id=user.id,
            session_token_hash=session_token_hash,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(seconds=settings.session_ttl_seconds),
        )
    )
    response = RedirectResponse(settings.frontend_url, status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookie(response, session_token)
    response.delete_cookie(settings.account_link_cookie_name, path="/api/auth")
    return response


@router.post("/email/request", response_model=LinkEmailAccepted, status_code=status.HTTP_202_ACCEPTED)
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
            "ip": _client_ip(request),
            "user_agent": request.headers.get("user-agent"),
        },
    )
    recipient = result.scalar_one_or_none()
    if not recipient:
        await _record_link_audit(
            session,
            request,
            event_type="identity.link_failed",
            result="denied",
            intent_id=payload.intent_id,
            metadata={"stage": "link_email_issue"},
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Link request is unavailable or expired")

    try:
        await send_account_link_email(recipient, token)
    except Exception as exc:
        await _record_link_audit(
            session,
            request,
            event_type="identity.link_failed",
            result="error",
            intent_id=payload.intent_id,
            metadata={"stage": "link_email_delivery"},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is temporarily unavailable",
        ) from exc
    return LinkEmailAccepted(message="A confirmation link has been sent to the verified email address.")


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
    completion = result.scalar_one_or_none()
    if not completion:
        return RedirectResponse(
            _frontend_url("/auth/link-account", {"status": "invalid-or-expired"}),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    user_id = uuid.UUID(str(completion["user_id"]))
    intent_id = uuid.UUID(str(completion["intent_id"]))
    replayed = bool(completion.get("replayed"))
    await apply_user_context(session, user_id)
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Linked account is unavailable")

    await _record_link_audit(
        session,
        request,
        event_type="identity.link_completed",
        result="success",
        intent_id=intent_id,
        actor_user_id=user.id,
        metadata={"confirmation": "link_email", "replayed": replayed},
    )
    if not replayed:
        try:
            await send_account_linked_notification(user.email, ("Google", "Email Magic Link"))
        except Exception:
            await _record_link_audit(
                session,
                request,
                event_type="identity.link_notification_failed",
                result="error",
                intent_id=intent_id,
                actor_user_id=user.id,
            )
    return await _create_authenticated_response(session, request, user)


@router.post("/intents/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_account_link(
    payload: DeclineLinkRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> None:
    if not settings.account_linking_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    browser_binding = request.cookies.get(settings.account_link_cookie_name)
    if not browser_binding:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Link session is missing")
    result = await session.execute(
        text("select health_compass.app_decline_account_link(:intent_id, :browser_hash)"),
        {"intent_id": payload.intent_id, "browser_hash": hash_secret(browser_binding)},
    )
    if not bool(result.scalar_one()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Link request cannot be declined")
    await _record_link_audit(
        session,
        request,
        event_type="identity.link_declined",
        result="success",
        intent_id=payload.intent_id,
    )


@router.post("/intents/create-separate-account")
async def create_separate_account(
    payload: CreateSeparateAccountRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not settings.account_linking_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if payload.confirmation != SEPARATE_ACCOUNT_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit separate-account confirmation is required",
        )
    browser_binding = request.cookies.get(settings.account_link_cookie_name)
    if not browser_binding:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Link session is missing")

    result = await session.execute(
        text(
            "select health_compass.app_claim_declined_link_for_separate_account("
            ":intent_id, :browser_hash)"
        ),
        {"intent_id": payload.intent_id, "browser_hash": hash_secret(browser_binding)},
    )
    identity_payload = result.scalar_one_or_none()
    if not identity_payload:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Separate account request is unavailable or expired",
        )

    provider = str(identity_payload["provider"])
    subject = str(identity_payload["subject"])
    email = str(identity_payload["normalized_email"])
    claims = dict(identity_payload.get("claims") or {})
    if provider not in {"google", "email"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unsupported identity provider")

    user_id = uuid.uuid4()
    await apply_user_context(session, user_id)
    user = User(
        id=user_id,
        email=email,
        display_name=str(claims.get("name") or email.split("@", 1)[0]),
        status="active",
    )
    session.add(user)
    await session.flush()
    session.add(
        UserIdentity(
            user_id=user.id,
            provider=provider,
            subject=subject,
            issuer=(settings.oidc_issuer or "") if provider == "google" else "health-compass-email",
            claims=claims or {"email": email, "email_verified": True},
            last_seen_at=datetime.datetime.now(datetime.UTC),
        )
    )
    await ensure_personal_workspace(session, user)
    await _record_link_audit(
        session,
        request,
        event_type="identity.separate_account_confirmed",
        result="success",
        intent_id=payload.intent_id,
        actor_user_id=user.id,
        metadata={"provider": provider},
    )
    return await _create_authenticated_response(session, request, user)
