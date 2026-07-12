"""PostgreSQL RLS and privilege tests for HC-017 Slice B."""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"
APP_ENV = "TEST_DATABASE_URL"

pytestmark = pytest.mark.integration


def _sync_url(env_name: str) -> str:
    url = os.environ.get(env_name, "").strip()
    if not url:
        pytest.skip(f"{env_name} is not configured")
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _set_user(connection: psycopg.Connection, user_id: uuid.UUID) -> None:
    connection.execute(
        "SELECT set_config('app.current_user_id', %s, true)",
        (str(user_id),),
    )


@pytest.fixture(scope="module")
def document_fixture() -> dict[str, uuid.UUID]:
    ids = {
        "owner": uuid.uuid4(),
        "editor": uuid.uuid4(),
        "viewer": uuid.uuid4(),
        "analyzer": uuid.uuid4(),
        "outsider": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "profile": uuid.uuid4(),
        "document": uuid.uuid4(),
        "editor_document": uuid.uuid4(),
        "job": uuid.uuid4(),
    }

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        for role in ("owner", "editor", "viewer", "analyzer", "outsider"):
            connection.execute(
                """
                INSERT INTO health_compass.users
                  (id, email, display_name, status)
                VALUES (%s, %s, %s, 'active')
                """,
                (ids[role], f"document-{role}-{ids[role]}@example.test", role),
            )

        connection.execute(
            """
            INSERT INTO health_compass.workspaces
              (id, name, slug, created_by_user_id)
            VALUES (%s, 'Document RLS test', %s, %s)
            """,
            (ids["workspace"], f"document-{ids['workspace']}", ids["owner"]),
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
            VALUES (%s, %s, %s, 'Document profile')
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
        for role, permission in (
            ("editor", "edit"),
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

    yield ids

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "DELETE FROM health_compass.document_processing_jobs WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.profile_documents WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.profile_audit_events WHERE profile_id = %s",
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
            ([ids[key] for key in ("owner", "editor", "viewer", "analyzer", "outsider")],),
        )


def _insert_document(
    connection: psycopg.Connection,
    *,
    document_id: uuid.UUID,
    profile_id: uuid.UUID,
    actor_id: uuid.UUID,
    suffix: str,
) -> None:
    storage_key = f"quarantine/{document_id}/original"
    connection.execute(
        """
        INSERT INTO health_compass.profile_documents (
          id, profile_id, uploaded_by_user_id, status, original_filename,
          declared_media_type, detected_media_type, byte_size, sha256,
          storage_backend, quarantine_storage_key, current_storage_key
        ) VALUES (
          %s, %s, %s, 'quarantined', %s,
          'application/pdf', 'application/pdf', 10, %s,
          'local', %s, %s
        )
        """,
        (
            document_id,
            profile_id,
            actor_id,
            f"analysis-{suffix}.pdf",
            suffix * 64,
            storage_key,
            storage_key,
        ),
    )


def test_owner_and_editor_can_insert_documents(
    document_fixture: dict[str, uuid.UUID],
) -> None:
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, document_fixture["owner"])
        _insert_document(
            connection,
            document_id=document_fixture["document"],
            profile_id=document_fixture["profile"],
            actor_id=document_fixture["owner"],
            suffix="a",
        )
        connection.execute(
            """
            INSERT INTO health_compass.document_processing_jobs (
              id, document_id, profile_id, job_type, status, attempt,
              idempotency_key, input_sha256
            ) VALUES (%s, %s, %s, 'inspect', 'queued', 0, %s, %s)
            """,
            (
                document_fixture["job"],
                document_fixture["document"],
                document_fixture["profile"],
                f"inspect:{document_fixture['document']}:a",
                "a" * 64,
            ),
        )

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, document_fixture["editor"])
        _insert_document(
            connection,
            document_id=document_fixture["editor_document"],
            profile_id=document_fixture["profile"],
            actor_id=document_fixture["editor"],
            suffix="b",
        )


def test_owner_editor_and_viewer_can_read_but_analyze_cannot(
    document_fixture: dict[str, uuid.UUID],
) -> None:
    for role in ("owner", "editor", "viewer"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, document_fixture[role])
            row = connection.execute(
                "SELECT original_filename FROM health_compass.profile_documents WHERE id = %s",
                (document_fixture["document"],),
            ).fetchone()
            assert row == ("analysis-a.pdf",)
            assert connection.execute(
                "SELECT id FROM health_compass.document_processing_jobs WHERE id = %s",
                (document_fixture["job"],),
            ).fetchone() == (document_fixture["job"],)

    for role in ("analyzer", "outsider"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, document_fixture[role])
            assert connection.execute(
                "SELECT id FROM health_compass.profile_documents WHERE id = %s",
                (document_fixture["document"],),
            ).fetchone() is None
            assert connection.execute(
                "SELECT id FROM health_compass.document_processing_jobs WHERE id = %s",
                (document_fixture["job"],),
            ).fetchone() is None


def test_read_only_roles_and_outsider_cannot_insert(
    document_fixture: dict[str, uuid.UUID],
) -> None:
    for role in ("viewer", "analyzer", "outsider"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, document_fixture[role])
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                _insert_document(
                    connection,
                    document_id=uuid.uuid4(),
                    profile_id=document_fixture["profile"],
                    actor_id=document_fixture[role],
                    suffix="c",
                )


def test_app_role_cannot_update_or_delete_document_rows(
    document_fixture: dict[str, uuid.UUID],
) -> None:
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, document_fixture["owner"])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "UPDATE health_compass.profile_documents SET status = 'accepted' WHERE id = %s",
                (document_fixture["document"],),
            )

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, document_fixture["owner"])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "DELETE FROM health_compass.profile_documents WHERE id = %s",
                (document_fixture["document"],),
            )


def test_missing_context_fails_closed(document_fixture: dict[str, uuid.UUID]) -> None:
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        assert connection.execute(
            "SELECT id FROM health_compass.profile_documents WHERE id = %s",
            (document_fixture["document"],),
        ).fetchone() is None


def test_document_activity_blocks_empty_duplicate_assessment(
    document_fixture: dict[str, uuid.UUID],
) -> None:
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        payload = connection.execute(
            "SELECT health_compass.app_duplicate_user_activity(%s)",
            (document_fixture["owner"],),
        ).fetchone()[0]
        assert payload["is_empty"] is False
        assert payload["profile_documents"] >= 1
        assert payload["meaningful_count"] >= payload["profile_documents"]


def test_document_view_helper_is_restricted_and_hardened() -> None:
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        row = connection.execute(
            """
            SELECT
              p.prosecdef,
              pg_get_userbyid(p.proowner),
              p.proconfig,
              has_function_privilege('public', p.oid, 'EXECUTE')
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'health_compass'
              AND p.proname = 'app_can_view_document'
            """
        ).fetchone()
        assert row is not None
        assert row[0] is True
        assert row[1] == "health_compass_rls_definer"
        assert "search_path=\"\"" in (row[2] or []) or "search_path=" in (row[2] or [])
        assert "row_security=off" in (row[2] or [])
        assert row[3] is False
