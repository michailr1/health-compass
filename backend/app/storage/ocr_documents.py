"""Encrypted storage for machine OCR TSV provenance artifacts."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.storage.encrypted_objects import (
    DocumentKeyring,
    EncryptedObjectMetadata,
    encrypt_stream_to_path,
)


def ocr_artifact_role(artifact_id: uuid.UUID) -> str:
    return f"ocr:{artifact_id.hex[:24]}"


@dataclass(frozen=True)
class StoredOCRArtifact:
    id: uuid.UUID
    page_artifact_id: uuid.UUID
    page_number: int
    storage_key: str
    metadata: EncryptedObjectMetadata

    @property
    def artifact_role(self) -> str:
        return ocr_artifact_role(self.id)


class OCRDocumentStorage:
    """Opaque encrypted OCR namespace for the restricted OCR worker."""

    def __init__(
        self,
        root: str,
        *,
        keyring: DocumentKeyring,
        min_free_bytes: int,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.keyring = keyring
        self.min_free_bytes = min_free_bytes
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)

    def _resolve_key(self, storage_key: str) -> Path:
        relative = Path(storage_key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid OCR object key")
        path = self.root / relative
        resolved_parent = path.parent.resolve(strict=False)
        if resolved_parent != self.root and self.root not in resolved_parent.parents:
            raise ValueError("Invalid OCR object key")
        return path

    @staticmethod
    def artifact_key(
        document_id: uuid.UUID,
        run_id: uuid.UUID,
        page_number: int,
    ) -> str:
        if page_number < 1 or page_number > 50:
            raise ValueError("Invalid OCR page number")
        return f"ocr/{document_id}/{run_id}/page-{page_number}.tsv.hcenc"

    def path_for_key(self, storage_key: str) -> Path:
        return self._resolve_key(storage_key)

    def store_tsv(
        self,
        descriptor: int,
        *,
        document_id: uuid.UUID,
        run_id: uuid.UUID,
        artifact_id: uuid.UUID,
        page_artifact_id: uuid.UUID,
        page_number: int,
        max_plaintext_bytes: int,
    ) -> StoredOCRArtifact:
        key = self.artifact_key(document_id, run_id, page_number)
        role = ocr_artifact_role(artifact_id)
        with os.fdopen(os.dup(descriptor), "rb") as source:
            source.seek(0)
            metadata = encrypt_stream_to_path(
                source,
                self._resolve_key(key),
                document_id=document_id,
                artifact_role=role,
                keyring=self.keyring,
                max_plaintext_bytes=max_plaintext_bytes,
                min_free_bytes=self.min_free_bytes,
            )
        return StoredOCRArtifact(
            id=artifact_id,
            page_artifact_id=page_artifact_id,
            page_number=page_number,
            storage_key=key,
            metadata=metadata,
        )

    def delete_key(self, storage_key: str) -> None:
        path = self._resolve_key(storage_key)
        path.unlink(missing_ok=True)
        parent = path.parent
        while parent != self.root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
