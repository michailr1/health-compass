"""Health Compass API — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger, redacted_url
from app.core.request_id import RequestIDMiddleware
from app.schemas.errors import ErrorDetail, ErrorResponse

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    configure_logging()
    settings.validate_production()
    logger.info(
        "Starting %s v%s (%s)",
        settings.service_name,
        settings.version,
        settings.environment,
    )
    yield
    logger.info("Shutting down %s", settings.service_name)


app = FastAPI(
    title="Health Compass API",
    version=settings.version,
    description="Backend API for the Health Compass personal health portal",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

# Middleware
app.add_middleware(RequestIDMiddleware)

# Routes
app.include_router(api_router)


# --- Exception handlers ---


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and return a safe error response."""
    request_id = getattr(request.state, "request_id", None)
    # Do not attach ``exc_info`` here. Exception text and tracebacks can contain
    # bound SQL parameters or user-entered clinical values. Operational
    # correlation is preserved with request_id, safe path and exception type.
    logger.error(
        "Unhandled exception",
        extra={
            "request_id": request_id,
            "path": redacted_url(request.url),
            "exception_type": type(exc).__name__,
        },
    )
    detail = ErrorDetail(
        code="internal_error",
        message="An internal error occurred",
        request_id=request_id,
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error=detail).model_dump(),
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a structured JSON response for unknown routes."""
    request_id = getattr(request.state, "request_id", None)
    detail = ErrorDetail(
        code="not_found",
        message="The requested resource was not found",
        request_id=request_id,
    )
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(error=detail).model_dump(),
    )
