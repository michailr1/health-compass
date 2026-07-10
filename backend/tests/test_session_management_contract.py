"""Contract tests for HC-013 session management."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.session_management import _current_token_hash
from app.core.session_tokens import hash_token
from app.schemas.session_management import (
    AuthSessionSummary,
    SessionRevocationResponse,
    SessionRotationResponse,
)


def test_current_token_hash_requires_browser_session() -> None:
    with pytest.raises(HTTPException) as exc:
        _current_token_hash(None)
    assert exc.value.status_code == 409


def test_current_token_hash_never_returns_raw_token() -> None:
    raw = "example-session-token"
    result = _current_token_hash(raw)
    assert result == hash_token(raw)
    assert result != raw


def test_session_response_contracts_do_not_expose_token_material() -> None:
    session_id = uuid.uuid4()
    summary = AuthSessionSummary(
        id=session_id,
        is_current=True,
        ip_address="127.0.0.1",
        user_agent="Browser",
        created_at="2026-07-10T10:00:00Z",
        expires_at="2026-07-11T10:00:00Z",
    )
    assert "token" not in summary.model_dump()
    assert SessionRotationResponse(session_id=session_id).rotated is True
    assert SessionRevocationResponse(
        session_id=session_id,
        current_session=False,
    ).revoked is True
