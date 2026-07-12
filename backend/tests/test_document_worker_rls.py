"""PostgreSQL tests for the HC-017 restricted scanner worker boundary."""

from __future__ import annotations

import datetime
import os
import uuid

import psycopg
import pytest
from psycopg.rows import dict_row

pytestmark = pytest.mark.integration

ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"
WORKER_ENV = "TEST_DATABASE_WORKER_URL"


def _sync_url(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        pytest.skip(f"{env_name} is not configured")
    return value.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


@pytest.fixture
def worker_fixture() -> dict[str, object]:
    ids: dict[str, object] = {
        "owner": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "profile": uuid.uuid4(),
        "clean_document": uuid.uuid4(),
        "infected_document": uuid.uuid4(),
        "retry_document": uuid.uuid4(),
        "clean_job": uuid.uuid4(),
        "infected_job": uuid.uuid4(),
        "retry_job": uuid.uuid4(),
    }

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            """
            INSERT INTO health_compass.users (id, email, display_name, status)
            VALUES (%s, %s, 'Document worker owner', 'active')
            """,
            (ids["owner"], f"document-worker-{ids['owner']}@example.test"),
        )
        connection.execute(
            """
            INSERT INTO health_compass.workspaces
              (id, name, slug, created_by_user_id)
            VALUES (%s, 'Document worker test', %s, %s)
            """,
            (ids["workspace"], f"document-worker-{ids['workspace']}", ids["owner"]),
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
            VALUES (%s, %s, %s, 'Document worker profile')
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

        for index, kind in enumerate(("clean", "infected", "retry"), start=1):
            document_id = ids[f"{kind}_document"]
            job_id = ids[f"{kind}_job"]
            digest = f"{index:x}" * 64
            connection.execute(
                """
                INSERT INTO health_compass.profile_documents (
                  id, profile_id, uploaded_by_user_id, status, original_filename,
                  declared_media_type, detected_media_type, byte_size, encrypted_size,
                  sha256, storage_backend, quarantine_storage_key,
                  encryption_format, encryption_key_id, scanner_status
                ) VALUES (
                  %s, %s, %s, 'quarantined', %s,
                  'application/pdf', 'application/pdf', 10, 64,
                  %s, 'local_encrypted', %s,
                  'hcenc1', 'test-key', 'not_scanned'
                )
                """,
                (
                    document_id,
                    ids["profile"],
                    ids["owner"],
                    f"{kind}.pdf",
                    digest,
                    f"quarantine/{document_id}/original.hcenc",
                ),
            )
            connection.execute(
                """
                INSERT INTO health_compass.document_processing_jobs (
                  id, document_id, profile_id, job_type, status, attempt,
                  idempotency_key, input_sha256, created_at
                ) VALUES (
                  %s, %s, %s, 'scan', 'queued', 0, %s, %s,
                  now() + make_interval(secs => %s)
                )
                """,
                (
                    job_id,
                    document_id,
                    ids["profile"],
                    f"scan:{document_id}:clamav-v1",
                    digest,
                    index,
                ),
            )

    yield ids

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
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
            "DELETE FROM health_compass.users WHERE id = %s",
            (ids["owner"],),
        )


def _claim(worker_id: str) -> dict[str, object] | None:
    with psycopg.connect(
        _sync_url(WORKER_ENV),
        row_factory=dict_row,
    ) as connection:
        return connection.execute(
            "SELECT * FROM health_compass.app_claim_document_job(%s, 300, 5)",
            (worker_id,),
        ).fetchone()


def test_restricted_worker_queue_flow(worker_fixture: dict[str, object]) -> None:
    with psycopg.connect(_sync_url(WORKER_ENV)) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT id FROM health_compass.profile_documents")
    with psycopg.connect(_sync_url(WORKER_ENV)) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "UPDATE health_compass.document_processing_jobs SET status = 'failed'"
            )

    clean_worker = "scanner-worker:test-clean"
    clean = _claim(clean_worker)
    assert clean is not None
    assert clean["job_id"] == worker_fixture["clean_job"]
    assert clean["storage_backend"] == "local_encrypted"
    assert clean["encryption_format"] == "hcenc1"

    with psycopg.connect(_sync_url(WORKER_ENV)) as connection:
        with pytest.raises(psycopg.DatabaseError) as exc_info:
            connection.execute(
                """
                SELECT health_compass.app_heartbeat_document_job(%s, %s, %s, 300)
                """,
                (
                    worker_fixture["clean_job"],
                    clean_worker,
                    clean["lease_expires_at"] - datetime.timedelta(seconds=1),
                ),
            ).fetchone()
        assert exc_info.value.sqlstate == "HC409"

    render_job_id = uuid.uuid4()
    clean_audit_id = uuid.uuid4()
    clean_args = (
        worker_fixture["clean_job"],
        clean_worker,
        clean["lease_expires_at"],
        "clamav",
        "1.4.3",
        "27800",
        datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=5),
        "clean",
        render_job_id,
        f"render:{worker_fixture['clean_document']}:safe-render-v1",
        clean_audit_id,
    )
    for _ in range(2):
        with psycopg.connect(_sync_url(WORKER_ENV)) as connection:
            assert connection.execute(
                """
                SELECT health_compass.app_complete_document_scan(
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                clean_args,
            ).fetchone() == (True,)

    infected_worker = "scanner-worker:test-infected"
    infected = _claim(infected_worker)
    assert infected is not None
    assert infected["job_id"] == worker_fixture["infected_job"]
    with psycopg.connect(_sync_url(WORKER_ENV)) as connection:
        assert connection.execute(
            """
            SELECT health_compass.app_complete_document_scan(
              %s, %s, %s, 'clamav', '1.4.3', '27800', %s,
              'infected', NULL, NULL, %s
            )
            """,
            (
                worker_fixture["infected_job"],
                infected_worker,
                infected["lease_expires_at"],
                datetime.datetime.now(datetime.UTC),
                uuid.uuid4(),
            ),
        ).fetchone() == (True,)

    retry_worker = "scanner-worker:test-retry"
    retry = _claim(retry_worker)
    assert retry is not None
    assert retry["job_id"] == worker_fixture["retry_job"]
    with psycopg.connect(_sync_url(WORKER_ENV)) as connection:
        assert connection.execute(
            """
            SELECT health_compass.app_fail_document_job(
              %s, %s, %s, 'scanner_unavailable', true, 5, 60
            )
            """,
            (
                worker_fixture["retry_job"],
                retry_worker,
                retry["lease_expires_at"],
            ),
        ).fetchone() == (True,)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        clean_document = connection.execute(
            """
            SELECT status, scanner_status, scanner_engine, failure_code
            FROM health_compass.profile_documents WHERE id = %s
            """,
            (worker_fixture["clean_document"],),
        ).fetchone()
        clean_job = connection.execute(
            """
            SELECT status, attempt, lease_owner, lease_expires_at
            FROM health_compass.document_processing_jobs WHERE id = %s
            """,
            (worker_fixture["clean_job"],),
        ).fetchone()
        render_jobs = connection.execute(
            """
            SELECT count(*) FROM health_compass.document_processing_jobs
            WHERE document_id = %s AND job_type = 'render'
            """,
            (worker_fixture["clean_document"],),
        ).fetchone()[0]
        clean_audits = connection.execute(
            """
            SELECT changed_fields FROM health_compass.profile_audit_events
            WHERE entity_id = %s AND action = 'document.scan_clean'
            """,
            (worker_fixture["clean_document"],),
        ).fetchall()

        infected_document = connection.execute(
            """
            SELECT status, scanner_status, failure_code,
                   deletion_requested_at IS NOT NULL
            FROM health_compass.profile_documents WHERE id = %s
            """,
            (worker_fixture["infected_document"],),
        ).fetchone()
        infected_render_count = connection.execute(
            """
            SELECT count(*) FROM health_compass.document_processing_jobs
            WHERE document_id = %s AND job_type = 'render'
            """,
            (worker_fixture["infected_document"],),
        ).fetchone()[0]
        infected_audit = connection.execute(
            """
            SELECT changed_fields FROM health_compass.profile_audit_events
            WHERE entity_id = %s AND action = 'document.scan_rejected'
            """,
            (worker_fixture["infected_document"],),
        ).fetchone()

        retry_job = connection.execute(
            """
            SELECT status, attempt, error_code, next_attempt_at IS NOT NULL,
                   lease_owner, lease_expires_at
            FROM health_compass.document_processing_jobs WHERE id = %s
            """,
            (worker_fixture["retry_job"],),
        ).fetchone()
        retry_document = connection.execute(
            """
            SELECT status, scanner_status, failure_code
            FROM health_compass.profile_documents WHERE id = %s
            """,
            (worker_fixture["retry_document"],),
        ).fetchone()

        assert clean_document == ("quarantined", "clean", "clamav", None)
        assert clean_job == ("succeeded", 1, None, None)
        assert render_jobs == 1
        assert clean_audits == [({},)]
        assert infected_document == (
            "rejected",
            "infected",
            "malware_detected",
            True,
        )
        assert infected_render_count == 0
        assert infected_audit == ({},)
        assert retry_job == (
            "queued",
            1,
            "scanner_unavailable",
            True,
            None,
            None,
        )
        assert retry_document == (
            "quarantined",
            "error",
            "scanner_unavailable",
        )


def test_worker_functions_are_hardened_and_exclusive() -> None:
    signatures = (
        "app_claim_document_job(text,integer,integer)",
        "app_heartbeat_document_job(uuid,text,timestamp with time zone,integer)",
        (
            "app_complete_document_scan(uuid,text,timestamp with time zone,text,text,"
            "text,timestamp with time zone,text,uuid,text,uuid)"
        ),
        (
            "app_fail_document_job(uuid,text,timestamp with time zone,text,boolean,"
            "integer,integer)"
        ),
    )
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        for signature in signatures:
            row = connection.execute(
                """
                SELECT p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig,
                       has_function_privilege('public', p.oid, 'EXECUTE'),
                       has_function_privilege('health_compass_app', p.oid, 'EXECUTE'),
                       has_function_privilege('health_compass_worker', p.oid, 'EXECUTE')
                FROM pg_proc p
                WHERE p.oid = %s::regprocedure
                """,
                (f"health_compass.{signature}",),
            ).fetchone()
            assert row is not None
            assert row[0] is True
            assert row[1] == "health_compass_rls_definer"
            assert "row_security=off" in (row[2] or [])
            assert any(item.startswith("search_path=") for item in (row[2] or []))
            assert row[3:] == (False, False, True)
