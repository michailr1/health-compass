"""Main API router — aggregates all route modules."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.account_link import router as account_link_router
from app.api.routes.auth import router as login_router
from app.api.routes.clinical_context import router as clinical_context_router
from app.api.routes.clinical_dictionary import router as clinical_dictionary_router
from app.api.routes.clinical_review import router as clinical_review_router
from app.api.routes.duplicate_resolution import router as duplicate_resolution_router
from app.api.routes.email_auth import router as email_auth_router
from app.api.routes.health import router as health_router
from app.api.routes.health_profile import router as health_profile_router
from app.api.routes.identity import router as user_router
from app.api.routes.identity_removal import router as identity_removal_router
from app.api.routes.private import router as private_router
from app.api.routes.sign_in_methods import router as sign_in_methods_router
from app.api.routes.version import router as version_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(version_router)
api_router.include_router(private_router)
api_router.include_router(user_router)
api_router.include_router(health_profile_router)
api_router.include_router(clinical_dictionary_router)
# Transition-safe review-state routes must be registered before the legacy
# Clinical Context routes because several paths intentionally overlap.
api_router.include_router(clinical_review_router)
api_router.include_router(clinical_context_router)
api_router.include_router(login_router)
api_router.include_router(email_auth_router)
api_router.include_router(account_link_router)
api_router.include_router(sign_in_methods_router)
api_router.include_router(identity_removal_router)
api_router.include_router(duplicate_resolution_router)
