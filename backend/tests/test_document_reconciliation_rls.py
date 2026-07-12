"""PostgreSQL regression tests for HC-017 storage reconciliation."""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

pytestmark = pytest.mark.integration

ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"
RECONCILER_ENV = "TEST_DATABASE_RECONCILER_URL"


def _sync_url(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        pytest.skip(f"{env_name} is not configured")
    return value.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


@pytest.fixture
def missing_object_fixture() -> dict[str, uuid.UUID | str]:
    ids: dict[str, uuid.UUID | str] = {
        "owner": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "profile": uuid.uuid4(),
        "document": uuid.uuid4(),
    }
    storage_key = f"quarantine/{ids['document']}/original.hcenc"
    ids["storage_key"] = storage_key

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            """
            INSERT INTO health_compass.users (id, email, display_name, status)
            VALUES (%s, %s, 'Reconciliation owner', 'active')
            """,
            (ids["owner"], f"reconcile-{ids['owner']}@example.test"),
        )
        connection.execute(
            """
            INSERT INTO health_compass.workspaces
              (id, name, slug, created_by_user_id)
            VALUES (%s, 'Reconciliation test', %s, %s)
            """,
            (ids["workspace"], f"reconcile-{ids['workspace']}", ids["owner"]),
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
            VALUES (%s, %s, %s, 'Reconciliation profile')
            """,
            (ids["profile"], ids["workspace"], ids["owner"]),
        )
        connection.execute(
            """
            INSERT INTO health_compass.profile_permissions
              (id, profile_id, user_id, permission, granted_by_user_id)
            VALUES (%s, %s, %s, 'owner', %s)
            """,
            (uuid.uuid4(), ids["profile"], ids["owner"], ids["owner"]),
        )
        connection.execute(
            """
            INSERT INTO health_compass.profile_documents (
              id, profile_id, uploaded_by_user_id, status, original_filename,
              declared_media_type, detected_media_type, byte_size, encrypted_size,
              sha256, storage_backend, quarantine_storage_key, current_storage_key,
              encryption_format, encryption_key_id, scanner_status, render_status
            ) VALUES (
              %s, %s, %s, 'quarantined', 'missing.pdf',
              'application/pdf', 'application/pdf', 10, 64,
              %s, 'local_encrypted', %s, %s,
              'hcenc1', 'test-key', 'not_scanned', 'not_started'
            )
            """,
            (
                ids["document"],
                ids["profile"],
                ids["owner"],
                "c" * 64,
                storage_key,
                storage_key,
            ),
        )

    yield ids

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
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
            "DELETE FROM health_compass.users WHERE id = %s",
            (ids["owner"],),
        )


def test_repeated_missing_source_creates_one_audit_event(
    missing_object_fixture: dict[str, uuid.UUID | str],
) -> None:
    for _ in range(2):
        with psycopg.connect(_sync_url(RECONCILER_ENV)) as connection:
            assert connection.execute(
                """
                SELECT health_compass.app_mark_document_object_missing(
                  %s, 'document_object_missing', %s
                )
                """,
                (missing_object_fixture["storage_key"], uuid.uuid4()),
            ).fetchone() == (True,)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        document = connection.execute(
            """
            SELECT status, render_status, failure_code
            FROM health_compass.profile_documents WHERE id = %s
            """,
            (missing_object_fixture["document"],),
        ).fetchone()
        audits = connection.execute(
            """
            SELECT count(*) FROM health_compass.profile_audit_events
            WHERE entity_id = %s
              AND action = 'document.storage_missing'
              AND changed_fields = '{}'::jsonb
            """,
            (missing_object_fixture["document"],),
        ).fetchone()[0]
    assert document == ("failed", "error", "document_object_missing")
    assert audits == 1
