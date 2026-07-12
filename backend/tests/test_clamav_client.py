"""Unit tests for the local ClamAV Unix-socket client."""

from __future__ import annotations

import datetime
import io
import os
import socket
import struct
import threading
import uuid
from pathlib import Path

import pytest

from app.scanning.clamav import (
    ClamAVClient,
    ScannerEncryptedObjectError,
    ScannerSignatureStaleError,
)
from app.storage.encrypted_objects import DocumentKeyring, encrypt_stream_to_path


def _keyring(tmp_path: Path) -> DocumentKeyring:
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    key_path = credentials / "test-key"
    key_path.write_bytes(b"k" * 32)
    os.chmod(key_path, 0o400)
    return DocumentKeyring(str(credentials), "test-key")


def _encrypted_source(
    tmp_path: Path,
    *,
    document_id: uuid.UUID,
    payload: bytes,
) -> tuple[Path, DocumentKeyring]:
    keyring = _keyring(tmp_path)
    path = tmp_path / "source.hcenc"
    encrypt_stream_to_path(
        io.BytesIO(payload),
        path,
        document_id=document_id,
        artifact_role="source_quarantine",
        keyring=keyring,
        max_plaintext_bytes=len(payload) + 1,
    )
    return path, keyring


def _read_exact(connection: socket.socket, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def _read_null_command(connection: socket.socket) -> bytes:
    data = bytearray()
    while not data.endswith(b"\x00"):
        # Read exactly through the command terminator. A larger recv() may also
        # consume the first INSTREAM frame because Unix sockets are streams.
        chunk = connection.recv(1)
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def _serve_version_and_scan(
    socket_path: Path,
    *,
    scan_response: bytes,
    signature_time: datetime.datetime,
    received: bytearray,
) -> threading.Thread:
    ready = threading.Event()

    def server() -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(socket_path))
            listener.listen(2)
            ready.set()

            with listener.accept()[0] as connection:
                assert _read_null_command(connection) == b"zVERSION\x00"
                formatted = signature_time.strftime("%a %b %d %H:%M:%S %Y")
                connection.sendall(f"ClamAV 1.4.3/27800/{formatted}\x00".encode())

            with listener.accept()[0] as connection:
                assert _read_null_command(connection) == b"zINSTREAM\x00"
                while True:
                    length_raw = _read_exact(connection, 4)
                    if len(length_raw) != 4:
                        return
                    length = struct.unpack("!I", length_raw)[0]
                    if length == 0:
                        break
                    chunk = _read_exact(connection, length)
                    if len(chunk) != length:
                        return
                    received.extend(chunk)
                connection.sendall(scan_response)

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)
    return thread


def _client(socket_path: Path) -> ClamAVClient:
    return ClamAVClient(
        str(socket_path),
        timeout_seconds=2,
        max_stream_bytes=1024 * 1024,
        max_signature_age_hours=48,
    )


def test_clean_encrypted_document_is_streamed_after_decryption(tmp_path: Path) -> None:
    document_id = uuid.uuid4()
    payload = b"private medical document" * 100
    source, keyring = _encrypted_source(
        tmp_path,
        document_id=document_id,
        payload=payload,
    )
    socket_path = tmp_path / "clamd.sock"
    received = bytearray()
    thread = _serve_version_and_scan(
        socket_path,
        scan_response=b"stream: OK\x00",
        signature_time=datetime.datetime.now(datetime.UTC),
        received=received,
    )

    result = _client(socket_path).scan_encrypted_object(
        source,
        document_id=document_id,
        artifact_role="source_quarantine",
        keyring=keyring,
    )
    thread.join(timeout=2)

    assert result.clean is True
    assert result.infected is False
    assert result.version.engine == "clamav"
    assert bytes(received) == payload


def test_found_response_is_mapped_without_exposing_signature_name(tmp_path: Path) -> None:
    document_id = uuid.uuid4()
    source, keyring = _encrypted_source(
        tmp_path,
        document_id=document_id,
        payload=b"test payload",
    )
    socket_path = tmp_path / "clamd.sock"
    received = bytearray()
    thread = _serve_version_and_scan(
        socket_path,
        scan_response=b"stream: Test-Signature FOUND\x00",
        signature_time=datetime.datetime.now(datetime.UTC),
        received=received,
    )

    result = _client(socket_path).scan_encrypted_object(
        source,
        document_id=document_id,
        artifact_role="source_quarantine",
        keyring=keyring,
    )
    thread.join(timeout=2)

    assert result.clean is False
    assert result.infected is True
    assert not hasattr(result, "signature_name")


def test_stale_signatures_fail_before_document_stream(tmp_path: Path) -> None:
    socket_path = tmp_path / "clamd.sock"
    ready = threading.Event()

    def server() -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(socket_path))
            listener.listen(1)
            ready.set()
            with listener.accept()[0] as connection:
                assert _read_null_command(connection) == b"zVERSION\x00"
                old = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=5)
                formatted = old.strftime("%a %b %d %H:%M:%S %Y")
                connection.sendall(f"ClamAV 1.4.3/27000/{formatted}\x00".encode())

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert ready.wait(timeout=2)

    with pytest.raises(ScannerSignatureStaleError):
        _client(socket_path).version()
    thread.join(timeout=2)


def test_tampered_encrypted_document_never_receives_clean_result(tmp_path: Path) -> None:
    document_id = uuid.uuid4()
    source, keyring = _encrypted_source(
        tmp_path,
        document_id=document_id,
        payload=b"content" * 100,
    )
    payload = bytearray(source.read_bytes())
    payload[len(payload) // 2] ^= 0x01
    source.write_bytes(payload)

    socket_path = tmp_path / "clamd.sock"
    received = bytearray()
    thread = _serve_version_and_scan(
        socket_path,
        scan_response=b"stream: OK\x00",
        signature_time=datetime.datetime.now(datetime.UTC),
        received=received,
    )

    with pytest.raises(ScannerEncryptedObjectError):
        _client(socket_path).scan_encrypted_object(
            source,
            document_id=document_id,
            artifact_role="source_quarantine",
            keyring=keyring,
        )
    thread.join(timeout=2)
    assert not thread.is_alive()
