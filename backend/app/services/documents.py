"""Service layer for HC-017 secure document intake."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import desc, select
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
            encryption_format=stored.encryption_format,
            encryption_key_id=stored.encryption_key_id,
            scanner_status="not_scanned",
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
