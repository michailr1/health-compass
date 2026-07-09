"""Schemas for identity and profile access APIs."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.health_profile import ProfileReadiness


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str | None = None
    status: str


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_by_user_id: uuid.UUID


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    owner_user_id: uuid.UUID
    display_name: str
    date_of_birth: datetime.date | None = None
    sex: str | None = None
    height_cm: Decimal | None = None
    timezone: str | None = None
    readiness: ProfileReadiness | None = None


class DashboardSnapshotResponse(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    summary: dict
    priorities: list
    source_label: str
    created_at: datetime.datetime
