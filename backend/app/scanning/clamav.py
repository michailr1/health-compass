"""Strict local ClamAV clamd client for encrypted document workers."""

from __future__ import annotations

import datetime
import re
import socket
import struct
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.storage.encrypted_objects import (
    DocumentKeyring,
    EncryptedObjectAuthenticationError,
    EncryptedObjectError,
    iter_decrypted_for_untrusted_consumer,
)

_MAX_RESPONSE_BYTES = 2048
_VERSION_RE = re.compile(r"^ClamAV (?P<engine>[^/]+)/(?P<signatures>[^/]+)/(?P<date>.+)$")


class ScannerError(Exception):
    """Base class for safe fail-closed scanner errors."""


class ScannerUnavailableError(ScannerError):
    pass


class ScannerProtocolError(ScannerError):
    pass


class ScannerSignatureStaleError(ScannerError):
    pass


class ScannerStreamTooLargeError(ScannerError):
    pass


class ScannerEncryptedObjectError(ScannerError):
    pass


@dataclass(frozen=True)
class ScannerVersion:
    engine: str
    engine_version: str
    signature_version: str
    signature_timestamp: datetime.datetime


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    infected: bool
    version: ScannerVersion


class ClamAVClient:
    """Use clamd over a local Unix socket with the INSTREAM protocol."""

    def __init__(
        self,
        socket_path: str,
        *,
        timeout_seconds: int,
        max_stream_bytes: int,
        max_signature_age_hours: int,
    ) -> None:
        self.socket_path = socket_path
        self.timeout_seconds = timeout_seconds
        self.max_stream_bytes = max_stream_bytes
        self.max_signature_age = datetime.timedelta(hours=max_signature_age_hours)

    def _connect(self) -> socket.socket:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.timeout_seconds)
        try:
            connection.connect(self.socket_path)
        except OSError as exc:
            connection.close()
            raise ScannerUnavailableError("Document scanner is unavailable") from exc
        return connection

    @staticmethod
    def _read_response(connection: socket.socket) -> str:
        chunks = bytearray()
        while len(chunks) <= _MAX_RESPONSE_BYTES:
            try:
                chunk = connection.recv(256)
            except OSError as exc:
                raise ScannerUnavailableError("Document scanner response failed") from exc
            if not chunk:
                break
            terminator = chunk.find(b"\x00")
            if terminator >= 0:
                chunks.extend(chunk[:terminator])
                break
            chunks.extend(chunk)
        if not chunks or len(chunks) > _MAX_RESPONSE_BYTES:
            raise ScannerProtocolError("Invalid document scanner response")
        try:
            return chunks.decode("utf-8", errors="strict").strip()
        except UnicodeDecodeError as exc:
            raise ScannerProtocolError("Invalid document scanner response encoding") from exc

    def version(self) -> ScannerVersion:
        with self._connect() as connection:
            try:
                connection.sendall(b"zVERSION\x00")
            except OSError as exc:
                raise ScannerUnavailableError("Document scanner command failed") from exc
            response = self._read_response(connection)

        match = _VERSION_RE.fullmatch(response)
        if match is None:
            raise ScannerProtocolError("Unexpected document scanner version response")

        engine_version = match.group("engine").strip()
        signature_version = match.group("signatures").strip()
        raw_date = match.group("date").strip()
        try:
            signature_timestamp = datetime.datetime.strptime(
                raw_date,
                "%a %b %d %H:%M:%S %Y",
            ).replace(tzinfo=datetime.UTC)
        except ValueError as exc:
            raise ScannerProtocolError("Invalid scanner signature timestamp") from exc

        now = datetime.datetime.now(datetime.UTC)
        age = now - signature_timestamp
        if age < -datetime.timedelta(hours=1) or age > self.max_signature_age:
            raise ScannerSignatureStaleError("Document scanner signatures are stale")

        return ScannerVersion(
            engine="clamav",
            engine_version=engine_version,
            signature_version=signature_version,
            signature_timestamp=signature_timestamp,
        )

    def scan_chunks(
        self,
        chunks: Iterable[bytes],
        *,
        version: ScannerVersion,
    ) -> ScanResult:
        total = 0
        with self._connect() as connection:
            try:
                connection.sendall(b"zINSTREAM\x00")
                for chunk in chunks:
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > self.max_stream_bytes:
                        raise ScannerStreamTooLargeError(
                            "Document exceeds scanner stream limit"
                        )
                    connection.sendall(struct.pack("!I", len(chunk)))
                    connection.sendall(chunk)
                # This terminator is sent only after the encrypted object has
                # reached GCM finalize successfully. A corrupted object therefore
                # cannot receive a clean scanner result.
                connection.sendall(struct.pack("!I", 0))
            except ScannerError:
                raise
            except OSError as exc:
                raise ScannerUnavailableError("Document scanner stream failed") from exc
            response = self._read_response(connection)

        if response == "stream: OK":
            return ScanResult(clean=True, infected=False, version=version)
        if response.startswith("stream: ") and response.endswith(" FOUND"):
            return ScanResult(clean=False, infected=True, version=version)
        if response.startswith("stream: ") and response.endswith(" ERROR"):
            raise ScannerProtocolError("Document scanner rejected the stream")
        raise ScannerProtocolError("Unexpected document scanner result")

    def scan_encrypted_object(
        self,
        source_path: Path,
        *,
        document_id: uuid.UUID,
        artifact_role: str,
        keyring: DocumentKeyring,
    ) -> ScanResult:
        version = self.version()
        try:
            chunks = iter_decrypted_for_untrusted_consumer(
                source_path,
                document_id=document_id,
                artifact_role=artifact_role,
                keyring=keyring,
            )
            return self.scan_chunks(chunks, version=version)
        except EncryptedObjectAuthenticationError as exc:
            raise ScannerEncryptedObjectError(
                "Encrypted document authentication failed before scan completion"
            ) from exc
        except EncryptedObjectError as exc:
            raise ScannerEncryptedObjectError(
                "Encrypted document could not be read for scanning"
            ) from exc
