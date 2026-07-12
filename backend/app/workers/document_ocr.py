"""Restricted HC-017 D1 local OCR worker."""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import os
import socket
import time
import uuid
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.ocr.tesseract import (
    OCRLanguageDataError,
    OCRLimits,
    OCROutputError,
    OCRProcessError,
    OCRTimeoutError,
    TesseractOCR,
)
from app.rendering.safe_render import InvalidRenderedImageError, validate_png_descriptor
from app.rendering.verified_memory import (
    VerifiedMemoryUnavailableError,
    verified_document_memfd,
)
from app.storage.encrypted_objects import (
    DocumentKeyring,
    EncryptedObjectAlreadyExistsError,
    EncryptedObjectError,
)
from app.storage.ocr_documents import OCRDocumentStorage, StoredOCRArtifact
from app.storage.rendered_documents import page_artifact_role


@dataclass(frozen=True)
class ClaimedOCRPage:
    artifact_id: uuid.UUID
    page_number: int
    storage_key: str
    encryption_format: str
    encryption_key_id: str
    sha256: str
    width: int
    height: int


@dataclass(frozen=True)
class ClaimedOCRRun:
    run_id: uuid.UUID
    document_id: uuid.UUID
    profile_id: uuid.UUID
    render_run_id: uuid.UUID
    attempt: int
    lease_expires_at: datetime.datetime
    input_manifest_sha256: str
    language_spec: str
    psm: int
    pages: tuple[ClaimedOCRPage, ...]


def _database_dsn(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def default_ocr_worker_id() -> str:
    hostname = socket.gethostname().replace("_", "-")[:80]
    return f"{hostname}:{os.getpid()}"


class DocumentOCRWorker:
    """Claim OCR runs through restricted functions and persist encrypted TSV."""

    def __init__(self, *, worker_id: str | None = None) -> None:
        if not settings.document_ocr_database_url:
            raise RuntimeError("DOCUMENT_OCR_DATABASE_URL is required")
        self.worker_id = worker_id or default_ocr_worker_id()
        self.database_dsn = _database_dsn(settings.document_ocr_database_url)
        self.keyring = DocumentKeyring(
            settings.document_credentials_directory,
            settings.document_encryption_active_key_id,
        )
        self.storage = OCRDocumentStorage(
            settings.document_storage_root,
            keyring=self.keyring,
            min_free_bytes=settings.document_min_free_bytes,
        )
        self.ocr = TesseractOCR(
            executable_path=settings.document_tesseract_path,
            tessdata_directory=settings.document_tessdata_directory,
            language_spec=settings.document_ocr_language_spec,
            psm=settings.document_ocr_psm,
            limits=OCRLimits(
                timeout_seconds=settings.document_ocr_timeout_seconds,
                cpu_seconds=settings.document_ocr_cpu_seconds,
                memory_bytes=settings.document_ocr_memory_bytes,
                max_output_bytes=settings.document_ocr_max_output_bytes,
                max_rows=settings.document_ocr_max_rows,
                max_candidates=settings.document_ocr_max_candidates,
                max_candidate_chars=settings.document_ocr_max_candidate_chars,
                max_candidate_words=settings.document_ocr_max_candidate_words,
            ),
        )

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_dsn, row_factory=dict_row)

    @staticmethod
    def _parse_claim(row: dict[str, object]) -> ClaimedOCRRun:
        pages_value = row.pop("pages")
        if not isinstance(pages_value, list):
            raise RuntimeError("OCR claim returned an invalid page manifest")
        pages = tuple(
            ClaimedOCRPage(
                artifact_id=uuid.UUID(str(item["artifact_id"])),
                page_number=int(item["page_number"]),
                storage_key=str(item["storage_key"]),
                encryption_format=str(item["encryption_format"]),
                encryption_key_id=str(item["encryption_key_id"]),
                sha256=str(item["sha256"]),
                width=int(item["width"]),
                height=int(item["height"]),
            )
            for item in pages_value
        )
        return ClaimedOCRRun(pages=pages, **row)

    def claim(self) -> ClaimedOCRRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM health_compass.app_claim_document_ocr_run(%s, %s, %s)",
                (
                    self.worker_id,
                    settings.document_ocr_lease_seconds,
                    settings.document_ocr_max_attempts,
                ),
            ).fetchone()
        return None if row is None else self._parse_claim(dict(row))

    def heartbeat(self, run: ClaimedOCRRun) -> ClaimedOCRRun:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT health_compass.app_heartbeat_document_ocr_run(
                  %s, %s, %s, %s
                ) AS lease_expires_at
                """,
                (
                    run.run_id,
                    self.worker_id,
                    run.lease_expires_at,
                    settings.document_ocr_lease_seconds,
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("OCR heartbeat returned no value")
        return dataclasses.replace(run, lease_expires_at=row["lease_expires_at"])

    @staticmethod
    def _input_manifest(pages: tuple[ClaimedOCRPage, ...]) -> str:
        payload = [
            {
                "id": str(page.artifact_id),
                "page_number": page.page_number,
                "sha256": page.sha256,
                "width": page.width,
                "height": page.height,
            }
            for page in sorted(pages, key=lambda item: item.page_number)
        ]
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _artifact_payload(
        artifact: StoredOCRArtifact,
    ) -> dict[str, object]:
        return {
            "id": str(artifact.id),
            "page_artifact_id": str(artifact.page_artifact_id),
            "page_number": artifact.page_number,
            "storage_key": artifact.storage_key,
            "byte_size": artifact.metadata.plaintext_size,
            "encrypted_size": artifact.metadata.encrypted_size,
            "sha256": artifact.metadata.plaintext_sha256,
            "encryption_format": artifact.metadata.format,
            "encryption_key_id": artifact.metadata.key_id,
        }

    @staticmethod
    def _output_manifest(
        artifacts: list[dict[str, object]],
        candidates: list[dict[str, object]],
    ) -> str:
        safe_candidates = [
            {
                key: value
                for key, value in candidate.items()
                if key != "id"
            }
            for candidate in candidates
        ]
        encoded = json.dumps(
            {"artifacts": artifacts, "candidates": safe_candidates},
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return hashlib.sha256(encoded).hexdigest()

    def _complete(
        self,
        run: ClaimedOCRRun,
        *,
        engine_version: str,
        traineddata_manifest: str,
        artifacts: list[dict[str, object]],
        candidates: list[dict[str, object]],
    ) -> None:
        output_manifest = self._output_manifest(artifacts, candidates)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT health_compass.app_complete_document_ocr_run(
                  %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s
                ) AS completed
                """,
                (
                    run.run_id,
                    self.worker_id,
                    run.lease_expires_at,
                    "tesseract",
                    engine_version,
                    traineddata_manifest,
                    output_manifest,
                    json.dumps(artifacts, ensure_ascii=True),
                    json.dumps(candidates, ensure_ascii=False),
                    uuid.uuid4(),
                ),
            ).fetchone()
        if row is None or row["completed"] is not True:
            raise RuntimeError("OCR completion was not confirmed")

    def _fail(
        self,
        run: ClaimedOCRRun,
        *,
        error_code: str,
        retryable: bool,
        retry_after_seconds: int,
    ) -> None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT health_compass.app_fail_document_ocr_run(
                  %s, %s, %s, %s, %s, %s, %s, %s
                ) AS failed
                """,
                (
                    run.run_id,
                    self.worker_id,
                    run.lease_expires_at,
                    error_code,
                    retryable,
                    settings.document_ocr_max_attempts,
                    retry_after_seconds,
                    uuid.uuid4(),
                ),
            ).fetchone()
        if row is None or row["failed"] is not True:
            raise RuntimeError("OCR failure was not confirmed")

    @staticmethod
    def _failure_policy(error: Exception) -> tuple[str, bool, int]:
        if isinstance(error, OCRTimeoutError):
            return "ocr_timeout", True, 300
        if isinstance(error, OCRLanguageDataError):
            return "ocr_language_data_unavailable", True, 3600
        if isinstance(error, OCROutputError):
            return "ocr_output_invalid", False, 0
        if isinstance(error, OCRProcessError):
            return "ocr_process_error", True, 300
        if isinstance(error, InvalidRenderedImageError):
            return "ocr_safe_page_invalid", False, 0
        if isinstance(error, VerifiedMemoryUnavailableError):
            return "ocr_verified_memory_unavailable", True, 600
        if isinstance(error, EncryptedObjectAlreadyExistsError):
            return "ocr_object_collision", True, 3600
        if isinstance(error, EncryptedObjectError):
            return "ocr_storage_error", True, 300
        return "ocr_internal_error", True, 300

    def _delete_created_keys(self, keys: list[str]) -> None:
        for key in reversed(keys):
            self.storage.delete_key(key)

    def run_once(self) -> bool:
        run = self.claim()
        if run is None:
            return False
        if run.language_spec != settings.document_ocr_language_spec:
            self._fail(
                run,
                error_code="ocr_language_config_mismatch",
                retryable=False,
                retry_after_seconds=0,
            )
            return True
        if run.psm != settings.document_ocr_psm:
            self._fail(
                run,
                error_code="ocr_psm_config_mismatch",
                retryable=False,
                retry_after_seconds=0,
            )
            return True
        if self._input_manifest(run.pages) != run.input_manifest_sha256:
            self._fail(
                run,
                error_code="ocr_input_manifest_mismatch",
                retryable=False,
                retry_after_seconds=0,
            )
            return True

        created_keys: list[str] = []
        artifact_payloads: list[dict[str, object]] = []
        candidate_payloads: list[dict[str, object]] = []
        engine_version: str | None = None
        traineddata_manifest: str | None = None
        try:
            for page in run.pages:
                run = self.heartbeat(run)
                if page.encryption_format != "hcenc1":
                    raise EncryptedObjectError("Unsupported safe-page encryption format")
                source_path = self.storage.path_for_key(page.storage_key)
                with verified_document_memfd(
                    source_path,
                    document_id=run.document_id,
                    artifact_role=page_artifact_role(page.artifact_id),
                    keyring=self.keyring,
                    max_plaintext_bytes=settings.document_render_max_output_bytes,
                ) as page_descriptor:
                    validate_png_descriptor(
                        page_descriptor,
                        max_bytes=settings.document_render_max_output_bytes,
                        max_pixels=settings.document_max_image_pixels,
                    )
                    result = self.ocr.run_tsv(page_descriptor)
                    try:
                        parsed = self.ocr.parse_tsv(
                            result.descriptor,
                            page_width=page.width,
                            page_height=page.height,
                        )
                        if engine_version is None:
                            engine_version = result.engine_version
                            traineddata_manifest = result.traineddata_manifest_sha256
                        elif (
                            engine_version != result.engine_version
                            or traineddata_manifest != result.traineddata_manifest_sha256
                        ):
                            raise OCRProcessError("OCR engine provenance changed during run")

                        artifact_id = uuid.uuid5(run.run_id, f"tsv:{page.page_number}")
                        stored = self.storage.store_tsv(
                            result.descriptor,
                            document_id=run.document_id,
                            run_id=run.run_id,
                            artifact_id=artifact_id,
                            page_artifact_id=page.artifact_id,
                            page_number=page.page_number,
                            max_plaintext_bytes=settings.document_ocr_max_output_bytes,
                        )
                        created_keys.append(stored.storage_key)
                        artifact_payloads.append(self._artifact_payload(stored))
                        for item in parsed:
                            candidate_payloads.append(
                                {
                                    "id": str(
                                        uuid.uuid5(
                                            run.run_id,
                                            f"candidate:{page.page_number}:{item.candidate_index}",
                                        )
                                    ),
                                    "page_artifact_id": str(page.artifact_id),
                                    "page_number": page.page_number,
                                    "candidate_index": item.candidate_index,
                                    "original_text": item.original_text,
                                    "confidence_min": item.confidence_min,
                                    "confidence_mean": item.confidence_mean,
                                    "left_px": item.left_px,
                                    "top_px": item.top_px,
                                    "width_px": item.width_px,
                                    "height_px": item.height_px,
                                    "word_count": item.word_count,
                                }
                            )
                    finally:
                        os.close(result.descriptor)

            if engine_version is None or traineddata_manifest is None:
                raise OCROutputError("OCR run produced no page provenance")
            self._complete(
                run,
                engine_version=engine_version,
                traineddata_manifest=traineddata_manifest,
                artifacts=artifact_payloads,
                candidates=candidate_payloads,
            )
            return True
        except psycopg.DatabaseError as exc:
            if exc.sqlstate in {"HC409", "HC422"}:
                self._delete_created_keys(created_keys)
            raise
        except Exception as exc:
            self._delete_created_keys(created_keys)
            code, retryable, delay = self._failure_policy(exc)
            self._fail(
                run,
                error_code=code,
                retryable=retryable,
                retry_after_seconds=delay,
            )
            return True

    def run_forever(self, *, idle_sleep_seconds: float = 2.0) -> None:
        while True:
            worked = self.run_once()
            if not worked:
                time.sleep(idle_sleep_seconds)
