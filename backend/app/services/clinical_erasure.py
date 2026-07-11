"""Owner-only permanent erasure for Clinical Context records."""

from __future__ import annotations

import datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.clinical_erasure import ClinicalEraseSection

_ERASURE_ERROR_BY_SQLSTATE: dict[str, tuple[int, str]] = {
    "HC404": (status.HTTP_404_NOT_FOUND, "Clinical record not found"),
    "HC409": (status.HTTP_409_CONFLICT, "Clinical record was updated elsewhere"),
    "HC428": (status.HTTP_428_PRECONDITION_REQUIRED, "expected_updated_at is required"),
    "HC422": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown clinical section"),
}


async def erase_clinical_record(
    session: AsyncSession,
    *,
    profile_id: uuid.UUID,
    section: ClinicalEraseSection,
    record_id: uuid.UUID,
    expected_updated_at: datetime.datetime,
    request_id: str | None,
) -> dict[str, object]:
    """Erase one record and its content-bearing audit history atomically.

    The PostgreSQL function is the security boundary: it requires the current
    session user to be the profile owner, checks the optimistic-concurrency
    timestamp, removes the clinical row and earlier value-bearing audit events,
    and writes only a generic content-free tombstone.

    Health-data consent is intentionally not required. A user must remain able
    to erase their data after withdrawing consent.
    """

    erasure_event_id = uuid.uuid4()
    try:
        result = await session.execute(
            text(
                "SELECT health_compass.app_erase_clinical_record("
                ":profile_id, :section, :record_id, :expected_updated_at, "
                ":erasure_event_id, :request_id)"
            ),
            {
                "profile_id": profile_id,
                "section": section,
                "record_id": record_id,
                "expected_updated_at": expected_updated_at,
                "erasure_event_id": erasure_event_id,
                "request_id": request_id,
            },
        )
        deleted = bool(result.scalar_one())
    except DBAPIError as exc:
        original = getattr(exc, "orig", None)
        sqlstate = str(
            getattr(original, "sqlstate", None)
            or getattr(original, "pgcode", None)
            or ""
        )
        mapped = _ERASURE_ERROR_BY_SQLSTATE.get(sqlstate)
        if mapped is None:
            raise
        http_status, detail = mapped
        raise HTTPException(status_code=http_status, detail=detail) from exc

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinical record not found",
        )

    return {
        "deleted": True,
        "record_id": record_id,
        "section": section,
    }
