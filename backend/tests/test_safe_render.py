"""Unit tests for sealed-memory and rendered PNG validation."""

from __future__ import annotations

import fcntl
import io
import os
import struct
import uuid
import zlib
from pathlib import Path

import pytest

from app.rendering.safe_render import (
    InvalidRenderedImageError,
    RenderLimits,
    SafeDocumentRenderer,
    validate_png_descriptor,
)
from app.rendering.verified_memory import verified_document_memfd
from app.storage.encrypted_objects import DocumentKeyring, encrypt_stream_to_path


def _renderer() -> SafeDocumentRenderer:
    return SafeDocumentRenderer(
        pdfinfo_path="/usr/bin/pdfinfo",
        pdftocairo_path="/usr/bin/pdftocairo",
        magick_path="/usr/bin/magick",
        limits=RenderLimits(
            timeout_seconds=5,
            cpu_seconds=2,
            memory_bytes=128 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_pixels=1_000_000,
            max_pages=10,
            dpi=150,
        ),
    )


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def _png(width: int = 1, height: int = 1) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + (b"\x00\x00\x00" * width)
    pixels = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(pixels))
        + _png_chunk(b"IEND", b"")
    )


def _descriptor(payload: bytes) -> int:
    flags = getattr(os, "MFD_CLOEXEC", 0) | getattr(os, "MFD_ALLOW_SEALING", 0)
    descriptor = os.memfd_create("hc-test-png", flags)
    os.write(descriptor, payload)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return descriptor


def _keyring(tmp_path: Path) -> DocumentKeyring:
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    key_path = credentials / "test-key"
    key_path.write_bytes(b"k" * 32)
    os.chmod(key_path, 0o400)
    return DocumentKeyring(str(credentials), "test-key")


def test_renderer_output_memfd_can_be_sealed_read_only() -> None:
    descriptor = _renderer()._new_memfd("hc-render-test")
    try:
        os.write(descriptor, b"rendered")
        _renderer()._seal_readonly(descriptor)
        seals = fcntl.fcntl(descriptor, fcntl.F_GET_SEALS)
        assert seals & fcntl.F_SEAL_WRITE
        with pytest.raises(OSError):
            os.write(descriptor, b"x")
    finally:
        os.close(descriptor)


def test_valid_png_is_structurally_verified() -> None:
    descriptor = _descriptor(_png(4, 3))
    try:
        assert validate_png_descriptor(
            descriptor,
            max_bytes=1024 * 1024,
            max_pixels=100,
        ) == (4, 3)
    finally:
        os.close(descriptor)


def test_png_crc_and_metadata_are_rejected() -> None:
    corrupted = bytearray(_png())
    corrupted[-1] ^= 0x01
    descriptor = _descriptor(bytes(corrupted))
    try:
        with pytest.raises(InvalidRenderedImageError, match="CRC"):
            validate_png_descriptor(
                descriptor,
                max_bytes=1024 * 1024,
                max_pixels=100,
            )
    finally:
        os.close(descriptor)

    payload = _png()[:-12] + _png_chunk(b"tEXt", b"patient=name") + _png_chunk(b"IEND", b"")
    descriptor = _descriptor(payload)
    try:
        with pytest.raises(InvalidRenderedImageError, match="disallowed metadata"):
            validate_png_descriptor(
                descriptor,
                max_bytes=1024 * 1024,
                max_pixels=100,
            )
    finally:
        os.close(descriptor)


def test_verified_memfd_is_exposed_only_after_gcm_authentication(tmp_path: Path) -> None:
    keyring = _keyring(tmp_path)
    document_id = uuid.uuid4()
    plaintext = b"verified medical document"
    source = tmp_path / "source.hcenc"
    encrypt_stream_to_path(
        io.BytesIO(plaintext),
        source,
        document_id=document_id,
        artifact_role="source_quarantine",
        keyring=keyring,
        max_plaintext_bytes=1024,
    )

    with verified_document_memfd(
        source,
        document_id=document_id,
        artifact_role="source_quarantine",
        keyring=keyring,
        max_plaintext_bytes=1024,
    ) as descriptor:
        assert os.read(descriptor, len(plaintext)) == plaintext
        seals = fcntl.fcntl(descriptor, fcntl.F_GET_SEALS)
        assert seals & fcntl.F_SEAL_WRITE
        with pytest.raises(OSError):
            os.write(descriptor, b"x")
