"""Restricted HC-017 safe-renderer worker."""

from __future__ import annotations

import dataclasses
import datetime
import json
import os
import socket
import time
import uuid
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.rendering.safe_render import (
    InvalidRenderedImageError,
    RenderLimits,
    RenderProcessError,
    RenderTimeoutError,
    SafeDocumentRenderer,
    SafeRenderError,
    UnsupportedDocumentError,
)
from app.rendering.verified_memory import (
    VerifiedMemoryUnavailableError,
    verified_document_memfd,
)
from app.storage.encrypted_objects import (
    DocumentKeyring,
    EncryptedObjectAlreadyExistsError,
    EncryptedObjectError,
    EncryptedObjectMetadata,
)
from app.storage.rendered_documents import (
    RenderedDocumentStorage,
    StoredPageArtifact,
)


@dataclass(frozen=True)
class ClaimedRenderJob:
    job_id: uuid.UUID
    document_id: uuid.UUID
    profile_id: uuid.UUID
    attempt: int
    lease_expires_at: datetime.datetime
    source_storage_key: str
    detected_media_type: str
    encryption_format: str
    encryption_key_id: str
    input_sha256: str


def _database_dsn(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def default_renderer_id() -> str:
    hostname = socket.gethostname().replace("_", "-")[:80]
    return f"{hostname}:{os.getpid()}"


class DocumentRendererWorker:
    """Claim render jobs through restricted functions and persist encrypted pages."""

    def __init__(self, *, worker_id: str | None = None) -> None:
        if not settings.document_renderer_database_url:
            raise RuntimeError("DOCUMENT_RENDERER_DATABASE_URL is required")
        self.worker_id = worker_id or default_renderer_id()
        self.database_dsn = _database_dsn(settings.document_renderer_database_url)
        self.keyring = DocumentKeyring(
            settings.document_credentials_directory,
            settings.document_encryption_active_key_id,
        )
        self.storage = RenderedDocumentStorage(
            settings.document_storage_root,
            keyring=self.keyring,
            min_free_bytes=settings.document_min_free_bytes,
        )
        self.renderer = SafeDocumentRenderer(
            pdfinfo_path=settings.document_pdfinfo_path,
            pdftocairo_path=settings.document_pdftocairo_path,
            magick_path=settings.document_magick_path,
            limits=RenderLimits(
                timeout_seconds=settings.document_render_timeout_seconds,
                cpu_seconds=settings.document_render_cpu_seconds,
                memory_bytes=settings.document_render_memory_bytes,
                max_output_bytes=settings.document_render_max_output_bytes,
                max_pixels=settings.document_max_image_pixels,
                max_pages=settings.document_render_max_pages,
                dpi=settings.document_render_dpi,
            ),
        )

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_dsn, row_factory=dict_row)

    def claim(self) -> ClaimedRenderJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM health_compass.app_claim_render_job(%s, %s, %s)",
                (
                    self.worker_id,
                    settings.document_render_lease_seconds,
                    settings.document_render_max_attempts,
                ),
            ).fetchone()
            return None if row is None else ClaimedRenderJob(**row)

    def heartbeat(self, job: ClaimedRenderJob) -> ClaimedRenderJob:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT health_compass.app_heartbeat_render_job(
                  %s, %s, %s, %s
                ) AS lease_expires_at
                """,
                (
                    job.job_id,
                    self.worker_id,
                    job.lease_expires_at,
                    settings.document_render_lease_seconds,
                ),
            ).fetchone()
            if row is None:
                raise RuntimeError("Renderer heartbeat returned no value")
            return dataclasses.replace(job, lease_expires_at=row["lease_expires_at"])

    @staticmethod
    def _artifact_payload(artifacts: list[StoredPageArtifact]) -> list[dict[str, object]]:
        return [
            {
                "id": str(item.id),
                "page_number": item.page_number,
                "storage_key": item.storage_key,
                "media_type": "image/png",
                "byte_size": item.metadata.plaintext_size,
                "encrypted_size": item.metadata.encrypted_size,
                "sha256": item.metadata.plaintext_sha256,
                "encryption_format": item.metadata.format,
                "encryption_key_id": item.metadata.key_id,
                "width": item.width,
                "height": item.height,
            }
            for item in artifacts
        ]

    def _complete(
        self,
        job: ClaimedRenderJob,
        *,
        run_id: uuid.UUID,
        accepted_key: str,
        accepted_metadata: EncryptedObjectMetadata,
        artifacts: list[StoredPageArtifact],
    ) -> None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT health_compass.app_complete_document_render(
                  %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s::jsonb, %s
                ) AS completed
                """,
                (
                    job.job_id,
                    self.worker_id,
                    job.lease_expires_at,
                    run_id,
                    accepted_key,
                    accepted_metadata.encrypted_size,
                    accepted_metadata.format,
                    accepted_metadata.key_id,
                    len(artifacts),
                    "hc-safe-renderer",
                    "1",
                    json.dumps(self._artifact_payload(artifacts)),
                    uuid.uuid4(),
                ),
            ).fetchone()
            if row is None or row["completed"] is not True:
                raise RuntimeError("Document render completion was not confirmed")

    def _fail(
        self,
        job: ClaimedRenderJob,
        *,
        error_code: str,
        retryable: bool,
        retry_after_seconds: int,
    ) -> None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT health_compass.app_fail_render_job(
                  %s, %s, %s, %s, %s, %s, %s
                ) AS failed
                """,
                (
                    job.job_id,
                    self.worker_id,
                    job.lease_expires_at,
                    error_code,
                    retryable,
                    settings.document_render_max_attempts,
                    retry_after_seconds,
                ),
            ).fetchone()
            if row is None or row["failed"] is not True:
                raise RuntimeError("Document render failure was not confirmed")

    @staticmethod
    def _failure_policy(error: Exception) -> tuple[str, bool, int]:
        if isinstance(error, RenderTimeoutError):
            return "render_timeout", True, 300
        if isinstance(error, UnsupportedDocumentError):
            return "unsupported_document", False, 0
        if isinstance(error, InvalidRenderedImageError):
            return "invalid_rendered_image", False, 0
        if isinstance(error, VerifiedMemoryUnavailableError):
            return "verified_memory_unavailable", True, 600
        if isinstance(error, EncryptedObjectAlreadyExistsError):
            return "render_object_collision", True, 3600
        if isinstance(error, EncryptedObjectError):
            return "render_storage_error", True, 300
        if isinstance(error, RenderProcessError):
            return "render_process_error", True, 300
        if isinstance(error, SafeRenderError):
            return "render_error", True, 300
        return "render_internal_error", True, 300

    def _page_numbers(self, job: ClaimedRenderJob, verified_descriptor: int) -> range:
        if job.detected_media_type == "application/pdf":
            inspection = self.renderer.inspect_pdf(verified_descriptor)
            return range(1, inspection.page_count + 1)
        if job.detected_media_type in {"image/jpeg", "image/png"}:
            return range(1, 2)
        raise UnsupportedDocumentError("Unsupported source media type")

    def _render_page(
        self,
        job: ClaimedRenderJob,
        verified_descriptor: int,
        page_number: int,
    ):
        if job.detected_media_type == "application/pdf":
            return self.renderer.render_pdf_page(verified_descriptor, page_number)
        return self.renderer.render_image(verified_descriptor)

    def _delete_created_keys(self, keys: list[str]) -> None:
        for key in reversed(keys):
            self.storage.delete_key(key)

    def run_once(self) -> bool:
        job = self.claim()
        if job is None:
            return False
        if job.encryption_format != "hcenc1":
            self._fail(
                job,
                error_code="unsupported_storage_format",
                retryable=False,
                retry_after_seconds=0,
            )
            return True

        run_id = uuid.uuid4()
        created_keys: list[str] = []
        completed = False
        try:
            source_path = self.storage.path_for_key(job.source_storage_key)
            with verified_document_memfd(
                source_path,
                document_id=job.document_id,
                artifact_role="source_quarantine",
                keyring=self.keyring,
                max_plaintext_bytes=settings.document_max_bytes,
            ) as verified_descriptor:
                artifacts: list[StoredPageArtifact] = []
                for page_number in self._page_numbers(job, verified_descriptor):
                    # Renew before each parser invocation so any later failure is
                    # reported with the current lease value.
                    job = self.heartbeat(job)
                    rendered = self._render_page(job, verified_descriptor, page_number)
                    try:
                        artifact = self.storage.store_page(
                            rendered.descriptor,
                            document_id=job.document_id,
                            run_id=run_id,
                            artifact_id=uuid.uuid4(),
                            page_number=page_number,
                            width=rendered.width,
                            height=rendered.height,
                            max_plaintext_bytes=settings.document_render_max_output_bytes,
                        )
                        artifacts.append(artifact)
                        created_keys.append(artifact.storage_key)
                    finally:
                        os.close(rendered.descriptor)

                accepted_key, accepted_metadata = self.storage.store_accepted_source(
                    verified_descriptor,
                    document_id=job.document_id,
                    max_plaintext_bytes=settings.document_max_bytes,
                )
                created_keys.append(accepted_key)
                self._complete(
                    job,
                    run_id=run_id,
                    accepted_key=accepted_key,
                    accepted_metadata=accepted_metadata,
                    artifacts=artifacts,
                )
                completed = True
        except psycopg.DatabaseError as exc:
            # HC409/HC422 prove that completion was rejected. Connection errors
            # are ambiguous: leave staged objects for reconciliation rather than
            # deleting data that may already be committed.
            if exc.sqlstate in {"HC409", "HC422"}:
                self._delete_created_keys(created_keys)
            raise
        except Exception as exc:
            self._delete_created_keys(created_keys)
            code, retryable, delay = self._failure_policy(exc)
            self._fail(
                job,
                error_code=code,
                retryable=retryable,
                retry_after_seconds=delay,
            )
            return True

        if completed:
            # The database already points at accepted/artifact objects. Failure
            # to remove the old quarantine copy must never roll back committed
            # data; reconciliation will isolate it after the grace period.
            try:
                self.storage.delete_key(job.source_storage_key)
            except OSError:
                pass
            return True
        return False

    def run_forever(self, *, idle_sleep_seconds: float = 2.0) -> None:
        while True:
            worked = self.run_once()
            if not worked:
                time.sleep(idle_sleep_seconds)
