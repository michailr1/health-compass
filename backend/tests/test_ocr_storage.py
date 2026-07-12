"""Unit tests for encrypted OCR TSV provenance objects."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.storage.encrypted_objects import (
    DocumentKeyring,
    iter_decrypted_for_untrusted_consumer,
)
from app.storage.ocr_documents import OCRDocumentStorage, ocr_artifact_role


def _keyring(tmp_path: Path) -> DocumentKeyring:
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    key_path = credentials / "test-key"
    key_path.write_bytes(b"k" * 32)
    os.chmod(key_path, 0o400)
    return DocumentKeyring(str(credentials), "test-key")


def test_tsv_is_encrypted_under_an_opaque_run_key(tmp_path: Path) -> None:
    keyring = _keyring(tmp_path)
    storage = OCRDocumentStorage(
        str(tmp_path / "objects"),
        keyring=keyring,
        min_free_bytes=0,
    )
    document_id = uuid.uuid4()
    run_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    page_artifact_id = uuid.uuid4()
    plaintext = b"level\tpage_num\ttext\n5\t1\tprivate-value\n"
    flags = getattr(os, "MFD_CLOEXEC", 0) | getattr(os, "MFD_ALLOW_SEALING", 0)
    descriptor = os.memfd_create("hc-ocr-storage-test", flags)
    try:
        os.write(descriptor, plaintext)
        os.lseek(descriptor, 0, os.SEEK_SET)
        stored = storage.store_tsv(
            descriptor,
            document_id=document_id,
            run_id=run_id,
            artifact_id=artifact_id,
            page_artifact_id=page_artifact_id,
            page_number=1,
            max_plaintext_bytes=1024,
        )
    finally:
        os.close(descriptor)

    assert stored.storage_key == f"ocr/{document_id}/{run_id}/page-1.tsv.hcenc"
    encrypted = storage.path_for_key(stored.storage_key).read_bytes()
    assert b"private-value" not in encrypted
    recovered = b"".join(
        iter_decrypted_for_untrusted_consumer(
            storage.path_for_key(stored.storage_key),
            document_id=document_id,
            artifact_role=ocr_artifact_role(artifact_id),
            keyring=keyring,
        )
    )
    assert recovered == plaintext
    assert stored.metadata.plaintext_size == len(plaintext)
    assert stored.metadata.encrypted_size > len(plaintext)
