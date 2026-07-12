"""Verified in-memory plaintext handles for restricted renderers."""

from __future__ import annotations

import contextlib
import fcntl
import os
import uuid
from collections.abc import Iterator
from pathlib import Path

from app.storage.encrypted_objects import (
    DocumentKeyring,
    iter_decrypted_for_untrusted_consumer,
)


class VerifiedMemoryUnavailableError(RuntimeError):
    """The host cannot provide the required sealed in-memory file primitive."""


@contextlib.contextmanager
def verified_document_memfd(
    source_path: Path,
    *,
    document_id: uuid.UUID,
    artifact_role: str,
    keyring: DocumentKeyring,
    max_plaintext_bytes: int,
) -> Iterator[int]:
    """Decrypt and authenticate a source before exposing a sealed read-only fd.

    Plaintext is written only to an anonymous Linux memfd. The caller receives
    the descriptor after GCM finalization has succeeded and write/grow/shrink
    seals have been applied. Parser subprocesses may inherit the descriptor but
    cannot modify its contents.
    """

    if not hasattr(os, "memfd_create") or not hasattr(fcntl, "F_ADD_SEALS"):
        raise VerifiedMemoryUnavailableError(
            "Sealed memory files are required for document rendering"
        )

    flags = getattr(os, "MFD_CLOEXEC", 0) | getattr(os, "MFD_ALLOW_SEALING", 0)
    descriptor = os.memfd_create("hc-verified-document", flags)
    total = 0
    try:
        for chunk in iter_decrypted_for_untrusted_consumer(
            source_path,
            document_id=document_id,
            artifact_role=artifact_role,
            keyring=keyring,
        ):
            total += len(chunk)
            if total > max_plaintext_bytes:
                raise ValueError("Verified document exceeds configured plaintext limit")
            view = memoryview(chunk)
            while view:
                written = os.write(descriptor, view)
                if written < 1:
                    raise OSError("Unable to write verified memory file")
                view = view[written:]

        os.lseek(descriptor, 0, os.SEEK_SET)
        seals = (
            fcntl.F_SEAL_WRITE
            | fcntl.F_SEAL_GROW
            | fcntl.F_SEAL_SHRINK
            | fcntl.F_SEAL_SEAL
        )
        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seals)
        yield descriptor
    finally:
        os.close(descriptor)
