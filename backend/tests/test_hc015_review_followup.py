"""Regression coverage for the independent HC-015 PR review follow-up."""

from __future__ import annotations

import importlib.util
import inspect
import json
import logging
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi import HTTPException, Request

from app.core.logging import JsonFormatter, RedactAccessPathFilter
from app.db.session import engine
from app.main import global_exception_handler
from app.services.clinical_context import void_record


async def test_void_requires_an_explicit_version_precondition() -> None:
    parameter = inspect.signature(void_record).parameters["expected_updated_at"]
    assert parameter.default is inspect.Parameter.empty

    with pytest.raises(HTTPException) as exc_info:
        await void_record(  # type: ignore[arg-type]
            None,
            uuid.uuid4(),
            "conditions",
            uuid.uuid4(),
            "superseded",
            None,
            None,
            None,
        )
    assert exc_info.value.status_code == 428
    assert exc_info.value.detail == "expected_updated_at is required"


def test_sqlalchemy_engine_hides_bound_parameters() -> None:
    assert engine.sync_engine.hide_parameters is True


def test_uvicorn_access_filter_removes_auth_query_string() -> None:
    token = "secret-magic-link-token"
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=(
            "127.0.0.1:50000",
            "GET",
            f"/api/auth/email/consume?token={token}",
            "1.1",
            200,
        ),
        exc_info=None,
    )

    assert RedactAccessPathFilter().filter(record) is True
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"].endswith('GET /api/auth/email/consume HTTP/1.1" 200')
    assert token not in payload["message"]
    assert "?token=" not in payload["message"]


async def test_global_handler_omits_exception_values_and_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def capture(*args: object, **kwargs: object) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr("app.main.logger.error", capture)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/auth/email/consume",
            "raw_path": b"/api/auth/email/consume",
            "query_string": b"token=medical-secret-value",
            "headers": [],
            "scheme": "https",
            "server": ("health.funti.cc", 443),
            "client": ("127.0.0.1", 50000),
            "state": {"request_id": "request-123"},
        }
    )

    response = await global_exception_handler(
        request,
        ValueError("medical-secret-value"),
    )

    assert response.status_code == 500
    assert captured["args"] == ("Unhandled exception",)
    assert "exc_info" not in captured["kwargs"]
    extra = captured["kwargs"]["extra"]
    assert extra == {
        "request_id": "request-123",
        "path": "https://health.funti.cc/api/auth/email/consume",
        "exception_type": "ValueError",
    }
    assert "medical-secret-value" not in repr(captured)


def _load_migration_0047() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0047_enforce_canonical_concept_domain_integrity.py"
    )
    spec = importlib.util.spec_from_file_location("hc015_migration_0047", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dictionary_migration_locks_tables_before_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration_0047()
    statements: list[str] = []

    monkeypatch.setattr(migration.op, "execute", lambda sql: statements.append(str(sql)))
    monkeypatch.setattr(migration, "_repair_and_verify_existing_rows", lambda: None)
    monkeypatch.setattr(migration, "_create_validating_trigger_function", lambda: None)

    migration.upgrade()

    assert statements
    first = " ".join(statements[0].split())
    assert first.startswith("LOCK TABLE")
    assert "profile_conditions" in first
    assert "profile_allergies" in first
    assert "profile_medications" in first
    assert "profile_supplements" in first
    assert "IN ACCESS EXCLUSIVE MODE" in first
