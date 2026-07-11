"""HC-015 Slice C: structured JSON logging and secret redaction (CR-12)."""

from __future__ import annotations

import json
import logging

from app.core.logging import JsonFormatter, redacted_url


def _format(record_msg: str, **extra: object) -> dict:
    record = logging.LogRecord(
        name="app.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=record_msg,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return json.loads(JsonFormatter().format(record))


def test_log_lines_are_valid_json_with_hostile_message() -> None:
    hostile = 'quote " backslash \\ newline \n {"forged":"field"}'
    payload = _format(hostile)
    assert payload["message"] == hostile
    assert payload["level"] == "ERROR"
    assert payload["logger"] == "app.test"
    assert "forged" not in payload


def test_request_id_is_emitted_as_top_level_field() -> None:
    payload = _format("boom", request_id="550e8400-e29b-41d4-a716-446655440000")
    assert payload["request_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_path_extra_is_emitted() -> None:
    payload = _format("boom", path="/api/auth/email/consume")
    assert payload["path"] == "/api/auth/email/consume"


def test_redacted_url_drops_query_string_entirely() -> None:
    url = "https://health.funti.cc/api/auth/email/consume?token=super-secret-token"
    redacted = redacted_url(url)
    assert redacted == "https://health.funti.cc/api/auth/email/consume"
    assert "token" not in redacted
    assert "super-secret" not in redacted


def test_redacted_url_handles_relative_paths() -> None:
    assert redacted_url("/private/ping?session=abc") == "/private/ping"


def test_exception_info_is_serialized_inside_json() -> None:
    try:
        raise ValueError("inner 'detail'")
    except ValueError:
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=True,
        )
        import sys

        record.exc_info = sys.exc_info()
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError" in payload["exc_info"]
