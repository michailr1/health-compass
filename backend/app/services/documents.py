"""Service layer for HC-017 secure document intake."""

from __future__ import annotations

import os
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import discard_rollback_cleanup, register_rollback_cleanup
from app.models.document import DocumentProcessingJob, ProfileDocument
from app.models.profile_audit_event import ProfileAuditEvent
from app.models.user import User
from app.schemas.document import DocumentIntakeCapabilities
from app.services.health_profile import (
    can_edit_profile,
    get_visible_profile,
    require_health_data_consent,
    require_profile_edit_access,
)
from app.storage.documents import (
    SUPPORTED_MEDIA_TYPES,
    DocumentValidationError,
    EncryptedLocalDocumentStorage,
)
from app.storage.encrypted_objects import DocumentKeyring

ENCRYPTED_OBJECT_QUOTA_OVERHEAD = 1024


async def document_capabilities(
    session: AsyncSession,
    profile_id: uuid.UUID,
) -> DocumentIntakeCapabilities:
    await get_visible_profile(session, profile_id)
    editable = await can_edit_profile(session, profile_id)
    return DocumentIntakeCapabilities(
        upload_enabled=(
            settings.document_upload_enabled
            and settings.is_development
            and editable
        ),
        accepted_media_types=sorted(SUPPORTED_MEDIA_TYPES),
        max_bytes=settings.document_max_bytes,
        max_image_pixels=settings.document_max_image_pixels,
    )


def _storage() -> EncryptedLocalDocumentStorage:
    if settings.document_storage_backend.strip().lower() != "local_encrypted":
        raise RuntimeError("Unsupported document storage backend")
    return EncryptedLocalDocumentStorage(
        settings.document_storage_root,
        keyring=DocumentKeyring(
            settings.document_credentials_directory,
            settings.document_encryption_active_key_id,
        ),
        min_free_bytes=settings.document_min_free_bytes,
    )


def _upload_size(upload: UploadFile) -> int:
    handle = upload.file
    handle.seek(0, os.SEEK_END)
    size = handle.tell()
    handle.seek(0)
    return size


async def _reserve_upload_quota(
    session: AsyncSession,
    profile_id: uuid.UUID,
    plaintext_size: int,
) -> None:
    result = await session.execute(
        text(
            """
            SELECT health_compass.app_reserve_document_upload(
              :profile_id, :additional_bytes, :profile_max_bytes,
              :global_max_bytes, :profile_max_documents,
              :profile_max_queued_jobs
            )
            """
        ),
        {
            "profile_id": profile_id,
            "additional_bytes": plaintext_size + ENCRYPTED_OBJECT_QUOTA_OVERHEAD,
            "profile_max_bytes": settings.document_profile_max_bytes,
            "global_max_bytes": settings.document_global_max_bytes,
            "profile_max_documents": settings.document_profile_max_documents,
            "profile_max_queued_jobs": settings.document_profile_max_queued_jobs,
        },
    )
    payload = result.scalar_one()
    if payload.get("allowed") is True:
        return

    code = str(payload.get("code") or "document_quota_exceeded")
    if code == "profile_document_queue_full":
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
        message = "Слишком много документов уже ожидают обработки."
    elif code == "global_document_quota_exceeded":
        status_code = status.HTTP_507_INSUFFICIENT_STORAGE
        message = "Хранилище документов временно достигло общего лимита."
    else:
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        message = "Для этого профиля достигнут лимит хранения документов."
    raise HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


async def list_documents(
    session: AsyncSession,
    profile_id: uuid.UUID,
    *,
    include_voided: bool = False,
) -> list[ProfileDocument]:
    await get_visible_profile(session, profile_id)
    query = select(ProfileDocument).where(
        ProfileDocument.profile_id == profile_id,
        ProfileDocument.erased_at.is_(None),
    )
    if not include_voided:
        query = query.where(ProfileDocument.voided_at.is_(None))
    result = await session.execute(query.order_by(desc(ProfileDocument.created_at)))
    return list(result.scalars().all())


async def get_document(
    session: AsyncSession,
    profile_id: uuid.UUID,
    document_id: uuid.UUID,
) -> ProfileDocument:
    await get_visible_profile(session, profile_id)
    result = await session.execute(
        select(ProfileDocument).where(
            ProfileDocument.id == document_id,
            ProfileDocument.profile_id == profile_id,
            ProfileDocument.erased_at.is_(None),
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document


async def create_document(
    session: AsyncSession,
    profile_id: uuid.UUID,
    upload: UploadFile,
    current_user: User,
    request_id: str | None,
) -> ProfileDocument:
    if not settings.document_upload_enabled or not settings.is_development:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document intake is not enabled",
        )

    await get_visible_profile(session, profile_id)
    await require_profile_edit_access(session, profile_id)
    await require_health_data_consent(session, current_user.id)

    source_size = _upload_size(upload)
    if source_size < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "empty_document",
                    "message": "Файл пуст.",
                }
            },
        )
    if source_size > settings.document_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": {
                    "code": "document_too_large",
                    "message": "Файл превышает допустимый размер.",
                }
            },
        )
    await _reserve_upload_quota(session, profile_id, source_size)

    document_id = uuid.uuid4()
    storage = _storage()
    stored = None
    cleanup_token: str | None = None
    try:
        stored = await storage.write_quarantine(
            document_id,
            upload,
            max_bytes=settings.document_max_bytes,
            max_image_pixels=settings.document_max_image_pixels,
        )
        cleanup_token = register_rollback_cleanup(
            session,
            lambda key=stored.storage_key: storage.delete(key),
        )

        document = ProfileDocument(
            id=document_id,
            profile_id=profile_id,
            uploaded_by_user_id=current_user.id,
            status="quarantined",
            original_filename=stored.original_filename,
            declared_media_type=stored.declared_media_type,
            detected_media_type=stored.detected_media_type,
            byte_size=stored.byte_size,
            encrypted_size=stored.encrypted_size,
            sha256=stored.sha256,
            storage_backend=storage.backend_name,
            quarantine_storage_key=stored.storage_key,
            current_storage_key=stored.storage_key,
            encryption_format=stored.encryption_format,
            encryption_key_id=stored.encryption_key_id,
            scanner_status="not_scanned",
            render_status="not_started",
            page_count=stored.page_count,
        )
        session.add(document)
        await session.flush([document])

        session.add(
            DocumentProcessingJob(
                id=uuid.uuid4(),
                document_id=document_id,
                profile_id=profile_id,
                job_type="scan",
                status="queued",
                attempt=0,
                idempotency_key=(
                    f"scan:{document_id}:{stored.sha256}:clamav-v1"
                ),
                input_sha256=stored.sha256,
            )
        )
        session.add(
            ProfileAuditEvent(
                id=uuid.uuid4(),
                profile_id=profile_id,
                actor_user_id=current_user.id,
                entity_type="document",
                entity_id=document_id,
                action="document.uploaded",
                changed_fields={},
                request_id=request_id,
            )
        )
        await session.flush()
        return document
    except DocumentValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        ) from exc
    except Exception:
        if cleanup_token is not None:
            discard_rollback_cleanup(session, cleanup_token)
        if stored is not None:
            await storage.delete(stored.storage_key)
        raise
