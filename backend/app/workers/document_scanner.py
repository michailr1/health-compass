"""Restricted HC-017 scanner worker using only definer-function database APIs."""

from __future__ import annotations

import datetime
import os
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.scanning.clamav import (
    ClamAVClient,
    ScannerEncryptedObjectError,
    ScannerError,
    ScannerProtocolError,
    ScannerSignatureStaleError,
    ScannerStreamTooLargeError,
    ScannerUnavailableError,
    ScanResult,
)
from app.storage.documents import EncryptedLocalDocumentStorage
from app.storage.encrypted_objects import DocumentKeyring


@dataclass(frozen=True)
class ClaimedDocumentJob:
    job_id: uuid.UUID
    document_id: uuid.UUID
    profile_id: uuid.UUID
    job_type: str
    attempt: int
    lease_expires_at: datetime.datetime
    storage_backend: str
    storage_key: str
    encryption_format: str
    encryption_key_id: str
    input_sha256: str


def _database_dsn(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def default_worker_id() -> str:
    hostname = socket.gethostname().replace("_", "-")[:80]
    return f"{hostname}:{os.getpid()}"


class DocumentScannerWorker:
    """Claim and scan one document at a time without direct table privileges."""

    def __init__(self, *, worker_id: str | None = None) -> None:
        if not settings.document_worker_database_url:
            raise RuntimeError("DOCUMENT_WORKER_DATABASE_URL is required")
        self.worker_id = worker_id or default_worker_id()
        self.database_dsn = _database_dsn(settings.document_worker_database_url)
        self.keyring = DocumentKeyring(
            settings.document_credentials_directory,
            settings.document_encryption_active_key_id,
        )
        self.storage = EncryptedLocalDocumentStorage(
            settings.document_storage_root,
            keyring=self.keyring,
            min_free_bytes=settings.document_min_free_bytes,
        )
        self.scanner = ClamAVClient(
            settings.document_scanner_socket,
            timeout_seconds=settings.document_scanner_timeout_seconds,
            max_stream_bytes=settings.document_max_bytes,
            max_signature_age_hours=settings.document_scanner_max_signature_age_hours,
        )

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_dsn, row_factory=dict_row)

    def claim(self) -> ClaimedDocumentJob | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM health_compass.app_claim_document_job(%s, %s, %s)
                """,
                (
                    self.worker_id,
                    settings.document_worker_lease_seconds,
                    settings.document_worker_max_attempts,
                ),
            ).fetchone()
            if row is None:
                return None
            return ClaimedDocumentJob(**row)

    def heartbeat(
        self,
        job: ClaimedDocumentJob,
    ) -> datetime.datetime:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT health_compass.app_heartbeat_document_job(
                  %s, %s, %s, %s
                ) AS lease_expires_at
                """,
                (
                    job.job_id,
                    self.worker_id,
                    job.lease_expires_at,
                    settings.document_worker_lease_seconds,
                ),
            ).fetchone()
            if row is None:
                raise RuntimeError("Worker heartbeat returned no value")
            return row["lease_expires_at"]

    def _complete(self, job: ClaimedDocumentJob, result: ScanResult) -> None:
        render_job_id = uuid.uuid4() if result.clean else None
        render_key = (
            f"render:{job.document_id}:{job.input_sha256}:safe-render-v1"
            if result.clean
            else None
        )
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT health_compass.app_complete_document_scan(
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) AS completed
                """,
                (
                    job.job_id,
                    self.worker_id,
                    job.lease_expires_at,
                    result.version.engine,
                    result.version.engine_version,
                    result.version.signature_version,
                    result.version.signature_timestamp,
                    "infected" if result.infected else "clean",
                    render_job_id,
                    render_key,
                    uuid.uuid4(),
                ),
            ).fetchone()
            if row is None or row["completed"] is not True:
                raise RuntimeError("Document scan completion was not confirmed")

    def _fail(
        self,
        job: ClaimedDocumentJob,
        *,
        error_code: str,
        retryable: bool,
        retry_after_seconds: int,
    ) -> None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT health_compass.app_fail_document_job(
                  %s, %s, %s, %s, %s, %s, %s
                ) AS failed
                """,
                (
                    job.job_id,
                    self.worker_id,
                    job.lease_expires_at,
                    error_code,
                    retryable,
                    settings.document_worker_max_attempts,
                    retry_after_seconds,
                ),
            ).fetchone()
            if row is None or row["failed"] is not True:
                raise RuntimeError("Document job failure was not confirmed")

    @staticmethod
    def _failure_policy(error: ScannerError) -> tuple[str, bool, int]:
        if isinstance(error, ScannerSignatureStaleError):
            return "scanner_signatures_stale", True, 3600
        if isinstance(error, ScannerUnavailableError):
            return "scanner_unavailable", True, 60
        if isinstance(error, ScannerStreamTooLargeError):
            return "scanner_stream_too_large", False, 0
        if isinstance(error, ScannerEncryptedObjectError):
            return "encrypted_object_invalid", False, 0
        if isinstance(error, ScannerProtocolError):
            return "scanner_protocol_error", True, 300
        return "scanner_error", True, 300

    def run_once(self) -> bool:
        job = self.claim()
        if job is None:
            return False
        if job.storage_backend != "local_encrypted" or job.encryption_format != "hcenc1":
            self._fail(
                job,
                error_code="unsupported_storage_format",
                retryable=False,
                retry_after_seconds=0,
            )
            return True

        path: Path = self.storage.object_path(job.storage_key)
        try:
            result = self.scanner.scan_encrypted_object(
                path,
                document_id=job.document_id,
                artifact_role="source_quarantine",
                keyring=self.keyring,
            )
        except ScannerError as exc:
            code, retryable, delay = self._failure_policy(exc)
            self._fail(
                job,
                error_code=code,
                retryable=retryable,
                retry_after_seconds=delay,
            )
            return True

        self._complete(job, result)
        return True

    def run_forever(self, *, idle_sleep_seconds: float = 2.0) -> None:
        while True:
            worked = self.run_once()
            if not worked:
                time.sleep(idle_sleep_seconds)
