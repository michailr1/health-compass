"""Schemas for HC-013 session management."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel


class AuthSessionSummary(BaseModel):
    id: uuid.UUID
    is_current: bool
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime.datetime
    expires_at: datetime.datetime


class SessionRotationResponse(BaseModel):
    session_id: uuid.UUID
    rotated: bool = True


class SessionRevocationResponse(BaseModel):
    session_id: uuid.UUID
    revoked: bool = True
    current_session: bool
