"""HC-026: resolve exactly one empty duplicate after second-provider proof."""

from __future__ import annotations

import datetime
import json
import uuid
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.account_linking import hash_secret, new_browser_binding
from app.core.config import settings
from app.core.magic_links import (
    hash_magic_token,
    new_magic_token,
    send_account_linked_notifications,
    send_duplicate_resolution_email,
)
from app.core.session_tokens import hash_token, new_session_token
from app.db.rls import apply_session_context, apply_user_context
from app.db.session import get_session
from app.models.user import AuthSession, User
from app.services.account_linking import verified_notification_emails

router = APIRouter(prefix="/auth/duplicates", tags=["auth"])


class DuplicateResolutionStartResponse(BaseModel):
    available: bool
    reason: str | None = None
    intent_id: uuid.UUID | None = None
    required_provider: str | None = None
    canonical_is_current: bool | None = None
    confirmation_url: str | None = None
    message: str


def _frontend_url(path: str, query: dict[str, str] | None = None) -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query or {}), ""))


def _set_flow_cookie(response: JSONResponse | RedirectResponse, value: str) -> None:
    response.set_cookie(
        settings.account_link_cookie_name,
        value,
        max_age=settings.account_link_intent_ttl_seconds,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/api/auth",
    )


async def _record_duplicate_audit(
    session: AsyncSession,
    request: Request,
    *,
    event_type: str,
    result: str,
    intent_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    metadata: dict | None = None,
) -> None:
    await session.execute(
        text(
            "select health_compass.app_record_duplicate_resolution_audit("
            ":event_type, :result, :intent_id, :actor_user_id, :ip, :user_agent, "
            "cast(:metadata as jsonb))"
        ),
        {
            "event_type": event_type,
            "result": result,
            "intent_id": intent_id,
            "actor_user_id": str(actor_user_id),
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "metadata": json.dumps(metadata or {}),
        },
    )


async def _create_canonical_session_response(
    session: AsyncSession,
    request: Request,
    user_id: uuid.UUID,
    redirect_path: str,
) -> RedirectResponse:
    await apply_user_context(session, user_id)
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Canonical account is unavailable")

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

    response = RedirectResponse(
        _frontend_url(redirect_path, {"status": "duplicate-resolved"}),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=settings.session_ttl_seconds,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/api",
    )
    response.delete_cookie(settings.account_link_cookie_name, path="/api/auth")
    return response


async def _notify_duplicate_resolution(
    session: AsyncSession,
    request: Request,
    *,
    canonical_user: User,
    intent_id: uuid.UUID,
) -> None:
    recipients = await verified_notification_emails(session, canonical_user)
    failures = await send_account_linked_notifications(
        recipients,
        ("Google", "Email Magic Link"),
    )
    if failures:
        await _record_duplicate_audit(
            session,
            request,
            event_type="identity.duplicate_resolution_notification_failed",
            result="partial" if len(failures) < len(recipients) else "error",
            intent_id=intent_id,
            actor_user_id=canonical_user.id,
            metadata={"recipient_count": len(recipients), "failure_count": len(failures)},
        )


@router.post("/start", response_model=DuplicateResolutionStartResponse)
async def start_duplicate_resolution(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if not settings.account_linking_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    browser_binding = new_browser_binding()
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        seconds=settings.account_link_intent_ttl_seconds
    )
    result = await session.execute(
        text(
            "select health_compass.app_create_duplicate_resolution_intent("
            ":user_id, :browser_hash, :expires_at)"
        ),
        {
            "user_id": current_user.id,
            "browser_hash": hash_secret(browser_binding),
            "expires_at": expires_at,
        },
    )
    resolution = result.scalar_one_or_none()
    if not resolution or not bool(resolution.get("available")):
        reason = str((resolution or {}).get("reason") or "resolution_unavailable")
        payload = DuplicateResolutionStartResponse(
            available=False,
            reason=reason,
            message=(
                "Автоматическое объединение недоступно. Если оба профиля содержат данные, "
                "Health Compass не выполняет общий merge."
            ),
        )
        return JSONResponse(payload.model_dump(mode="json"), status_code=status.HTTP_409_CONFLICT)

    intent_id = uuid.UUID(str(resolution["intent_id"]))
    required_provider = str(resolution["required_provider"])
    canonical_is_current = bool(resolution["canonical_is_current"])
    confirmation_url: str | None = None
    message = "Подтвердите владение вторым аккаунтом."

    if required_provider == "email":
        token = new_magic_token()
        issued = await session.execute(
            text(
                "select health_compass.app_issue_duplicate_resolution_email_token("
                ":intent_id, :browser_hash, :token_hash, :expires_at)"
            ),
            {
                "intent_id": intent_id,
                "browser_hash": hash_secret(browser_binding),
                "token_hash": hash_magic_token(token),
                "expires_at": expires_at,
            },
        )
        recipient = issued.scalar_one_or_none()
        if not recipient:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email proof is unavailable")
        try:
            await send_duplicate_resolution_email(recipient, token)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery is temporarily unavailable",
            ) from exc
        message = "Ссылка подтверждения отправлена на email второго аккаунта."
    else:
        confirmation_url = (
            "/api/auth/duplicates/google/start?"
            + urlencode({"intent_id": str(intent_id)})
        )

    await _record_duplicate_audit(
        session,
        request,
        event_type="identity.duplicate_resolution_started",
        result="success",
        intent_id=intent_id,
        actor_user_id=current_user.id,
        metadata={
            "required_provider": required_provider,
            "canonical_is_current": canonical_is_current,
        },
    )

    payload = DuplicateResolutionStartResponse(
        available=True,
        intent_id=intent_id,
        required_provider=required_provider,
        canonical_is_current=canonical_is_current,
        confirmation_url=confirmation_url,
        message=message,
    )
    response = JSONResponse(payload.model_dump(mode="json"))
    _set_flow_cookie(response, browser_binding)
    return response


@router.get("/email/consume")
async def consume_duplicate_resolution_email(
    request: Request,
    token: str = Query(min_length=32, max_length=256),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not settings.account_linking_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    browser_binding = request.cookies.get(settings.account_link_cookie_name)
    if not browser_binding:
        return RedirectResponse(
            _frontend_url("/app/sign-in-methods", {"status": "invalid-duplicate-browser"}),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    result = await session.execute(
        text(
            "select health_compass.app_complete_duplicate_resolution_email("
            ":token_hash, :browser_hash)"
        ),
        {
            "token_hash": hash_magic_token(token),
            "browser_hash": hash_secret(browser_binding),
        },
    )
    completion = result.scalar_one_or_none()
    if not completion:
        return RedirectResponse(
            _frontend_url("/app/sign-in-methods", {"status": "duplicate-resolution-failed"}),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    canonical_user_id = uuid.UUID(str(completion["canonical_user_id"]))
    intent_id = uuid.UUID(str(completion["intent_id"]))
    replayed = bool(completion.get("replayed"))
    await apply_user_context(session, canonical_user_id)
    user_result = await session.execute(select(User).where(User.id == canonical_user_id))
    canonical_user = user_result.scalar_one_or_none()
    if canonical_user is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Canonical account is unavailable")

    await _record_duplicate_audit(
        session,
        request,
        event_type="identity.duplicate_resolution_completed",
        result="success",
        intent_id=intent_id,
        actor_user_id=canonical_user.id,
        metadata={"confirmation": "email", "replayed": replayed},
    )
    if not replayed:
        await _notify_duplicate_resolution(
            session,
            request,
            canonical_user=canonical_user,
            intent_id=intent_id,
        )

    return await _create_canonical_session_response(
        session,
        request,
        canonical_user.id,
        "/app/sign-in-methods",
    )
