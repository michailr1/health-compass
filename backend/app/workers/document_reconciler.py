"""Restricted reconciliation of encrypted document objects and DB references."""

from __future__ import annotations

import os
import socket
import stat
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings

_ACTIVE_NAMESPACES = ("quarantine", "accepted", "derived")


@dataclass(frozen=True)
class StorageReference:
    storage_key: str
    document_id: uuid.UUID
    profile_id: uuid.UUID
    artifact_role: str


@dataclass(frozen=True)
class ReconciliationResult:
    referenced: int
    missing: int
    isolated: int
    deleted_orphans: int
    unsafe_entries: int


def _database_dsn(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def default_reconciler_id() -> str:
    hostname = socket.gethostname().replace("_", "-")[:80]
    return f"{hostname}:{os.getpid()}"


class DocumentStorageReconciler:
    """Compare opaque filesystem objects with restricted database references."""

    def __init__(self) -> None:
        if not settings.document_reconciler_database_url:
            raise RuntimeError("DOCUMENT_RECONCILER_DATABASE_URL is required")
        self.database_dsn = _database_dsn(settings.document_reconciler_database_url)
        self.root = Path(settings.document_storage_root).expanduser().resolve()
        self.orphan_root = self.root / "orphan"
        self.orphan_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.orphan_root, 0o700)

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_dsn, row_factory=dict_row)

    def references(self) -> dict[str, StorageReference]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM health_compass.app_list_document_storage_references()"
            ).fetchall()
        return {
            row["storage_key"]: StorageReference(**row)
            for row in rows
        }

    def _safe_path(self, storage_key: str) -> Path:
        relative = Path(storage_key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid storage reference")
        path = self.root / relative
        parent = path.parent.resolve(strict=False)
        if parent != self.root and self.root not in parent.parents:
            raise ValueError("Invalid storage reference")
        return path

    @staticmethod
    def _is_safe_regular_file(path: Path) -> bool:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return False
        return stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1

    def _iter_active_objects(self):
        for namespace in _ACTIVE_NAMESPACES:
            base = self.root / namespace
            if not base.exists():
                continue
            for directory, names, files in os.walk(base, followlinks=False):
                directory_path = Path(directory)
                # Do not descend through symlink directories.
                names[:] = [
                    name
                    for name in names
                    if not (directory_path / name).is_symlink()
                ]
                for name in files:
                    path = directory_path / name
                    relative = path.relative_to(self.root).as_posix()
                    yield relative, path

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _isolate(self, path: Path) -> None:
        destination = self.orphan_root / f"{uuid.uuid4()}.hcenc"
        os.link(path, destination, follow_symlinks=False)
        path.unlink()
        self._fsync_directory(destination.parent)
        self._fsync_directory(path.parent)

    def _mark_missing(self, reference: StorageReference) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                SELECT health_compass.app_mark_document_object_missing(
                  %s, 'document_object_missing', %s
                )
                """,
                (reference.storage_key, uuid.uuid4()),
            ).fetchone()

    def run_once(self, *, now: float | None = None) -> ReconciliationResult:
        current_time = time.time() if now is None else now
        references = self.references()
        missing = 0
        isolated = 0
        deleted_orphans = 0
        unsafe_entries = 0

        for reference in references.values():
            try:
                path = self._safe_path(reference.storage_key)
            except ValueError:
                self._mark_missing(reference)
                missing += 1
                continue
            if not self._is_safe_regular_file(path):
                self._mark_missing(reference)
                missing += 1

        for storage_key, path in self._iter_active_objects():
            if storage_key in references:
                continue
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                unsafe_entries += 1
                continue
            if current_time - metadata.st_mtime < settings.document_orphan_grace_seconds:
                continue
            self._isolate(path)
            isolated += 1

        for path in self.orphan_root.iterdir():
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                unsafe_entries += 1
                continue
            if current_time - metadata.st_mtime < settings.document_orphan_delete_seconds:
                continue
            path.unlink()
            deleted_orphans += 1
        if deleted_orphans:
            self._fsync_directory(self.orphan_root)

        return ReconciliationResult(
            referenced=len(references),
            missing=missing,
            isolated=isolated,
            deleted_orphans=deleted_orphans,
            unsafe_entries=unsafe_entries,
        )
