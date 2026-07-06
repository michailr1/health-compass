"""Version response schema."""

from __future__ import annotations

from pydantic import BaseModel


class VersionResponse(BaseModel):
    service: str
    version: str
    commit: str
    environment: str
