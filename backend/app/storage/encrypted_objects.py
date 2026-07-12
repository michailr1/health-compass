"""Versioned streaming authenticated encryption for private document objects."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import struct
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"HCENC1"
FORMAT_VERSION = "hcenc1"
NONCE_SIZE = 12
TAG_SIZE = 16
KEY_SIZE = 32
MAX_KEY_ID_BYTES = 64
MAX_ROLE_BYTES = 32
CHUNK_SIZE = 1024 * 1024
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class EncryptedObjectError(Exception):
    """Base class for safe encrypted-object failures."""


class EncryptedObjectFormatError(EncryptedObjectError):
    """Envelope structure is invalid or unsupported."""


class EncryptedObjectAuthenticationError(EncryptedObjectError):
    """Ciphertext authentication failed."""


class EncryptionKeyUnavailableError(EncryptedObjectError):
    """Requested key ID is unavailable or unsafe."""


class EncryptedObjectTooLargeError(EncryptedObjectError):
    """Plaintext exceeds the configured object limit."""


class EncryptedObjectStorageFullError(EncryptedObjectError):
    """Reserved free-space floor would be crossed."""


@dataclass(frozen=True)
class EncryptedObjectMetadata:
    format: str
    key_id: str
    plaintext_size: int
    encrypted_size: int
    plaintext_sha256: str


@dataclass(frozen=True)
class EnvelopeHeader:
    key_id: str
    nonce: bytes
    raw: bytes
    header_size: int


class DocumentKeyring:
    """Read fixed-length binary AES keys from a protected credential directory."""

    def __init__(self, credentials_directory: str, active_key_id: str) -> None:
        self.directory = Path(credentials_directory).expanduser().resolve()
        self.active_key_id = self._validate_key_id(active_key_id)

    @staticmethod
    def _validate_key_id(value: str) -> str:
        if not _KEY_ID_RE.fullmatch(value):
            raise EncryptionKeyUnavailableError("Invalid document encryption key ID")
        return value

    def key_path(self, key_id: str) -> Path:
        validated = self._validate_key_id(key_id)
        path = (self.directory / validated).resolve(strict=False)
        if path.parent != self.directory:
            raise EncryptionKeyUnavailableError("Invalid document encryption key path")
        return path

    def load(self, key_id: str) -> bytes:
        path = self.key_path(key_id)
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor: int | None = None
        try:
            descriptor = os.open(path, flags)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise EncryptionKeyUnavailableError(
                    "Document encryption key must be a regular single-link file"
                )
            if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise EncryptionKeyUnavailableError(
                    "Document encryption key permissions are unsafe"
                )
            key = os.read(descriptor, KEY_SIZE + 1)
        except EncryptionKeyUnavailableError:
            raise
        except OSError as exc:
            raise EncryptionKeyUnavailableError(
                "Document encryption key is unavailable"
            ) from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
        if len(key) != KEY_SIZE:
            raise EncryptionKeyUnavailableError(
                "Document encryption key must contain exactly 32 bytes"
            )
        return key

    def load_active(self) -> tuple[str, bytes]:
        return self.active_key_id, self.load(self.active_key_id)


def _role_bytes(artifact_role: str) -> bytes:
    try:
        encoded = artifact_role.encode("ascii", errors="strict")
    except UnicodeEncodeError as exc:
        raise EncryptedObjectFormatError(
            "Invalid encrypted object artifact role"
        ) from exc
    if not encoded or len(encoded) > MAX_ROLE_BYTES:
        raise EncryptedObjectFormatError("Invalid encrypted object artifact role")
    return encoded


def _aad(header: bytes, document_id: uuid.UUID, artifact_role: str) -> bytes:
    role = _role_bytes(artifact_role)
    return header + document_id.bytes + struct.pack("!B", len(role)) + role


def _safe_open_exclusive(path: Path) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return os.open(path, flags, 0o600)


def _safe_open_readonly(path: Path) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        os.close(descriptor)
        raise EncryptedObjectFormatError(
            "Encrypted object must be a regular single-link file"
        )
    return descriptor


def _check_free_space(path: Path, reserve_bytes: int) -> None:
    if reserve_bytes <= 0:
        return
    free = shutil.disk_usage(path).free
    if free < reserve_bytes:
        raise EncryptedObjectStorageFullError(
            "Reserved document-storage free space would be crossed"
        )


def encrypt_stream_to_path(
    source: BinaryIO,
    destination: Path,
    *,
    document_id: uuid.UUID,
    artifact_role: str,
    keyring: DocumentKeyring,
    max_plaintext_bytes: int,
    min_free_bytes: int = 0,
) -> EncryptedObjectMetadata:
    """Encrypt one object atomically without writing plaintext to persistent storage."""

    key_id, key = keyring.load_active()
    key_id_bytes = key_id.encode("ascii")
    if len(key_id_bytes) > MAX_KEY_ID_BYTES:
        raise EncryptionKeyUnavailableError("Document encryption key ID is too long")

    nonce = os.urandom(NONCE_SIZE)
    header = MAGIC + struct.pack("!B", len(key_id_bytes)) + key_id_bytes + nonce
    associated_data = _aad(header, document_id, artifact_role)

    destination = destination.resolve(strict=False)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination.parent, 0o700)
    _check_free_space(destination.parent, min_free_bytes + max_plaintext_bytes)

    temporary = destination.with_name(f".encrypting-{uuid.uuid4().hex}")
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(associated_data)

    plaintext_size = 0
    digest = hashlib.sha256()
    descriptor: int | None = None
    try:
        source.seek(0)
        descriptor = _safe_open_exclusive(temporary)
        with os.fdopen(descriptor, "wb") as output:
            descriptor = None
            output.write(header)
            while True:
                chunk = source.read(CHUNK_SIZE)
                if not chunk:
                    break
                plaintext_size += len(chunk)
                if plaintext_size > max_plaintext_bytes:
                    raise EncryptedObjectTooLargeError(
                        "Document exceeds the configured encrypted-object limit"
                    )
                if plaintext_size % (4 * CHUNK_SIZE) < len(chunk):
                    _check_free_space(destination.parent, min_free_bytes)
                digest.update(chunk)
                output.write(encryptor.update(chunk))

            output.write(encryptor.finalize())
            output.write(encryptor.tag)
            output.flush()
            os.fsync(output.fileno())

        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
        encrypted_size = destination.stat().st_size
        return EncryptedObjectMetadata(
            format=FORMAT_VERSION,
            key_id=key_id,
            plaintext_size=plaintext_size,
            encrypted_size=encrypted_size,
            plaintext_sha256=digest.hexdigest(),
        )
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise


def read_envelope_header(source: BinaryIO) -> EnvelopeHeader:
    magic = source.read(len(MAGIC))
    if magic != MAGIC:
        raise EncryptedObjectFormatError("Unknown encrypted object format")
    length_raw = source.read(1)
    if len(length_raw) != 1:
        raise EncryptedObjectFormatError("Truncated encrypted object header")
    key_id_length = length_raw[0]
    if key_id_length < 1 or key_id_length > MAX_KEY_ID_BYTES:
        raise EncryptedObjectFormatError("Invalid encrypted object key ID length")
    key_id_bytes = source.read(key_id_length)
    nonce = source.read(NONCE_SIZE)
    if len(key_id_bytes) != key_id_length or len(nonce) != NONCE_SIZE:
        raise EncryptedObjectFormatError("Truncated encrypted object header")
    try:
        key_id = key_id_bytes.decode("ascii")
    except UnicodeDecodeError as exc:
        raise EncryptedObjectFormatError("Invalid encrypted object key ID") from exc
    DocumentKeyring._validate_key_id(key_id)
    raw = magic + length_raw + key_id_bytes + nonce
    return EnvelopeHeader(
        key_id=key_id,
        nonce=nonce,
        raw=raw,
        header_size=len(raw),
    )


def iter_decrypted_for_untrusted_consumer(
    source_path: Path,
    *,
    document_id: uuid.UUID,
    artifact_role: str,
    keyring: DocumentKeyring,
    chunk_size: int = CHUNK_SIZE,
) -> Iterator[bytes]:
    """Yield plaintext to a malware scanner and verify the final GCM tag.

    The consumer may see plaintext before authentication completes. This helper
    is therefore restricted to an untrusted malware scanner. Parser/rendering
    code must verify the complete envelope before it receives plaintext.
    """

    descriptor = _safe_open_readonly(source_path.resolve(strict=False))
    with os.fdopen(descriptor, "rb") as source:
        metadata = os.fstat(source.fileno())
        total_size = metadata.st_size
        header = read_envelope_header(source)
        ciphertext_size = total_size - header.header_size - TAG_SIZE
        if ciphertext_size < 0:
            raise EncryptedObjectFormatError("Truncated encrypted object")
        source.seek(total_size - TAG_SIZE)
        tag = source.read(TAG_SIZE)
        if len(tag) != TAG_SIZE:
            raise EncryptedObjectFormatError("Missing encrypted object tag")
        key = keyring.load(header.key_id)
        decryptor = Cipher(
            algorithms.AES(key),
            modes.GCM(header.nonce, tag),
        ).decryptor()
        decryptor.authenticate_additional_data(
            _aad(header.raw, document_id, artifact_role)
        )
        source.seek(header.header_size)
        remaining = ciphertext_size
        try:
            while remaining:
                chunk = source.read(min(chunk_size, remaining))
                if not chunk:
                    raise EncryptedObjectFormatError(
                        "Truncated encrypted object ciphertext"
                    )
                remaining -= len(chunk)
                plaintext = decryptor.update(chunk)
                if plaintext:
                    yield plaintext
            tail = decryptor.finalize()
            if tail:
                yield tail
        except InvalidTag as exc:
            raise EncryptedObjectAuthenticationError(
                "Encrypted document authentication failed"
            ) from exc


def verify_encrypted_object(
    source_path: Path,
    *,
    document_id: uuid.UUID,
    artifact_role: str,
    keyring: DocumentKeyring,
) -> int:
    """Verify a complete object without persisting plaintext."""

    plaintext_size = 0
    for chunk in iter_decrypted_for_untrusted_consumer(
        source_path,
        document_id=document_id,
        artifact_role=artifact_role,
        keyring=keyring,
    ):
        plaintext_size += len(chunk)
    return plaintext_size
