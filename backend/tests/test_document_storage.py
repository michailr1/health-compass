"""Unit tests for HC-017 bounded quarantine storage."""

from __future__ import annotations

import io
import os
import stat
import struct
import uuid
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.storage.documents import (
    DocumentValidationError,
    LocalDocumentStorage,
    sanitize_original_filename,
)


def _upload(filename: str, content_type: str, payload: bytes) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(payload),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def _png(width: int = 1, height: int = 1) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", width, height)
    )


def _jpeg(width: int = 1, height: int = 1) -> bytes:
    return (
        b"\xff\xd8"
        + b"\xff\xc0"
        + b"\x00\x07"
        + b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
    )


@pytest.mark.asyncio
async def test_png_is_written_to_opaque_private_quarantine(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(str(tmp_path))
    document_id = uuid.uuid4()
    stored = await storage.write_quarantine(
        document_id,
        _upload("../../patient-result.png", "image/png", _png(120, 80)),
        max_bytes=1024,
        max_image_pixels=25_000_000,
    )

    assert stored.storage_key == f"quarantine/{document_id}/original"
    assert "patient-result" not in stored.storage_key
    assert stored.original_filename == "patient-result.png"
    assert stored.detected_media_type == "image/png"
    assert stored.image_width == 120
    assert stored.image_height == 80

    destination = tmp_path / stored.storage_key
    assert destination.read_bytes() == _png(120, 80)
    assert stat.S_IMODE(os.stat(destination).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(destination.parent).st_mode) == 0o700


@pytest.mark.asyncio
async def test_pdf_stays_quarantined_without_web_process_parsing(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(str(tmp_path))
    stored = await storage.write_quarantine(
        uuid.uuid4(),
        _upload("analysis.pdf", "application/pdf", b"%PDF-1.4\n%%EOF\n"),
        max_bytes=1024,
        max_image_pixels=25_000_000,
    )
    assert stored.detected_media_type == "application/pdf"
    assert stored.page_count is None
    assert stored.image_width is None


@pytest.mark.asyncio
async def test_jpeg_dimensions_are_bounded(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(str(tmp_path))
    with pytest.raises(DocumentValidationError, match="слишком большое") as exc_info:
        await storage.write_quarantine(
            uuid.uuid4(),
            _upload("scan.jpg", "image/jpeg", _jpeg(5000, 5000)),
            max_bytes=1024,
            max_image_pixels=1_000_000,
        )
    assert exc_info.value.code == "image_dimensions_exceeded"
    assert not list(tmp_path.rglob("original"))


@pytest.mark.asyncio
async def test_declared_media_type_must_match_magic_bytes(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(str(tmp_path))
    with pytest.raises(DocumentValidationError) as exc_info:
        await storage.write_quarantine(
            uuid.uuid4(),
            _upload("analysis.pdf", "application/pdf", _png()),
            max_bytes=1024,
            max_image_pixels=25_000_000,
        )
    assert exc_info.value.code == "media_type_mismatch"
    assert not list(tmp_path.rglob("original"))


@pytest.mark.asyncio
async def test_extension_must_match_declared_media_type(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(str(tmp_path))
    with pytest.raises(DocumentValidationError) as exc_info:
        await storage.write_quarantine(
            uuid.uuid4(),
            _upload("analysis.jpg", "application/pdf", b"%PDF-1.4\n%%EOF\n"),
            max_bytes=1024,
            max_image_pixels=25_000_000,
        )
    assert exc_info.value.code == "filename_media_type_mismatch"


@pytest.mark.asyncio
async def test_oversize_upload_is_removed(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(str(tmp_path))
    with pytest.raises(DocumentValidationError) as exc_info:
        await storage.write_quarantine(
            uuid.uuid4(),
            _upload("analysis.pdf", "application/pdf", b"%PDF-" + b"x" * 100),
            max_bytes=32,
            max_image_pixels=25_000_000,
        )
    assert exc_info.value.code == "document_too_large"
    assert exc_info.value.status_code == 413
    assert not list(tmp_path.rglob("original"))


def test_filename_sanitization_is_display_only_and_bounded() -> None:
    assert sanitize_original_filename("..\\folder/\x00patient.pdf") == "patient.pdf"
    assert sanitize_original_filename("..") == "document"
    assert len(sanitize_original_filename("a" * 400 + ".pdf")) == 255
