"""Unit tests for transaction-bound external artifact cleanup."""

from __future__ import annotations

import logging

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import (
    _run_rollback_cleanups,
    discard_rollback_cleanup,
    register_rollback_cleanup,
)


@pytest.mark.asyncio
async def test_rollback_cleanups_run_in_reverse_registration_order() -> None:
    session = AsyncSession()
    calls: list[str] = []

    async def first() -> None:
        calls.append("first")

    async def second() -> None:
        calls.append("second")

    register_rollback_cleanup(session, first)
    register_rollback_cleanup(session, second)

    await _run_rollback_cleanups(session)
    assert calls == ["second", "first"]


@pytest.mark.asyncio
async def test_discarded_cleanup_does_not_run() -> None:
    session = AsyncSession()
    calls: list[str] = []

    async def cleanup() -> None:
        calls.append("cleanup")

    token = register_rollback_cleanup(session, cleanup)
    discard_rollback_cleanup(session, token)

    await _run_rollback_cleanups(session)
    assert calls == []


@pytest.mark.asyncio
async def test_cleanup_failure_is_contained_without_sensitive_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = AsyncSession()

    async def failing_cleanup() -> None:
        raise RuntimeError("private/quarantine/path")

    register_rollback_cleanup(session, failing_cleanup)
    with caplog.at_level(logging.ERROR):
        await _run_rollback_cleanups(session)

    assert "request_rollback_cleanup_failed" in caplog.text
    assert "private/quarantine/path" not in caplog.text
