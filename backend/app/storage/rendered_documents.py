"""Encrypted storage helpers for accepted sources and safe page artifacts."""

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


@dataclass(frozen=True)
class StoredPageArtifact:
    id: uuid.UUID
    page_number: int
    storage_key: str
    metadata: EncryptedObjectMetadata
    width: int
    height: int

    @property
    def artifact_role(self) -> str:
        # 96 bits from the random artifact UUID fit the HCENC1 role bound and
        # prevent same-document page ciphertext from being silently swapped.
        return f"page:{self.id.hex[:24]}"


class RenderedDocumentStorage:
    """Opaque encrypted object namespace used only by restricted workers."""

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
            raise ValueError("Invalid document object key")
        path = self.root / relative
        resolved_parent = path.parent.resolve(strict=False)
        if resolved_parent != self.root and self.root not in resolved_parent.parents:
            raise ValueError("Invalid document object key")
        return path

    @staticmethod
    def accepted_key(document_id: uuid.UUID) -> str:
        return f"accepted/{document_id}/original.hcenc"

    @staticmethod
    def page_key(
        document_id: uuid.UUID,
        run_id: uuid.UUID,
        page_number: int,
    ) -> str:
        if page_number < 1 or page_number > 50:
            raise ValueError("Invalid safe page number")
        return f"derived/{document_id}/{run_id}/page-{page_number}.png.hcenc"

    def path_for_key(self, storage_key: str) -> Path:
        return self._resolve_key(storage_key)

    def store_accepted_source(
        self,
        verified_descriptor: int,
        *,
        document_id: uuid.UUID,
        max_plaintext_bytes: int,
    ) -> tuple[str, EncryptedObjectMetadata]:
        key = self.accepted_key(document_id)
        with os.fdopen(os.dup(verified_descriptor), "rb") as source:
            source.seek(0)
            metadata = encrypt_stream_to_path(
                source,
                self._resolve_key(key),
                document_id=document_id,
                artifact_role="source_accepted",
                keyring=self.keyring,
                max_plaintext_bytes=max_plaintext_bytes,
                min_free_bytes=self.min_free_bytes,
            )
        return key, metadata

    def store_page(
        self,
        page_descriptor: int,
        *,
        document_id: uuid.UUID,
        run_id: uuid.UUID,
        artifact_id: uuid.UUID,
        page_number: int,
        width: int,
        height: int,
        max_plaintext_bytes: int,
    ) -> StoredPageArtifact:
        key = self.page_key(document_id, run_id, page_number)
        artifact = StoredPageArtifact(
            id=artifact_id,
            page_number=page_number,
            storage_key=key,
            metadata=EncryptedObjectMetadata(
                format="",
                key_id="",
                plaintext_size=0,
                encrypted_size=0,
                plaintext_sha256="",
            ),
            width=width,
            height=height,
        )
        with os.fdopen(os.dup(page_descriptor), "rb") as source:
            source.seek(0)
            metadata = encrypt_stream_to_path(
                source,
                self._resolve_key(key),
                document_id=document_id,
                artifact_role=artifact.artifact_role,
                keyring=self.keyring,
                max_plaintext_bytes=max_plaintext_bytes,
                min_free_bytes=self.min_free_bytes,
            )
        return StoredPageArtifact(
            id=artifact_id,
            page_number=page_number,
            storage_key=key,
            metadata=metadata,
            width=width,
            height=height,
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
