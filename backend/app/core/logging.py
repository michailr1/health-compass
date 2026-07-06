"""Structured logging configuration for Health Compass API."""

from __future__ import annotations

import logging
import sys

from app.core.config import settings


def configure_logging() -> None:
    """Configure structured JSON logging for the application."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt=(
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"service":"%(service)s","environment":"%(environment)s",'
            '"message":"%(message)s"}'
        ),
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Remove default handlers to avoid duplicate output
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)

    # Set service-wide extra fields
    logging.Logger.manager.loggerDict  # ensure loggers are loaded
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
