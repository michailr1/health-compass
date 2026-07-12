"""Main API router — aggregates all route modules."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.account_link import router as account_link_router
from app.api.routes.auth import router as login_router
from app.api.routes.clinical_context import router as clinical_context_router
from app.api.routes.clinical_dictionary import router as clinical_dictionary_router
from app.api.routes.clinical_erasure import router as clinical_erasure_router
from app.api.routes.clinical_review import router as clinical_review_router
from app.api.routes.contextual_intake import router as contextual_intake_router
from app.api.routes.document_ocr import router as document_ocr_router
from app.api.routes.documents import router as documents_router
from app.api.routes.duplicate_resolution import router as duplicate_resolution_router
from app.api.routes.email_auth import router as email_auth_router
from app.api.routes.health import router as health_router
from app.api.routes.health_profile import router as health_profile_router
from app.api.routes.identity import router as user_router
from app.api.routes.identity_removal import router as identity_removal_router
from app.api.routes.private import router as private_router
from app.api.routes.profile_completion import router as profile_completion_router
from app.api.routes.sign_in_methods import router as sign_in_methods_router
from app.api.routes.version import router as version_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(version_router)
api_router.include_router(private_router)
api_router.include_router(user_router)
api_router.include_router(health_profile_router)
api_router.include_router(profile_completion_router)
api_router.include_router(clinical_dictionary_router)
api_router.include_router(contextual_intake_router)
api_router.include_router(documents_router)
api_router.include_router(document_ocr_router)
# Summary/review-state and section create routes are owned by
# clinical_review_router; clinical_context_router owns list/update/void and
# safety flags; clinical_erasure_router owns DELETE routes. The routers never
# register the same method/path pair, so registration order does not affect
# behavior (enforced by tests/test_route_table.py).
api_router.include_router(clinical_review_router)
api_router.include_router(clinical_context_router)
api_router.include_router(clinical_erasure_router)
api_router.include_router(login_router)
api_router.include_router(email_auth_router)
api_router.include_router(account_link_router)
api_router.include_router(sign_in_methods_router)
api_router.include_router(identity_removal_router)
api_router.include_router(duplicate_resolution_router)
