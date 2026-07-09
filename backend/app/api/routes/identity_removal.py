"""Step-up protected removal of a connected sign-in method."""

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
    send_identity_removal_email,
    send_identity_removed_notification,
)
from app.db.rls import apply_user_context
from app.db.session import get_session
from app.models.user import User
from app.services.account_linking import verified_notification_emails

router = APIRouter(prefix="/auth/identities/remove", tags=["auth"])


class IdentityRemovalStartResponse(BaseModel):
    intent_id: uuid.UUID
    target_provider: str
    required_provider: str
    confirmation_url: str | None = None
    message: str


def _frontend_url(path: str, query: dict[str, str] | None = None) -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query or {}), ""))


def _set_removal_cookie(response: JSONResponse | RedirectResponse, value: str) -> None:
    response.set_cookie(
        settings.account_link_cookie_name,
        value,
        max_age=settings.account_link_intent_ttl_seconds,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/api/auth",
    )


async def _record_removal_audit(
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
            "select health_compass.app_record_identity_removal_audit("
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


async def _notify_removal(
    session: AsyncSession,
    request: Request,
    *,
    user: User,
    intent_id: uuid.UUID,
    removed_provider: str,
) -> None:
    recipients = await verified_notification_emails(session, user)
    failures = 0
    for recipient in recipients:
        try:
            await send_identity_removed_notification(recipient, removed_provider)
        except Exception:
            failures += 1
    if failures:
        await _record_removal_audit(
            session,
            request,
            event_type="identity.removal_notification_failed",
            result="partial" if failures < len(recipients) else "error",
            intent_id=intent_id,
            actor_user_id=user.id,
            metadata={"recipient_count": len(recipients), "failure_count": failures},
        )


@router.post("/{identity_id}/start", response_model=IdentityRemovalStartResponse)
async def start_identity_removal(
    identity_id: uuid.UUID,
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
            "select health_compass.app_create_identity_removal_intent("
            ":user_id, :identity_id, :browser_hash, :expires_at)"
        ),
        {
            "user_id": current_user.id,
            "identity_id": identity_id,
            "browser_hash": hash_secret(browser_binding),
            "expires_at": expires_at,
        },
    )
    removal = result.scalar_one_or_none()
    if not removal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last sign-in method cannot be removed, or the method is unavailable",
        )

    intent_id = uuid.UUID(str(removal["intent_id"]))
    target_provider = str(removal["target_provider"])
    required_provider = str(removal["required_provider"])
    confirmation_url: str | None = None
    message = "Confirm the removal using the remaining sign-in method."

    if required_provider == "email":
        token = new_magic_token()
        issued = await session.execute(
            text(
                "select health_compass.app_issue_identity_removal_email_token("
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
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email step-up is unavailable")
        try:
            await send_identity_removal_email(recipient, token, target_provider)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery is temporarily unavailable",
            ) from exc
        message = "A separate removal confirmation link was sent to the remaining email method."
    else:
        confirmation_url = (
            "/api/auth/identities/remove/google/start?"
            + urlencode({"intent_id": str(intent_id)})
        )

    await _record_removal_audit(
        session,
        request,
        event_type="identity.removal_started",
        result="success",
        intent_id=intent_id,
        actor_user_id=current_user.id,
        metadata={
            "target_provider": target_provider,
            "required_provider": required_provider,
        },
    )

    payload = IdentityRemovalStartResponse(
        intent_id=intent_id,
        target_provider=target_provider,
        required_provider=required_provider,
        confirmation_url=confirmation_url,
        message=message,
    )
    response = JSONResponse(payload.model_dump(mode="json"))
    _set_removal_cookie(response, browser_binding)
    return response


@router.get("/email/consume")
async def consume_identity_removal_email(
    request: Request,
    token: str = Query(min_length=32, max_length=256),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not settings.account_linking_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    browser_binding = request.cookies.get(settings.account_link_cookie_name)
    if not browser_binding:
        return RedirectResponse(
            _frontend_url("/app/sign-in-methods", {"status": "invalid-removal-browser"}),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    result = await session.execute(
        text(
            "select health_compass.app_consume_identity_removal_email_token("
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
            _frontend_url("/app/sign-in-methods", {"status": "invalid-removal-token"}),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    user_id = uuid.UUID(str(completion["user_id"]))
    intent_id = uuid.UUID(str(completion["intent_id"]))
    removed_provider = str(completion["removed_provider"])
    replayed = bool(completion.get("replayed"))
    await apply_user_context(session, user_id)
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account is unavailable")

    await _record_removal_audit(
        session,
        request,
        event_type="identity.removal_completed",
        result="success",
        intent_id=intent_id,
        actor_user_id=user.id,
        metadata={"removed_provider": removed_provider, "replayed": replayed},
    )
    if not replayed:
        await _notify_removal(
            session,
            request,
            user=user,
            intent_id=intent_id,
            removed_provider=removed_provider,
        )

    response = RedirectResponse(
        _frontend_url("/app/sign-in-methods", {"status": "removed"}),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie(settings.account_link_cookie_name, path="/api/auth")
    return response
