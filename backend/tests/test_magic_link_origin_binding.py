"""Regression tests for Safari/WebKit Magic Link origin handling."""

from __future__ import annotations

import re
from http.cookies import SimpleCookie
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException, Request

from app.api.routes.email_auth import (
    MAGIC_LINK_CONFIRM_COOKIE,
    MAGIC_LINK_CONFIRM_FIELD,
    _origin_is_allowed,
    consume_magic_link,
    magic_link_interstitial,
)
from app.core.config import settings

TOKEN = "A" * 43


class _Result:
    def scalar_one_or_none(self) -> None:
        return None


class _Session:
    def __init__(self) -> None:
        self.execute_calls = 0

    async def execute(self, *args: object, **kwargs: object) -> _Result:
        self.execute_calls += 1
        return _Result()


def _request(
    *,
    method: str = "POST",
    origin: str | None = None,
    cookie: str | None = None,
    confirmation: str | None = None,
) -> Request:
    fields = {"token": TOKEN}
    if confirmation is not None:
        fields[MAGIC_LINK_CONFIRM_FIELD] = confirmation
    body = urlencode(fields).encode()
    headers = [(b"content-type", b"application/x-www-form-urlencoded")]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    if cookie is not None:
        headers.append((b"cookie", cookie.encode()))

    sent = False

    async def receive() -> dict[str, object]:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "path": "/auth/email/consume",
            "raw_path": b"/auth/email/consume",
            "query_string": b"",
            "headers": headers,
            "server": ("health.funti.cc", 443),
            "client": ("127.0.0.1", 50000),
        },
        receive,
    )


async def test_interstitial_sets_short_lived_browser_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "email_auth_enabled", True)
    monkeypatch.setattr(settings, "magic_link_consume_url", None)
    request = _request(method="GET")

    response = await magic_link_interstitial(request, TOKEN)

    assert response.status_code == 200
    body = response.body.decode()
    match = re.search(r'name="confirmation" value="([^"]+)"', body)
    assert match is not None
    submitted = match.group(1)

    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    morsel = cookie[MAGIC_LINK_CONFIRM_COOKIE]
    assert morsel.value == submitted
    assert morsel["secure"]
    assert morsel["httponly"]
    assert morsel["samesite"].lower() == "lax"
    assert morsel["path"] == "/auth/email/consume"
    assert response.headers["cache-control"] == "no-store"


async def test_explicit_default_https_port_is_same_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "frontend_url", "https://health.funti.cc/app")
    request = _request(origin="https://health.funti.cc:443")
    session = _Session()

    response = await consume_magic_link(request, session)  # type: ignore[arg-type]

    assert response.status_code == 303
    assert session.execute_calls == 1


async def test_null_origin_requires_matching_browser_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "frontend_url", "https://health.funti.cc/app")
    confirmation = "B" * 43
    cookie = f"{MAGIC_LINK_CONFIRM_COOKIE}={confirmation}"
    request = _request(origin="null", cookie=cookie, confirmation=confirmation)
    session = _Session()

    response = await consume_magic_link(request, session)  # type: ignore[arg-type]

    assert response.status_code == 303
    assert session.execute_calls == 1


async def test_null_origin_without_binding_is_rejected_before_token_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "frontend_url", "https://health.funti.cc/app")
    request = _request(origin="null")
    session = _Session()

    with pytest.raises(HTTPException) as exc_info:
        await consume_magic_link(request, session)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 403
    assert session.execute_calls == 0


async def test_hostile_origin_is_rejected_even_with_browser_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "frontend_url", "https://health.funti.cc/app")
    confirmation = "C" * 43
    cookie = f"{MAGIC_LINK_CONFIRM_COOKIE}={confirmation}"
    request = _request(
        origin="https://evil.example",
        cookie=cookie,
        confirmation=confirmation,
    )
    session = _Session()

    assert _origin_is_allowed(request, confirmation) is False
    with pytest.raises(HTTPException) as exc_info:
        await consume_magic_link(request, session)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 403
    assert session.execute_calls == 0
