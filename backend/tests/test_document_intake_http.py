"""HTTP-level acceptance tests for HC-017 secure document intake."""

from __future__ import annotations

import datetime
import os
import uuid
from pathlib import Path

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.session_tokens import hash_token, new_session_token

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


def _seed_profile(connection: psycopg.Connection) -> tuple[uuid.UUID, uuid.UUID, dict[str, Actor]]:
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
            (user_id, f"document-http-{role}-{user_id}@example.test", role),
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
        VALUES (%s, 'Document HTTP test', %s, %s)
        """,
        (workspace, f"document-http-{workspace}", owner),
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
        VALUES (%s, %s, %s, 'Document HTTP profile')
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
    return workspace, profile, actors


def _client(actor: Actor | None = None) -> AsyncClient:
    from app.core.config import settings
    from app.main import app

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    if actor is not None:
        client.cookies.set(settings.session_cookie_name, actor.token)
    return client


async def _dispose_engine() -> None:
    from app.db.session import engine

    await engine.dispose()


def _cleanup(
    workspace: uuid.UUID,
    profile: uuid.UUID,
    actors: dict[str, Actor],
) -> None:
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        connection.execute(
            "DELETE FROM health_compass.document_processing_jobs WHERE profile_id = %s",
            (profile,),
        )
        connection.execute(
            "DELETE FROM health_compass.profile_documents WHERE profile_id = %s",
            (profile,),
        )
        connection.execute(
            "DELETE FROM health_compass.profile_audit_events WHERE profile_id = %s",
            (profile,),
        )
        connection.execute(
            "DELETE FROM health_compass.profile_permissions WHERE profile_id = %s",
            (profile,),
        )
        connection.execute(
            "DELETE FROM health_compass.health_profiles WHERE id = %s",
            (profile,),
        )
        connection.execute(
            "DELETE FROM health_compass.workspace_members WHERE workspace_id = %s",
            (workspace,),
        )
        connection.execute(
            "DELETE FROM health_compass.workspaces WHERE id = %s",
            (workspace,),
        )
        connection.execute(
            "DELETE FROM health_compass.user_consents WHERE user_id = ANY(%s)",
            ([actor.user_id for actor in actors.values()],),
        )
        connection.execute(
            "DELETE FROM health_compass.auth_sessions WHERE user_id = ANY(%s)",
            ([actor.user_id for actor in actors.values()],),
        )
        connection.execute(
            "DELETE FROM health_compass.users WHERE id = ANY(%s)",
            ([actor.user_id for actor in actors.values()],),
        )


async def test_quarantine_upload_and_document_access_matrix(tmp_path: Path) -> None:
    from app.core.config import settings

    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        workspace, profile, actors = _seed_profile(connection)

    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    key_path = credentials / "test-key"
    key_path.write_bytes(b"k" * 32)
    os.chmod(key_path, 0o400)
    storage_root = tmp_path / "objects"

    old_values = {
        "document_upload_enabled": settings.document_upload_enabled,
        "document_storage_root": settings.document_storage_root,
        "document_credentials_directory": settings.document_credentials_directory,
        "document_encryption_active_key_id": settings.document_encryption_active_key_id,
        "document_min_free_bytes": settings.document_min_free_bytes,
    }
    settings.document_upload_enabled = True
    settings.document_storage_root = str(storage_root)
    settings.document_credentials_directory = str(credentials)
    settings.document_encryption_active_key_id = "test-key"
    settings.document_min_free_bytes = 0

    try:
        for role, expected_upload in (
            ("owner", True),
            ("edit", True),
            ("view", False),
            ("analyze", False),
        ):
            async with _client(actors[role]) as client:
                capabilities = await client.get(
                    f"/profiles/{profile}/document-intake/capabilities"
                )
            assert capabilities.status_code == 200, (role, capabilities.text)
            assert capabilities.json()["upload_enabled"] is expected_upload
            assert capabilities.json()["ocr_available"] is False

        async with _client(actors["outsider"]) as client:
            outsider_capabilities = await client.get(
                f"/profiles/{profile}/document-intake/capabilities"
            )
        assert outsider_capabilities.status_code == 404

        async with _client(actors["owner"]) as client:
            uploaded = await client.post(
                f"/profiles/{profile}/documents",
                files={"file": ("analysis.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
            )
        assert uploaded.status_code == 201, uploaded.text
        payload = uploaded.json()
        document_id = uuid.UUID(payload["id"])
        assert payload["status"] == "quarantined"
        assert payload["scanner_status"] == "not_scanned"
        assert payload["original_filename"] == "analysis.pdf"
        assert "sha256" not in payload
        assert "quarantine_storage_key" not in payload

        encrypted_path = storage_root / f"quarantine/{document_id}/original.hcenc"
        assert encrypted_path.exists()
        assert b"%PDF" not in encrypted_path.read_bytes()

        for role in ("owner", "edit", "view"):
            async with _client(actors[role]) as client:
                listed = await client.get(f"/profiles/{profile}/documents")
                detail = await client.get(
                    f"/profiles/{profile}/documents/{document_id}"
                )
            assert listed.status_code == 200, (role, listed.text)
            assert [item["id"] for item in listed.json()] == [str(document_id)]
            assert detail.status_code == 200, (role, detail.text)

        async with _client(actors["analyze"]) as client:
            analyze_list = await client.get(f"/profiles/{profile}/documents")
            analyze_detail = await client.get(
                f"/profiles/{profile}/documents/{document_id}"
            )
        assert analyze_list.status_code == 200
        assert analyze_list.json() == []
        assert analyze_detail.status_code == 404

        async with _client(actors["outsider"]) as client:
            outsider = await client.get(f"/profiles/{profile}/documents")
        assert outsider.status_code == 404

        async with _client() as client:
            anonymous = await client.get(f"/profiles/{profile}/documents")
        assert anonymous.status_code == 401

        with psycopg.connect(_admin_url()) as connection:
            audit = connection.execute(
                """
                SELECT action, changed_fields
                FROM health_compass.profile_audit_events
                WHERE profile_id = %s AND entity_id = %s
                """,
                (profile, document_id),
            ).fetchone()
            assert audit == ("document.uploaded", {})
            document = connection.execute(
                """
                SELECT storage_backend, encryption_format, encryption_key_id,
                       encrypted_size > byte_size, scanner_status
                FROM health_compass.profile_documents
                WHERE id = %s
                """,
                (document_id,),
            ).fetchone()
            assert document == (
                "local_encrypted",
                "hcenc1",
                "test-key",
                True,
                "not_scanned",
            )
            job = connection.execute(
                """
                SELECT job_type, status, attempt
                FROM health_compass.document_processing_jobs
                WHERE document_id = %s
                """,
                (document_id,),
            ).fetchone()
            assert job == ("scan", "queued", 0)
    finally:
        for name, value in old_values.items():
            setattr(settings, name, value)
        await _dispose_engine()
        _cleanup(workspace, profile, actors)


async def test_upload_is_fail_safe_when_feature_is_disabled() -> None:
    from app.core.config import settings

    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        workspace, profile, actors = _seed_profile(connection)

    old_enabled = settings.document_upload_enabled
    settings.document_upload_enabled = False
    try:
        async with _client(actors["owner"]) as client:
            capabilities = await client.get(
                f"/profiles/{profile}/document-intake/capabilities"
            )
            response = await client.post(
                f"/profiles/{profile}/documents",
                files={"file": ("analysis.pdf", b"%PDF-1.4\n%%EOF\n", "application/pdf")},
            )
        assert capabilities.status_code == 200
        assert capabilities.json()["upload_enabled"] is False
        assert response.status_code == 503
    finally:
        settings.document_upload_enabled = old_enabled
        await _dispose_engine()
        _cleanup(workspace, profile, actors)
