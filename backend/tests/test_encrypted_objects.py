"""Unit tests for the HCENC1 streaming object envelope."""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

import pytest

from app.storage.encrypted_objects import (
    DocumentKeyring,
    EncryptedObjectAuthenticationError,
    EncryptedObjectTooLargeError,
    EncryptionKeyUnavailableError,
    encrypt_stream_to_path,
    iter_decrypted_for_untrusted_consumer,
    verify_encrypted_object,
)


def _keyring(tmp_path: Path, *, key_id: str = "test-key") -> DocumentKeyring:
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    key_path = credentials / key_id
    key_path.write_bytes(b"k" * 32)
    os.chmod(key_path, 0o400)
    return DocumentKeyring(str(credentials), key_id)


def test_encrypt_round_trip_without_plaintext_file(tmp_path: Path) -> None:
    keyring = _keyring(tmp_path)
    document_id = uuid.uuid4()
    plaintext = (b"medical-document-content-" * 1000) + b"end"
    destination = tmp_path / "objects" / "source.hcenc"

    metadata = encrypt_stream_to_path(
        io.BytesIO(plaintext),
        destination,
        document_id=document_id,
        artifact_role="source_quarantine",
        keyring=keyring,
        max_plaintext_bytes=len(plaintext),
    )

    encrypted = destination.read_bytes()
    assert plaintext not in encrypted
    assert metadata.plaintext_size == len(plaintext)
    assert metadata.encrypted_size == len(encrypted)
    assert metadata.format == "hcenc1"
    assert metadata.key_id == "test-key"
    assert not list(destination.parent.glob(".encrypting-*"))

    recovered = b"".join(
        iter_decrypted_for_untrusted_consumer(
            destination,
            document_id=document_id,
            artifact_role="source_quarantine",
            keyring=keyring,
        )
    )
    assert recovered == plaintext
    assert verify_encrypted_object(
        destination,
        document_id=document_id,
        artifact_role="source_quarantine",
        keyring=keyring,
    ) == len(plaintext)


def test_aad_binds_document_and_artifact_role(tmp_path: Path) -> None:
    keyring = _keyring(tmp_path)
    document_id = uuid.uuid4()
    destination = tmp_path / "source.hcenc"
    encrypt_stream_to_path(
        io.BytesIO(b"content"),
        destination,
        document_id=document_id,
        artifact_role="source_quarantine",
        keyring=keyring,
        max_plaintext_bytes=100,
    )

    with pytest.raises(EncryptedObjectAuthenticationError):
        b"".join(
            iter_decrypted_for_untrusted_consumer(
                destination,
                document_id=uuid.uuid4(),
                artifact_role="source_quarantine",
                keyring=keyring,
            )
        )

    with pytest.raises(EncryptedObjectAuthenticationError):
        b"".join(
            iter_decrypted_for_untrusted_consumer(
                destination,
                document_id=document_id,
                artifact_role="safe_page",
                keyring=keyring,
            )
        )


def test_ciphertext_tampering_fails_authentication(tmp_path: Path) -> None:
    keyring = _keyring(tmp_path)
    document_id = uuid.uuid4()
    destination = tmp_path / "source.hcenc"
    encrypt_stream_to_path(
        io.BytesIO(b"content" * 100),
        destination,
        document_id=document_id,
        artifact_role="source_quarantine",
        keyring=keyring,
        max_plaintext_bytes=10_000,
    )

    payload = bytearray(destination.read_bytes())
    payload[len(payload) // 2] ^= 0x01
    destination.write_bytes(payload)

    with pytest.raises(EncryptedObjectAuthenticationError):
        b"".join(
            iter_decrypted_for_untrusted_consumer(
                destination,
                document_id=document_id,
                artifact_role="source_quarantine",
                keyring=keyring,
            )
        )


def test_oversized_source_leaves_no_object(tmp_path: Path) -> None:
    keyring = _keyring(tmp_path)
    destination = tmp_path / "source.hcenc"
    with pytest.raises(EncryptedObjectTooLargeError):
        encrypt_stream_to_path(
            io.BytesIO(b"x" * 100),
            destination,
            document_id=uuid.uuid4(),
            artifact_role="source_quarantine",
            keyring=keyring,
            max_plaintext_bytes=32,
        )
    assert not destination.exists()
    assert not list(tmp_path.glob(".encrypting-*"))


def test_each_object_uses_a_unique_nonce(tmp_path: Path) -> None:
    keyring = _keyring(tmp_path)
    document_id = uuid.uuid4()
    first = tmp_path / "first.hcenc"
    second = tmp_path / "second.hcenc"
    for destination in (first, second):
        encrypt_stream_to_path(
            io.BytesIO(b"same plaintext"),
            destination,
            document_id=document_id,
            artifact_role="source_quarantine",
            keyring=keyring,
            max_plaintext_bytes=100,
        )
    assert first.read_bytes() != second.read_bytes()


def test_keyring_rejects_symlink_and_unsafe_permissions(tmp_path: Path) -> None:
    credentials = tmp_path / "credentials"
    credentials.mkdir()
    real_key = tmp_path / "real-key"
    real_key.write_bytes(b"k" * 32)
    os.chmod(real_key, 0o400)
    (credentials / "linked-key").symlink_to(real_key)

    with pytest.raises(EncryptionKeyUnavailableError):
        DocumentKeyring(str(credentials), "linked-key").load_active()

    unsafe_key = credentials / "unsafe-key"
    unsafe_key.write_bytes(b"u" * 32)
    os.chmod(unsafe_key, 0o620)
    with pytest.raises(EncryptionKeyUnavailableError, match="permissions"):
        DocumentKeyring(str(credentials), "unsafe-key").load_active()


def test_keyring_rejects_hardlinked_key(tmp_path: Path) -> None:
    credentials = tmp_path / "credentials"
    credentials.mkdir()
    key_path = credentials / "test-key"
    key_path.write_bytes(b"k" * 32)
    os.chmod(key_path, 0o400)
    os.link(key_path, tmp_path / "second-link")

    with pytest.raises(EncryptionKeyUnavailableError, match="single-link"):
        DocumentKeyring(str(credentials), "test-key").load_active()
