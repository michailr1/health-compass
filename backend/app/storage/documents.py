"""Private quarantine storage and bounded file validation for HC-017 Slice B."""

from __future__ import annotations

import asyncio
import hashlib
import os
import struct
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

CHUNK_SIZE = 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SOF_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}
SUPPORTED_MEDIA_TYPES = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
}


class DocumentValidationError(Exception):
    """Safe validation failure that may be returned to the API client."""

    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class StoredDocument:
    storage_key: str
    original_filename: str
    declared_media_type: str
    detected_media_type: str
    byte_size: int
    sha256: str
    page_count: int | None
    image_width: int | None
    image_height: int | None


def sanitize_original_filename(value: str | None) -> str:
    """Return a display-only filename that can never influence a storage path."""

    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.replace("\\", "/").split("/")[-1]
    normalized = "".join(
        char for char in normalized if ord(char) >= 32 and ord(char) != 127
    ).strip()
    if normalized in {"", ".", ".."}:
        normalized = "document"
    return normalized[:255]


def normalize_declared_media_type(value: str | None) -> str:
    media_type = (value or "").split(";", 1)[0].strip().lower()
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise DocumentValidationError(
            "unsupported_media_type",
            "Поддерживаются только PDF, JPEG и PNG.",
        )
    return media_type


def validate_filename_extension(filename: str, media_type: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_MEDIA_TYPES[media_type]:
        raise DocumentValidationError(
            "filename_media_type_mismatch",
            "Расширение файла не соответствует заявленному формату.",
        )


def detect_media_type(prefix: bytes) -> str:
    if prefix.startswith(b"%PDF-"):
        return "application/pdf"
    if prefix.startswith(PNG_SIGNATURE):
        return "image/png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise DocumentValidationError(
        "unsupported_file_signature",
        "Формат файла не распознан или не поддерживается.",
    )


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or not header.startswith(PNG_SIGNATURE):
        raise DocumentValidationError("invalid_png", "PNG-файл повреждён.")
    if header[12:16] != b"IHDR":
        raise DocumentValidationError("invalid_png", "PNG-файл повреждён.")
    width, height = struct.unpack(">II", header[16:24])
    if width < 1 or height < 1:
        raise DocumentValidationError("invalid_png", "PNG-файл повреждён.")
    return width, height


def _read_exact(handle: BinaryIO, count: int) -> bytes:
    data = handle.read(count)
    if len(data) != count:
        raise DocumentValidationError("invalid_jpeg", "JPEG-файл повреждён.")
    return data


def _jpeg_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        if _read_exact(handle, 2) != b"\xff\xd8":
            raise DocumentValidationError("invalid_jpeg", "JPEG-файл повреждён.")

        while True:
            byte = handle.read(1)
            if not byte:
                break
            if byte != b"\xff":
                continue

            marker_byte = handle.read(1)
            while marker_byte == b"\xff":
                marker_byte = handle.read(1)
            if not marker_byte:
                break

            marker = marker_byte[0]
            if marker in {0xD8, 0xD9}:
                continue
            if marker == 0xDA:
                break

            segment_length = int.from_bytes(_read_exact(handle, 2), "big")
            if segment_length < 2:
                raise DocumentValidationError("invalid_jpeg", "JPEG-файл повреждён.")

            if marker in JPEG_SOF_MARKERS:
                segment = _read_exact(handle, segment_length - 2)
                if len(segment) < 5:
                    raise DocumentValidationError(
                        "invalid_jpeg", "JPEG-файл повреждён."
                    )
                height = int.from_bytes(segment[1:3], "big")
                width = int.from_bytes(segment[3:5], "big")
                if width < 1 or height < 1:
                    raise DocumentValidationError(
                        "invalid_jpeg", "JPEG-файл повреждён."
                    )
                return width, height

            handle.seek(segment_length - 2, os.SEEK_CUR)

    raise DocumentValidationError("invalid_jpeg", "JPEG-файл повреждён.")


def _validate_image_dimensions(
    path: Path,
    media_type: str,
    max_pixels: int,
) -> tuple[int | None, int | None]:
    if media_type == "image/png":
        width, height = _png_dimensions(path)
    elif media_type == "image/jpeg":
        width, height = _jpeg_dimensions(path)
    else:
        return None, None

    if width * height > max_pixels:
        raise DocumentValidationError(
            "image_dimensions_exceeded",
            "Изображение слишком большое для безопасной обработки.",
            status_code=413,
        )
    return width, height


class LocalDocumentStorage:
    """Development/test private filesystem adapter.

    The adapter accepts only opaque server-generated keys. It is intentionally
    not production-ready; configuration validation keeps Slice B disabled
    outside development until the scanner/object-storage slice is reviewed.
    """

    backend_name = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)

    def quarantine_key(self, document_id: uuid.UUID) -> str:
        return f"quarantine/{document_id}/original"

    def _resolve_key(self, storage_key: str) -> Path:
        relative = Path(storage_key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid storage key")
        path = (self.root / relative).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    async def write_quarantine(
        self,
        document_id: uuid.UUID,
        upload: UploadFile,
        *,
        max_bytes: int,
        max_image_pixels: int,
    ) -> StoredDocument:
        return await asyncio.to_thread(
            self._write_quarantine_sync,
            document_id,
            upload,
            max_bytes,
            max_image_pixels,
        )

    def _write_quarantine_sync(
        self,
        document_id: uuid.UUID,
        upload: UploadFile,
        max_bytes: int,
        max_image_pixels: int,
    ) -> StoredDocument:
        filename = sanitize_original_filename(upload.filename)
        declared_media_type = normalize_declared_media_type(upload.content_type)
        validate_filename_extension(filename, declared_media_type)

        storage_key = self.quarantine_key(document_id)
        destination = self._resolve_key(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(destination.parent, 0o700)
        temporary = destination.with_name(f".uploading-{uuid.uuid4()}")

        digest = hashlib.sha256()
        total = 0
        prefix = bytearray()

        try:
            upload.file.seek(0)
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "wb") as output:
                while True:
                    chunk = upload.file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise DocumentValidationError(
                            "document_too_large",
                            "Файл превышает допустимый размер.",
                            status_code=413,
                        )
                    if len(prefix) < 32:
                        prefix.extend(chunk[: 32 - len(prefix)])
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())

            if total == 0:
                raise DocumentValidationError("empty_document", "Файл пуст.")

            detected_media_type = detect_media_type(bytes(prefix))
            if detected_media_type != declared_media_type:
                raise DocumentValidationError(
                    "media_type_mismatch",
                    "Содержимое файла не соответствует заявленному формату.",
                )

            width, height = _validate_image_dimensions(
                temporary,
                detected_media_type,
                max_image_pixels,
            )

            os.replace(temporary, destination)
            os.chmod(destination, 0o600)
            return StoredDocument(
                storage_key=storage_key,
                original_filename=filename,
                declared_media_type=declared_media_type,
                detected_media_type=detected_media_type,
                byte_size=total,
                sha256=digest.hexdigest(),
                # PDF page counting is performed by the restricted inspection
                # worker in Slice C before a document can leave quarantine.
                page_count=None,
                image_width=width,
                image_height=height,
            )
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            try:
                destination.parent.rmdir()
            except OSError:
                pass
            raise

    async def delete(self, storage_key: str) -> None:
        await asyncio.to_thread(self._delete_sync, storage_key)

    def _delete_sync(self, storage_key: str) -> None:
        path = self._resolve_key(storage_key)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass
