"""Main API router — aggregates all route modules."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.private import router as private_router
from app.api.routes.version import router as version_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(version_router)
api_router.include_router(private_router)
