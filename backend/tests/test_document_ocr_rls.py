"""PostgreSQL integration tests for HC-017 D1 OCR worker and candidate RLS."""

from __future__ import annotations

import datetime
import hashlib
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
OCR_ENV = "TEST_DATABASE_OCR_URL"


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


def _input_manifest(
    artifact_id: uuid.UUID,
    *,
    sha256: str,
    width: int,
    height: int,
) -> str:
    payload = [
        {
            "id": str(artifact_id),
            "page_number": 1,
            "sha256": sha256,
            "width": width,
            "height": height,
        }
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


@pytest.fixture
def ocr_fixture() -> dict[str, uuid.UUID | str]:
    ids: dict[str, uuid.UUID | str] = {
        "owner": uuid.uuid4(),
        "editor": uuid.uuid4(),
        "viewer": uuid.uuid4(),
        "analyzer": uuid.uuid4(),
        "outsider": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "profile": uuid.uuid4(),
        "document": uuid.uuid4(),
        "render_run": uuid.uuid4(),
        "page_artifact": uuid.uuid4(),
        "ocr_run": uuid.uuid4(),
    }
    document_id = ids["document"]
    render_run = ids["render_run"]
    page_artifact = ids["page_artifact"]
    quarantine_key = f"quarantine/{document_id}/original.hcenc"
    accepted_key = f"accepted/{document_id}/original.hcenc"
    page_key = f"derived/{document_id}/{render_run}/page-1.png.hcenc"
    ids["page_sha"] = "b" * 64

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        for role in ("owner", "editor", "viewer", "analyzer", "outsider"):
            connection.execute(
                """
                INSERT INTO health_compass.users (id, email, display_name, status)
                VALUES (%s, %s, %s, 'active')
                """,
                (ids[role], f"ocr-{role}-{ids[role]}@example.test", role),
            )
        connection.execute(
            """
            INSERT INTO health_compass.workspaces
              (id, name, slug, created_by_user_id)
            VALUES (%s, 'OCR test', %s, %s)
            """,
            (ids["workspace"], f"ocr-{ids['workspace']}", ids["owner"]),
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
            VALUES (%s, %s, %s, 'OCR profile')
            """,
            (ids["profile"], ids["workspace"], ids["owner"]),
        )
        for role, permission in (
            ("owner", "owner"),
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
        connection.execute(
            """
            INSERT INTO health_compass.profile_documents (
              id, profile_id, uploaded_by_user_id, status, original_filename,
              declared_media_type, detected_media_type, byte_size, encrypted_size,
              sha256, storage_backend, quarantine_storage_key, current_storage_key,
              accepted_storage_key, encryption_format, encryption_key_id,
              scanner_status, scanner_engine, scanner_version,
              scanner_signature_version, scanner_signature_timestamp,
              scanner_completed_at, render_status, render_run_id, render_engine,
              render_version, render_completed_at, page_count
            ) VALUES (
              %s, %s, %s, 'accepted', 'analysis.pdf',
              'application/pdf', 'application/pdf', 10, 64,
              %s, 'local_encrypted', %s, %s, %s, 'hcenc1', 'test-key',
              'clean', 'clamav', '1.4.3', '27800', now() - interval '10 minutes',
              now() - interval '9 minutes', 'ready', %s, 'hc-safe-renderer',
              '1', now() - interval '5 minutes', 1
            )
            """,
            (
                document_id,
                ids["profile"],
                ids["owner"],
                "a" * 64,
                quarantine_key,
                accepted_key,
                accepted_key,
                render_run,
            ),
        )
        connection.execute(
            """
            INSERT INTO health_compass.document_artifacts (
              id, document_id, profile_id, run_id, artifact_type, page_number,
              status, storage_backend, storage_key, media_type, byte_size,
              encrypted_size, sha256, encryption_format, encryption_key_id,
              width, height
            ) VALUES (
              %s, %s, %s, %s, 'safe_page', 1,
              'ready', 'local_encrypted', %s, 'image/png', 10,
              64, %s, 'hcenc1', 'test-key', 100, 100
            )
            """,
            (
                page_artifact,
                document_id,
                ids["profile"],
                render_run,
                page_key,
                ids["page_sha"],
            ),
        )

    yield ids

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "DELETE FROM health_compass.document_ocr_candidates WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.document_ocr_artifacts WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.document_ocr_runs WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.document_artifacts WHERE profile_id = %s",
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
            ([ids[key] for key in ("owner", "editor", "viewer", "analyzer", "outsider")],),
        )


def test_ocr_queue_claim_completion_and_candidate_rls(
    ocr_fixture: dict[str, uuid.UUID | str],
) -> None:
    input_manifest = _input_manifest(
        ocr_fixture["page_artifact"],
        sha256=str(ocr_fixture["page_sha"]),
        width=100,
        height=100,
    )
    with psycopg.connect(_sync_url(RENDERER_ENV)) as connection:
        assert connection.execute(
            """
            SELECT health_compass.app_queue_document_ocr(
              %s, %s, %s, %s, %s, 'rus+eng', 6
            )
            """,
            (
                ocr_fixture["document"],
                ocr_fixture["render_run"],
                ocr_fixture["ocr_run"],
                f"ocr:{ocr_fixture['document']}:{ocr_fixture['render_run']}:rus+eng:6",
                input_manifest,
            ),
        ).fetchone() == (True,)

    with psycopg.connect(_sync_url(OCR_ENV)) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT id FROM health_compass.document_ocr_runs")

    worker_id = "ocr-worker:test"
    with psycopg.connect(_sync_url(OCR_ENV), row_factory=dict_row) as connection:
        claimed = connection.execute(
            "SELECT * FROM health_compass.app_claim_document_ocr_run(%s, 300, 3)",
            (worker_id,),
        ).fetchone()
    assert claimed is not None
    assert claimed["run_id"] == ocr_fixture["ocr_run"]
    assert claimed["input_manifest_sha256"] == input_manifest
    assert len(claimed["pages"]) == 1

    with psycopg.connect(_sync_url(OCR_ENV)) as connection:
        with pytest.raises(psycopg.DatabaseError) as exc_info:
            connection.execute(
                """
                SELECT health_compass.app_heartbeat_document_ocr_run(%s, %s, %s, 300)
                """,
                (
                    ocr_fixture["ocr_run"],
                    worker_id,
                    claimed["lease_expires_at"] - datetime.timedelta(seconds=1),
                ),
            ).fetchone()
        assert exc_info.value.sqlstate == "HC409"

    artifact_id = uuid.uuid5(ocr_fixture["ocr_run"], "tsv:1")
    candidate_id = uuid.uuid5(ocr_fixture["ocr_run"], "candidate:1:0")
    artifact_payload = [
        {
            "id": str(artifact_id),
            "page_artifact_id": str(ocr_fixture["page_artifact"]),
            "page_number": 1,
            "storage_key": (
                f"ocr/{ocr_fixture['document']}/{ocr_fixture['ocr_run']}/page-1.tsv.hcenc"
            ),
            "byte_size": 100,
            "encrypted_size": 160,
            "sha256": "c" * 64,
            "encryption_format": "hcenc1",
            "encryption_key_id": "test-key",
        }
    ]
    candidate_payload = [
        {
            "id": str(candidate_id),
            "page_artifact_id": str(ocr_fixture["page_artifact"]),
            "page_number": 1,
            "candidate_index": 0,
            "original_text": "Глюкоза 5.4 ммоль/л",
            "confidence_min": 84.0,
            "confidence_mean": 91.5,
            "left_px": 10,
            "top_px": 20,
            "width_px": 70,
            "height_px": 15,
            "word_count": 3,
        }
    ]
    completion_args = (
        ocr_fixture["ocr_run"],
        worker_id,
        claimed["lease_expires_at"],
        "tesseract",
        "5.3.0",
        "d" * 64,
        "e" * 64,
        json.dumps(artifact_payload),
        json.dumps(candidate_payload, ensure_ascii=False),
        uuid.uuid4(),
    )
    for _ in range(2):
        with psycopg.connect(_sync_url(OCR_ENV)) as connection:
            assert connection.execute(
                """
                SELECT health_compass.app_complete_document_ocr_run(
                  %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s
                )
                """,
                completion_args,
            ).fetchone() == (True,)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        document = connection.execute(
            """
            SELECT ocr_status, current_ocr_run_id, ocr_completed_at IS NOT NULL
            FROM health_compass.profile_documents WHERE id = %s
            """,
            (ocr_fixture["document"],),
        ).fetchone()
        run = connection.execute(
            """
            SELECT status, attempt, engine_name, engine_version,
                   traineddata_manifest_sha256, output_manifest_sha256
            FROM health_compass.document_ocr_runs WHERE id = %s
            """,
            (ocr_fixture["ocr_run"],),
        ).fetchone()
        artifact = connection.execute(
            """
            SELECT status, artifact_type, storage_key
            FROM health_compass.document_ocr_artifacts WHERE id = %s
            """,
            (artifact_id,),
        ).fetchone()
        candidate = connection.execute(
            """
            SELECT status, original_text, reviewed_text
            FROM health_compass.document_ocr_candidates WHERE id = %s
            """,
            (candidate_id,),
        ).fetchone()
        audit_count = connection.execute(
            """
            SELECT count(*) FROM health_compass.profile_audit_events
            WHERE entity_id = %s AND action = 'document.ocr_ready'
              AND changed_fields = '{}'::jsonb
            """,
            (ocr_fixture["document"],),
        ).fetchone()[0]
        clinical_count = sum(
            connection.execute(
                f"SELECT count(*) FROM health_compass.{table} WHERE profile_id = %s",
                (ocr_fixture["profile"],),
            ).fetchone()[0]
            for table in (
                "profile_conditions",
                "profile_allergies",
                "profile_medications",
                "profile_supplements",
                "body_measurements",
            )
        )
    assert document == ("review_required", ocr_fixture["ocr_run"], True)
    assert run == ("succeeded", 1, "tesseract", "5.3.0", "d" * 64, "e" * 64)
    assert artifact[0:2] == ("ready", "tesseract_tsv")
    assert candidate == ("needs_review", "Глюкоза 5.4 ммоль/л", None)
    assert audit_count == 1
    assert clinical_count == 0

    for role, expected in (
        ("owner", True),
        ("editor", True),
        ("viewer", False),
        ("analyzer", False),
        ("outsider", False),
    ):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ocr_fixture[role])
            row = connection.execute(
                "SELECT original_text FROM health_compass.document_ocr_candidates WHERE id = %s",
                (candidate_id,),
            ).fetchone()
            assert (row is not None) is expected


def test_ocr_functions_are_hardened_and_exclusive() -> None:
    ocr_signatures = (
        "app_claim_document_ocr_run(text,integer,integer)",
        "app_heartbeat_document_ocr_run(uuid,text,timestamp with time zone,integer)",
        (
            "app_complete_document_ocr_run(uuid,text,timestamp with time zone,text,text,"
            "text,text,jsonb,jsonb,uuid)"
        ),
        (
            "app_fail_document_ocr_run(uuid,text,timestamp with time zone,text,boolean,"
            "integer,integer,uuid)"
        ),
    )
    queue_signature = "app_queue_document_ocr(uuid,uuid,uuid,text,text,text,integer)"
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        for signature in ocr_signatures:
            row = connection.execute(
                """
                SELECT p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig,
                       has_function_privilege('public', p.oid, 'EXECUTE'),
                       has_function_privilege('health_compass_app', p.oid, 'EXECUTE'),
                       has_function_privilege('health_compass_renderer', p.oid, 'EXECUTE'),
                       has_function_privilege('health_compass_ocr_worker', p.oid, 'EXECUTE')
                FROM pg_proc p WHERE p.oid = %s::regprocedure
                """,
                (f"health_compass.{signature}",),
            ).fetchone()
            assert row is not None
            assert row[0] is True
            assert row[1] == "health_compass_rls_definer"
            assert "row_security=off" in (row[2] or [])
            assert row[3:] == (False, False, False, True)

        queue = connection.execute(
            """
            SELECT has_function_privilege('public', p.oid, 'EXECUTE'),
                   has_function_privilege('health_compass_app', p.oid, 'EXECUTE'),
                   has_function_privilege('health_compass_renderer', p.oid, 'EXECUTE'),
                   has_function_privilege('health_compass_ocr_worker', p.oid, 'EXECUTE')
            FROM pg_proc p WHERE p.oid = %s::regprocedure
            """,
            (f"health_compass.{queue_signature}",),
        ).fetchone()
        assert queue == (False, False, True, False)

        for table in (
            "document_ocr_runs",
            "document_ocr_artifacts",
            "document_ocr_candidates",
        ):
            rls = connection.execute(
                """
                SELECT c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'health_compass' AND c.relname = %s
                """,
                (table,),
            ).fetchone()
            assert rls == (True, True)
            grants = connection.execute(
                """
                SELECT privilege_type FROM information_schema.role_table_grants
                WHERE grantee = 'health_compass_ocr_worker'
                  AND table_schema = 'health_compass' AND table_name = %s
                """,
                (table,),
            ).fetchall()
            assert grants == []
