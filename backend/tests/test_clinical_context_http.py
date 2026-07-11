"""HTTP-level Clinical Context tests through the real FastAPI application.

Covers HC-015 Slice A acceptance: the summary endpoint always returns a valid
``ClinicalContextSummary`` regardless of router registration order, and the
owner/edit/view/analyze/outsider access matrix holds at the HTTP boundary.
"""

from __future__ import annotations

import datetime
import os
import uuid

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.session_tokens import hash_token, new_session_token
from app.schemas.clinical_context_summary import ClinicalContextSummary

pytestmark = pytest.mark.integration

ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"


def _admin_url() -> str:
    url = os.environ.get(ADMIN_ENV, "").strip()
    if not url:
        pytest.skip(f"{ADMIN_ENV} is not configured")
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


class Actor:
    def __init__(self, user_id: uuid.UUID, token: str) -> None:
        self.user_id = user_id
        self.token = token


def _seed_profile_with_actors(connection: psycopg.Connection) -> tuple[uuid.UUID, dict[str, Actor]]:
    """Create a profile plus users for each permission level and live sessions."""
    workspace = uuid.uuid4()
    profile = uuid.uuid4()
    actors: dict[str, Actor] = {}
    for role in ("owner", "edit", "view", "analyze", "outsider"):
        user_id = uuid.uuid4()
        token = new_session_token()
        actors[role] = Actor(user_id, token)
        connection.execute(
            """
            INSERT INTO health_compass.users (id, email, display_name, status)
            VALUES (%s, %s, %s, 'active')
            """,
            (user_id, f"http-{role}-{user_id}@example.test", role),
        )
        connection.execute(
            """
            INSERT INTO health_compass.auth_sessions
              (id, user_id, session_token_hash, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (
                uuid.uuid4(),
                user_id,
                hash_token(token),
                datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
            ),
        )
    owner = actors["owner"].user_id
    connection.execute(
        """
        INSERT INTO health_compass.workspaces (id, name, slug, created_by_user_id)
        VALUES (%s, 'HTTP matrix test', %s, %s)
        """,
        (workspace, f"http-{workspace}", owner),
    )
    connection.execute(
        """
        INSERT INTO health_compass.workspace_members (id, workspace_id, user_id, role)
        VALUES (%s, %s, %s, 'owner')
        """,
        (uuid.uuid4(), workspace, owner),
    )
    connection.execute(
        """
        INSERT INTO health_compass.health_profiles
          (id, workspace_id, owner_user_id, display_name)
        VALUES (%s, %s, %s, 'HTTP matrix profile')
        """,
        (profile, workspace, owner),
    )
    for role in ("owner", "edit", "view", "analyze"):
        connection.execute(
            """
            INSERT INTO health_compass.profile_permissions
              (id, profile_id, user_id, permission, granted_by_user_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (uuid.uuid4(), profile, actors[role].user_id, role, owner),
        )
    connection.execute(
        """
        INSERT INTO health_compass.user_consents
          (id, user_id, consent_type, document_version, accepted_at)
        VALUES (%s, %s, 'health_data_processing', 'v1', now())
        """,
        (uuid.uuid4(), owner),
    )
    return profile, actors


def _get_client(actor: Actor | None = None) -> AsyncClient:
    from app.core.config import settings
    from app.main import app

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    if actor is not None:
        client.cookies.set(settings.session_cookie_name, actor.token)
    return client


async def _dispose_app_engine() -> None:
    from app.db.session import engine

    await engine.dispose()


async def test_clinical_context_summary_contract_and_access_matrix() -> None:
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        profile, actors = _seed_profile_with_actors(connection)

    try:
        for role in ("owner", "edit", "view", "analyze"):
            async with _get_client(actors[role]) as client:
                response = await client.get(f"/profiles/{profile}/clinical-context")
            assert response.status_code == 200, (role, response.text)
            summary = ClinicalContextSummary.model_validate(response.json())
            assert str(summary.profile_id) == str(profile)
            for section in ("conditions", "allergies", "medications", "supplements"):
                state = summary.sections[section]
                assert state.review_state == "unknown"
                assert state.effective_state == "unknown"
                assert state.active_count == 0
                assert state.history_count == 0

        async with _get_client(actors["outsider"]) as client:
            outsider = await client.get(f"/profiles/{profile}/clinical-context")
        assert outsider.status_code == 404

        async with _get_client() as client:
            anonymous = await client.get(f"/profiles/{profile}/clinical-context")
        assert anonymous.status_code == 401
    finally:
        await _dispose_app_engine()


async def test_dictionary_integrity_violations_return_controlled_422() -> None:
    """HC-015 Slice D: DB-boundary rejections surface as validation errors."""
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        profile, actors = _seed_profile_with_actors(connection)
    owner = actors["owner"]
    medication_concept = "11111111-1111-4111-8111-111111111301"

    cases = [
        (medication_concept, "concept_domain_mismatch"),
        (str(uuid.uuid4()), "unknown_concept"),
        ("not-a-uuid-not-a-uuid-not-a-uuid-not-a-uuid", "invalid_concept_id"),
    ]
    try:
        async with _get_client(owner) as client:
            for code, expected_detail in cases:
                response = await client.post(
                    f"/profiles/{profile}/conditions",
                    json={
                        "display_name": "Проверка словаря",
                        "code_system": "health_compass",
                        "code": code,
                    },
                )
                assert response.status_code == 422, (code, response.text)
                assert response.json()["detail"] == expected_detail
    finally:
        await _dispose_app_engine()


async def test_review_and_create_flow_keeps_summary_contract() -> None:
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        profile, actors = _seed_profile_with_actors(connection)
    owner = actors["owner"]

    try:
        async with _get_client(owner) as client:
            reviewed = await client.post(
                f"/profiles/{profile}/clinical-context/review",
                json={"section": "allergies", "review_state": "confirmed_none"},
            )
            assert reviewed.status_code == 200, reviewed.text
            summary = ClinicalContextSummary.model_validate(reviewed.json())
            assert summary.sections["allergies"].review_state == "confirmed_none"
            assert summary.sections["allergies"].effective_state == "confirmed_none"

            created = await client.post(
                f"/profiles/{profile}/allergies",
                json={"substance_name": "Пенициллин"},
            )
            assert created.status_code == 201, created.text

            after = await client.get(f"/profiles/{profile}/clinical-context")
            assert after.status_code == 200
            summary = ClinicalContextSummary.model_validate(after.json())
            allergies = summary.sections["allergies"]
            assert allergies.review_state == "unknown"
            assert allergies.effective_state == "has_entries"
            assert allergies.active_count == 1
            assert allergies.history_count == 1
    finally:
        await _dispose_app_engine()
