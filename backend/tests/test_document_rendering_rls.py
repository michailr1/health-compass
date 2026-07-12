"""PostgreSQL integration tests for HC-017 C2 renderer and reconciler roles."""

from __future__ import annotations

import datetime
import json
import os
import uuid

import psycopg
import pytest
from psycopg.rows import dict_row

pytestmark = pytest.mark.integration

ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"
APP_ENV = "TEST_DATABASE_URL"
RENDERER_ENV = "TEST_DATABASE_RENDERER_URL"
RECONCILER_ENV = "TEST_DATABASE_RECONCILER_URL"


def _sync_url(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        pytest.skip(f"{env_name} is not configured")
    return value.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _set_user(connection: psycopg.Connection, user_id: uuid.UUID) -> None:
    connection.execute(
        "SELECT set_config('app.current_user_id', %s, true)",
        (str(user_id),),
    )


@pytest.fixture
def rendering_fixture() -> dict[str, uuid.UUID]:
    ids = {
        "owner": uuid.uuid4(),
        "viewer": uuid.uuid4(),
        "analyzer": uuid.uuid4(),
        "outsider": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "profile": uuid.uuid4(),
        "document": uuid.uuid4(),
        "job": uuid.uuid4(),
    }
    source_key = f"quarantine/{ids['document']}/original.hcenc"
    digest = "a" * 64

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        for role in ("owner", "viewer", "analyzer", "outsider"):
            connection.execute(
                """
                INSERT INTO health_compass.users (id, email, display_name, status)
                VALUES (%s, %s, %s, 'active')
                """,
                (ids[role], f"render-{role}-{ids[role]}@example.test", role),
            )
        connection.execute(
            """
            INSERT INTO health_compass.workspaces
              (id, name, slug, created_by_user_id)
            VALUES (%s, 'Render test', %s, %s)
            """,
            (ids["workspace"], f"render-{ids['workspace']}", ids["owner"]),
        )
        connection.execute(
            """
            INSERT INTO health_compass.workspace_members
              (id, workspace_id, user_id, role)
            VALUES (%s, %s, %s, 'owner')
            """,
            (uuid.uuid4(), ids["workspace"], ids["owner"]),
        )
        connection.execute(
            """
            INSERT INTO health_compass.health_profiles
              (id, workspace_id, owner_user_id, display_name)
            VALUES (%s, %s, %s, 'Render profile')
            """,
            (ids["profile"], ids["workspace"], ids["owner"]),
        )
        for role, permission in (
            ("owner", "owner"),
            ("viewer", "view"),
            ("analyzer", "analyze"),
        ):
            connection.execute(
                """
                INSERT INTO health_compass.profile_permissions
                  (id, profile_id, user_id, permission, granted_by_user_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (uuid.uuid4(), ids["profile"], ids[role], permission, ids["owner"]),
            )
        connection.execute(
            """
            INSERT INTO health_compass.profile_documents (
              id, profile_id, uploaded_by_user_id, status, original_filename,
              declared_media_type, detected_media_type, byte_size, encrypted_size,
              sha256, storage_backend, quarantine_storage_key, current_storage_key,
              encryption_format, encryption_key_id, scanner_status, scanner_engine,
              scanner_version, scanner_signature_version,
              scanner_signature_timestamp, scanner_completed_at, render_status
            ) VALUES (
              %s, %s, %s, 'quarantined', 'render.pdf',
              'application/pdf', 'application/pdf', 10, 64,
              %s, 'local_encrypted', %s, %s,
              'hcenc1', 'test-key', 'clean', 'clamav',
              '1.4.3', '27800', now() - interval '5 minutes', now(), 'queued'
            )
            """,
            (
                ids["document"],
                ids["profile"],
                ids["owner"],
                digest,
                source_key,
                source_key,
            ),
        )
        connection.execute(
            """
            INSERT INTO health_compass.document_processing_jobs (
              id, document_id, profile_id, job_type, status, attempt,
              idempotency_key, input_sha256
            ) VALUES (%s, %s, %s, 'render', 'queued', 0, %s, %s)
            """,
            (
                ids["job"],
                ids["document"],
                ids["profile"],
                f"render:{ids['document']}:safe-render-v1",
                digest,
            ),
        )

    yield ids

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "DELETE FROM health_compass.document_artifacts WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.document_processing_jobs WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.profile_audit_events WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.profile_documents WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.profile_permissions WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.health_profiles WHERE id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.workspace_members WHERE workspace_id = %s",
            (ids["workspace"],),
        )
        connection.execute(
            "DELETE FROM health_compass.workspaces WHERE id = %s",
            (ids["workspace"],),
        )
        connection.execute(
            "DELETE FROM health_compass.users WHERE id = ANY(%s)",
            ([ids[key] for key in ("owner", "viewer", "analyzer", "outsider")],),
        )


def test_renderer_completion_and_reconciler_reference_flow(
    rendering_fixture: dict[str, uuid.UUID],
) -> None:
    renderer_id = "renderer:test"
    with psycopg.connect(_sync_url(RENDERER_ENV)) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT id FROM health_compass.profile_documents")

    with psycopg.connect(
        _sync_url(RENDERER_ENV),
        row_factory=dict_row,
    ) as connection:
        claimed = connection.execute(
            "SELECT * FROM health_compass.app_claim_render_job(%s, 300, 3)",
            (renderer_id,),
        ).fetchone()
    assert claimed is not None
    assert claimed["job_id"] == rendering_fixture["job"]
    assert claimed["document_id"] == rendering_fixture["document"]

    with psycopg.connect(_sync_url(RENDERER_ENV)) as connection:
        with pytest.raises(psycopg.DatabaseError) as exc_info:
            connection.execute(
                """
                SELECT health_compass.app_heartbeat_render_job(%s, %s, %s, 300)
                """,
                (
                    rendering_fixture["job"],
                    renderer_id,
                    claimed["lease_expires_at"] - datetime.timedelta(seconds=1),
                ),
            ).fetchone()
        assert exc_info.value.sqlstate == "HC409"

    run_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    accepted_key = f"accepted/{rendering_fixture['document']}/original.hcenc"
    artifact_key = (
        f"derived/{rendering_fixture['document']}/{run_id}/page-1.png.hcenc"
    )
    artifacts = [
        {
            "id": str(artifact_id),
            "page_number": 1,
            "storage_key": artifact_key,
            "media_type": "image/png",
            "byte_size": 10,
            "encrypted_size": 64,
            "sha256": "b" * 64,
            "encryption_format": "hcenc1",
            "encryption_key_id": "test-key",
            "width": 1,
            "height": 1,
        }
    ]
    audit_id = uuid.uuid4()
    completion_args = (
        rendering_fixture["job"],
        renderer_id,
        claimed["lease_expires_at"],
        run_id,
        accepted_key,
        64,
        "hcenc1",
        "test-key",
        1,
        "hc-safe-renderer",
        "1",
        json.dumps(artifacts),
        audit_id,
    )
    for _ in range(2):
        with psycopg.connect(_sync_url(RENDERER_ENV)) as connection:
            assert connection.execute(
                """
                SELECT health_compass.app_complete_document_render(
                  %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s::jsonb, %s
                )
                """,
                completion_args,
            ).fetchone() == (True,)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        document = connection.execute(
            """
            SELECT status, render_status, render_run_id, current_storage_key,
                   accepted_storage_key, page_count
            FROM health_compass.profile_documents WHERE id = %s
            """,
            (rendering_fixture["document"],),
        ).fetchone()
        artifact = connection.execute(
            """
            SELECT id, run_id, status, storage_key, page_number
            FROM health_compass.document_artifacts WHERE document_id = %s
            """,
            (rendering_fixture["document"],),
        ).fetchone()
        job = connection.execute(
            """
            SELECT status, attempt, lease_owner, lease_expires_at
            FROM health_compass.document_processing_jobs WHERE id = %s
            """,
            (rendering_fixture["job"],),
        ).fetchone()
        audit_count = connection.execute(
            """
            SELECT count(*) FROM health_compass.profile_audit_events
            WHERE entity_id = %s AND action = 'document.render_ready'
              AND changed_fields = '{}'::jsonb
            """,
            (rendering_fixture["document"],),
        ).fetchone()[0]
    assert document == (
        "accepted",
        "ready",
        run_id,
        accepted_key,
        accepted_key,
        1,
    )
    assert artifact == (artifact_id, run_id, "ready", artifact_key, 1)
    assert job == ("succeeded", 1, None, None)
    assert audit_count == 1

    with psycopg.connect(_sync_url(RECONCILER_ENV)) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT id FROM health_compass.document_artifacts")
    with psycopg.connect(_sync_url(RECONCILER_ENV)) as connection:
        references = connection.execute(
            "SELECT storage_key, artifact_role "
            "FROM health_compass.app_list_document_storage_references() "
            "WHERE document_id = %s ORDER BY artifact_role",
            (rendering_fixture["document"],),
        ).fetchall()
    assert references == [
        (artifact_key, "safe_page:1"),
        (accepted_key, "source"),
    ]

    for role, expected in (("owner", True), ("viewer", True), ("analyzer", False), ("outsider", False)):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, rendering_fixture[role])
            row = connection.execute(
                "SELECT id FROM health_compass.document_artifacts WHERE id = %s",
                (artifact_id,),
            ).fetchone()
            assert (row is not None) is expected
