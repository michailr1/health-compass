"""API schemas for HC-017 secure document intake."""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

DocumentStatus = Literal[
    "uploading",
    "quarantined",
    "scanning",
    "accepted",
    "ocr_queued",
    "processing",
    "review_required",
    "confirmed",
    "rejected",
    "failed",
    "voided",
    "deletion_pending",
    "erased",
]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    status: DocumentStatus
    original_filename: str
    declared_media_type: str
    detected_media_type: str
    byte_size: int
    sha256: str
    page_count: int | None
    failure_code: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    voided_at: datetime.datetime | None


class DocumentIntakeCapabilities(BaseModel):
    upload_enabled: bool
    accepted_media_types: list[str]
    max_bytes: int
    max_image_pixels: int
    quarantine_only: Literal[True] = True
    preview_available: Literal[False] = False
    ocr_available: Literal[False] = False
