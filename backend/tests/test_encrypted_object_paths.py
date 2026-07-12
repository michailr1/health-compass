"""Filesystem-boundary regression tests for encrypted document objects."""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

import pytest

from app.storage.encrypted_objects import (
    DocumentKeyring,
    EncryptedObjectAlreadyExistsError,
    EncryptedObjectFormatError,
    EncryptionKeyUnavailableError,
    encrypt_stream_to_path,
    verify_encrypted_object,
)


def _keyring(tmp_path: Path) -> DocumentKeyring:
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    key_path = credentials / "active-key"
    key_path.write_bytes(b"k" * 32)
    os.chmod(key_path, 0o400)
    return DocumentKeyring(str(credentials), "active-key")


def test_keyring_rejects_symlink_to_another_key_in_same_directory(
    tmp_path: Path,
) -> None:
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    target = credentials / "real-key"
    target.write_bytes(b"k" * 32)
    os.chmod(target, 0o400)
    (credentials / "alias-key").symlink_to(target.name)

    with pytest.raises(EncryptionKeyUnavailableError):
        DocumentKeyring(str(credentials), "alias-key").load_active()


def test_existing_destination_is_never_overwritten_or_deleted(tmp_path: Path) -> None:
    keyring = _keyring(tmp_path)
    destination = tmp_path / "objects" / "source.hcenc"
    destination.parent.mkdir()
    destination.write_bytes(b"existing-object")
    os.chmod(destination, 0o600)

    with pytest.raises(EncryptedObjectAlreadyExistsError):
        encrypt_stream_to_path(
            io.BytesIO(b"new plaintext"),
            destination,
            document_id=uuid.uuid4(),
            artifact_role="source_quarantine",
            keyring=keyring,
            max_plaintext_bytes=1024,
        )

    assert destination.read_bytes() == b"existing-object"
    assert not list(destination.parent.glob(".encrypting-*"))


def test_encrypted_reader_rejects_final_symlink(tmp_path: Path) -> None:
    keyring = _keyring(tmp_path)
    document_id = uuid.uuid4()
    real_object = tmp_path / "real.hcenc"
    encrypt_stream_to_path(
        io.BytesIO(b"private document"),
        real_object,
        document_id=document_id,
        artifact_role="source_quarantine",
        keyring=keyring,
        max_plaintext_bytes=1024,
    )
    alias = tmp_path / "alias.hcenc"
    alias.symlink_to(real_object.name)

    with pytest.raises((EncryptedObjectFormatError, OSError)):
        verify_encrypted_object(
            alias,
            document_id=document_id,
            artifact_role="source_quarantine",
            keyring=keyring,
        )
