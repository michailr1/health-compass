"""Authenticated settings flows for adding a second sign-in method."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.account_linking import hash_secret, new_browser_binding
from app.core.config import settings
from app.core.magic_links import normalize_email
from app.db.session import get_session
from app.models.user import User, UserIdentity
from app.services.account_linking import create_account_link_intent

router = APIRouter(prefix="/auth/link/settings", tags=["auth"])


@dataclass(frozen=True, slots=True)
class SettingsLinkPlan:
    source: UserIdentity
    flow_type: str
    normalized_email: str


def build_settings_link_plan(
    provider: str,
    identities: dict[str, UserIdentity],
) -> SettingsLinkPlan | None:
    if provider in identities:
        return None

    if provider == "google":
        source = identities.get("email")
        if source is None or (source.claims or {}).get("email_verified") is not True:
            raise ValueError("A verified Email Magic Link identity is required")
        normalized_email = normalize_email(source.subject)
        return SettingsLinkPlan(
            source=source,
            flow_type="settings_add_google",
            normalized_email=normalized_email,
        )

    if provider == "email":
        source = identities.get("google")
        source_claims = source.claims if source is not None else {}
        if source is None or source_claims.get("email_verified") is not True:
            raise ValueError("A verified Google identity is required")
        normalized_email = normalize_email(str(source_claims.get("email") or ""))
        if not normalized_email:
            raise ValueError("Google email is unavailable")
        return SettingsLinkPlan(
            source=source,
            flow_type="settings_add_email",
            normalized_email=normalized_email,
        )

    raise ValueError("Unsupported identity provider")


def _frontend_url(path: str, query: dict[str, str] | None = None) -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query or {}), ""))


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


@router.get("/start")
async def start_settings_link(
    request: Request,
    provider: str = Query(pattern="^(google|email)$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not settings.account_linking_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    result = await session.execute(
        select(UserIdentity).where(UserIdentity.user_id == current_user.id)
    )
    identities = {identity.provider: identity for identity in result.scalars().all()}
    try:
        plan = build_settings_link_plan(provider, identities)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if plan is None:
        return RedirectResponse(
            _frontend_url("/app/sign-in-methods", {"status": "already-connected"}),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    browser_binding = new_browser_binding()
    intent_id = await create_account_link_intent(
        session,
        flow_type=plan.flow_type,
        normalized_email=plan.normalized_email,
        candidate_user_id=current_user.id,
        initiating_provider=plan.source.provider,
        initiating_subject=plan.source.subject,
        required_provider=provider,
        browser_binding_hash=hash_secret(browser_binding),
        expires_at=datetime.datetime.now(datetime.UTC)
        + datetime.timedelta(seconds=settings.account_link_intent_ttl_seconds),
        initiating_claims=plan.source.claims or {},
        created_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    response = RedirectResponse(
        _frontend_url(
            "/auth/link-account",
            {"intent": str(intent_id), "required": provider, "source": "settings"},
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _set_account_link_cookie(response, browser_binding)
    return response
