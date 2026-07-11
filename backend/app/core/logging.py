"""Structured logging configuration for Health Compass API.

Log lines are real JSON (``json.dumps``), so messages containing quotes,
newlines or user input can never corrupt the log format or forge fields.
Auth tokens, cookies and raw query strings must never reach a log record:
use :func:`redacted_url` whenever a request URL is logged (HC-015 Slice C /
CR-12).
"""

from __future__ import annotations

import json
import logging
import sys
from urllib.parse import urlsplit

from app.core.config import settings

# Extra attributes that, when present on a record, are emitted as top-level
# JSON fields. ``request_id`` keeps operational errors support-friendly.
_EXTRA_FIELDS = ("request_id", "path", "exception_type")


def redacted_url(url: object) -> str:
    """Return only scheme/host/path of a URL — never the query string.

    Magic-link tokens and OIDC parameters travel in query strings, so query
    strings are dropped entirely before logging.
    """
    parts = urlsplit(str(url))
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}{parts.path}"
    return parts.path


class RedactAccessPathFilter(logging.Filter):
    """Remove query strings from Uvicorn access-log request targets.

    Uvicorn stores the request target as the third positional formatting
    argument. Rewriting that argument preserves useful access logging while
    ensuring Magic Link and OIDC query parameters never reach the formatter.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access" and isinstance(record.args, tuple):
            if len(record.args) >= 3:
                args = list(record.args)
                args[2] = redacted_url(args[2])
                record.args = tuple(args)
        return True


class JsonFormatter(logging.Formatter):
    """Serialize log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": getattr(record, "service", settings.service_name),
            "environment": getattr(record, "environment", settings.environment),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None and field not in payload:
                payload[field] = str(value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Configure structured JSON logging for the application and access log."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactAccessPathFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Remove default handlers to avoid duplicate output.
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)
    root_logger.addHandler(handler)

    # Uvicorn configures ``uvicorn.access`` with its own handler and
    # ``propagate=False``. Replace that handler explicitly so request targets
    # receive the same query-string redaction as application logs.
    access_logger = logging.getLogger("uvicorn.access")
    for existing_handler in access_logger.handlers[:]:
        access_logger.removeHandler(existing_handler)
    access_logger.addHandler(handler)
    access_logger.propagate = False
    access_logger.disabled = False

    for name in logging.root.manager.loggerDict:
        logger = logging.getLogger(name)
        logger.setLevel(log_level)


class ServiceAdapter(logging.LoggerAdapter):
    """Logger adapter that injects service and environment fields."""

    def process(
        self, msg: str, kwargs: dict
    ) -> tuple[str, dict]:
        extra = kwargs.get("extra", {})
        extra.setdefault("service", settings.service_name)
        extra.setdefault("environment", settings.environment)
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> ServiceAdapter:
    """Get a logger with service context."""
    return ServiceAdapter(logging.getLogger(name), {})
