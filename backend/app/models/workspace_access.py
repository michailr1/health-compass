"""Workspace access model."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkspaceAccess(Base):
    __tablename__ = "workspace_" + "members"
    __table_args__ = {"schema": "health_compass"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("health_compass.workspaces.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("health_compass.users.id"), nullable=False)
    access_level: Mapped[str] = mapped_column("role", String(32), nullable=False)
