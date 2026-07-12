"""PostgreSQL acceptance tests and shared fixture for HC-017 Lab flows."""

from __future__ import annotations

import json
import os
import uuid
from decimal import Decimal

import psycopg
import pytest

pytestmark = pytest.mark.integration
ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"
APP_ENV = "TEST_DATABASE_URL"


def _sync_url(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        pytest.skip(f"{env_name} is not configured")
    return value.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _set_user(connection: psycopg.Connection, user_id: uuid.UUID) -> None:
    connection.execute(
        "SELECT set_config('app.current_user_id', %s, true)", (str(user_id),)
    )


def _draft_payload() -> dict[str, object]:
    return {
        "source_analyte_text": "Глюкоза",
        "source_value_text": "5.4",
        "value_kind": "numeric",
        "numeric_value": "5.4",
        "source_unit_text": "ммоль/л",
        "unit_not_present": False,
        "source_reference_range_text": "3.9–6.1",
        "reference_range_not_present": False,
        "source_observed_at_text": "12.07.2026",
        "observed_time_unknown": False,
        "observed_date": "2026-07-12",
        "observed_precision": "date",
    }


@pytest.fixture
def lab_fixture() -> dict[str, object]:
    ids = {
        name: uuid.uuid4()
        for name in (
            "owner",
            "editor",
            "viewer",
            "analyzer",
            "outsider",
            "workspace",
            "profile",
            "document",
            "render_run",
            "ocr_run",
            "page_artifact",
            "candidate_analyte",
            "candidate_value",
            "patient_decision",
            "consent",
        )
    }
    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        for role in ("owner", "editor", "viewer", "analyzer", "outsider"):
            connection.execute(
                "INSERT INTO health_compass.users (id,email,display_name,status) "
                "VALUES (%s,%s,%s,'active')",
                (ids[role], f"lab-{role}-{ids[role]}@example.test", role),
            )
        connection.execute(
            "INSERT INTO health_compass.workspaces "
            "(id,name,slug,created_by_user_id) VALUES (%s,'Lab test',%s,%s)",
            (ids["workspace"], f"lab-{ids['workspace']}", ids["owner"]),
        )
        connection.execute(
            "INSERT INTO health_compass.workspace_members "
            "(id,workspace_id,user_id,role) VALUES (%s,%s,%s,'owner')",
            (uuid.uuid4(), ids["workspace"], ids["owner"]),
        )
        connection.execute(
            "INSERT INTO health_compass.health_profiles "
            "(id,workspace_id,owner_user_id,display_name) "
            "VALUES (%s,%s,%s,'Lab profile')",
            (ids["profile"], ids["workspace"], ids["owner"]),
        )
        for role, permission in (
            ("owner", "owner"),
            ("editor", "edit"),
            ("viewer", "view"),
            ("analyzer", "analyze"),
        ):
            connection.execute(
                "INSERT INTO health_compass.profile_permissions "
                "(id,profile_id,user_id,permission,granted_by_user_id) "
                "VALUES (%s,%s,%s,%s,%s)",
                (
                    uuid.uuid4(),
                    ids["profile"],
                    ids[role],
                    permission,
                    ids["owner"],
                ),
            )
        connection.execute(
            "INSERT INTO health_compass.user_consents "
            "(id,user_id,consent_type,document_version,accepted_at) "
            "VALUES (%s,%s,'health_data_processing','v1',now())",
            (ids["consent"], ids["owner"]),
        )
        connection.execute(
            """
            INSERT INTO health_compass.profile_documents (
              id,profile_id,uploaded_by_user_id,status,original_filename,
              declared_media_type,detected_media_type,byte_size,encrypted_size,
              sha256,storage_backend,quarantine_storage_key,current_storage_key,
              accepted_storage_key,encryption_format,encryption_key_id,
              scanner_status,scanner_engine,scanner_version,
              scanner_signature_version,scanner_signature_timestamp,
              scanner_completed_at,render_status,render_run_id,render_engine,
              render_version,render_completed_at,ocr_status,current_ocr_run_id,
              ocr_completed_at,page_count
            ) VALUES (
              %s,%s,%s,'accepted','analysis.pdf','application/pdf',
              'application/pdf',10,64,%s,'local_encrypted',%s,%s,%s,'hcenc1',
              'test-key','clean','clamav','1.4.3','27800',now(),now(),'ready',
              %s,'hc-safe-renderer','1',now(),'review_required',%s,now(),1
            )
            """,
            (
                ids["document"],
                ids["profile"],
                ids["owner"],
                "a" * 64,
                f"quarantine/{ids['document']}/original.hcenc",
                f"accepted/{ids['document']}/original.hcenc",
                f"accepted/{ids['document']}/original.hcenc",
                ids["render_run"],
                ids["ocr_run"],
            ),
        )
        connection.execute(
            """
            INSERT INTO health_compass.document_artifacts (
              id,document_id,profile_id,run_id,artifact_type,page_number,status,
              storage_backend,storage_key,media_type,byte_size,encrypted_size,
              sha256,encryption_format,encryption_key_id,width,height
            ) VALUES (%s,%s,%s,%s,'safe_page',1,'ready','local_encrypted',%s,
              'image/png',10,64,%s,'hcenc1','test-key',100,100)
            """,
            (
                ids["page_artifact"],
                ids["document"],
                ids["profile"],
                ids["render_run"],
                f"derived/{ids['document']}/{ids['render_run']}/page-1.png.hcenc",
                "b" * 64,
            ),
        )
        connection.execute(
            """
            INSERT INTO health_compass.document_ocr_runs (
              id,document_id,profile_id,render_run_id,status,attempt,
              idempotency_key,input_manifest_sha256,output_manifest_sha256,
              engine_name,engine_version,language_spec,
              traineddata_manifest_sha256,psm,completed_at
            ) VALUES (%s,%s,%s,%s,'succeeded',1,%s,%s,%s,'tesseract','5.3.0',
              'rus+eng',%s,6,now())
            """,
            (
                ids["ocr_run"],
                ids["document"],
                ids["profile"],
                ids["render_run"],
                f"ocr:{ids['document']}:{ids['render_run']}:rus+eng:6",
                "c" * 64,
                "d" * 64,
                "e" * 64,
            ),
        )
        for candidate_id, index, text_value in (
            (ids["candidate_analyte"], 0, "Глюкоза"),
            (ids["candidate_value"], 1, "5.4 ммоль/л"),
        ):
            connection.execute(
                """
                INSERT INTO health_compass.document_ocr_candidates (
                  id,run_id,document_id,profile_id,page_artifact_id,page_number,
                  candidate_index,status,original_text,reviewed_text,
                  confidence_min,confidence_mean,left_px,top_px,width_px,
                  height_px,source_word_count,reviewed_by_user_id,reviewed_at
                ) VALUES (%s,%s,%s,%s,%s,1,%s,'accepted',%s,%s,85,92,10,%s,
                  70,15,2,%s,now())
                """,
                (
                    candidate_id,
                    ids["ocr_run"],
                    ids["document"],
                    ids["profile"],
                    ids["page_artifact"],
                    index,
                    text_value,
                    text_value,
                    20 + index * 20,
                    ids["owner"],
                ),
            )
        connection.execute(
            "INSERT INTO health_compass.document_ocr_patient_decisions "
            "(id,run_id,document_id,profile_id,decision,note,"
            "decided_by_user_id,decided_at) "
            "VALUES (%s,%s,%s,%s,'match',NULL,%s,now())",
            (
                ids["patient_decision"],
                ids["ocr_run"],
                ids["document"],
                ids["profile"],
                ids["owner"],
            ),
        )
        versions = connection.execute(
            "SELECT jsonb_agg(jsonb_build_object("
            "'id',id::text,'updated_at',updated_at::text) "
            "ORDER BY candidate_index) "
            "FROM health_compass.document_ocr_candidates WHERE run_id=%s",
            (ids["ocr_run"],),
        ).fetchone()[0]
        connection.execute(
            """
            UPDATE health_compass.document_ocr_runs SET
              review_status='finalized',review_finalized_by_user_id=%s,
              review_finalized_at=now(),review_source_document_updated_at=(
                SELECT updated_at FROM health_compass.profile_documents
                WHERE id=%s),review_candidate_versions=%s,
              review_patient_decision_id=%s,
              review_patient_decision_updated_at=(SELECT updated_at FROM
                health_compass.document_ocr_patient_decisions WHERE id=%s),
              updated_at=now()
            WHERE id=%s
            """,
            (
                ids["owner"],
                ids["document"],
                json.dumps(versions),
                ids["patient_decision"],
                ids["patient_decision"],
                ids["ocr_run"],
            ),
        )
        connection.execute(
            "UPDATE health_compass.profile_documents SET ocr_status='reviewed',"
            "updated_at=clock_timestamp() WHERE id=%s",
            (ids["document"],),
        )
    yield ids
    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "UPDATE health_compass.document_ocr_runs SET "
            "review_status='not_started', review_finalized_by_user_id=NULL, "
            "review_finalized_at=NULL, review_source_document_updated_at=NULL, "
            "review_candidate_versions=NULL, review_patient_decision_id=NULL, "
            "review_patient_decision_updated_at=NULL WHERE profile_id=%s",
            (ids["profile"],),
        )
        for statement in (
            "DELETE FROM health_compass.lab_observation_sources WHERE profile_id=%s",
            "DELETE FROM health_compass.lab_observations WHERE profile_id=%s",
            "DELETE FROM health_compass.lab_observation_draft_sources "
            "WHERE profile_id=%s",
            "DELETE FROM health_compass.lab_observation_drafts WHERE profile_id=%s",
            "DELETE FROM health_compass.document_ocr_patient_decisions "
            "WHERE profile_id=%s",
            "DELETE FROM health_compass.document_ocr_candidates WHERE profile_id=%s",
            "DELETE FROM health_compass.document_ocr_runs WHERE profile_id=%s",
            "DELETE FROM health_compass.document_artifacts WHERE profile_id=%s",
            "DELETE FROM health_compass.profile_audit_events WHERE profile_id=%s",
            "DELETE FROM health_compass.profile_documents WHERE profile_id=%s",
            "DELETE FROM health_compass.profile_permissions WHERE profile_id=%s",
        ):
            connection.execute(statement, (ids["profile"],))
        connection.execute(
            "DELETE FROM health_compass.user_consents WHERE user_id=%s",
            (ids["owner"],),
        )
        connection.execute(
            "DELETE FROM health_compass.health_profiles WHERE id=%s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.workspace_members WHERE workspace_id=%s",
            (ids["workspace"],),
        )
        connection.execute(
            "DELETE FROM health_compass.workspaces WHERE id=%s",
            (ids["workspace"],),
        )
        connection.execute(
            "DELETE FROM health_compass.users WHERE id=ANY(%s)",
            (
                [
                    ids[name]
                    for name in (
                        "owner",
                        "editor",
                        "viewer",
                        "analyzer",
                        "outsider",
                    )
                ],
            ),
        )


def _context_versions(connection: psycopg.Connection, ids: dict[str, object]):
    return connection.execute(
        """
        SELECT d.updated_at,r.review_finalized_at,pd.updated_at
        FROM health_compass.profile_documents d
        JOIN health_compass.document_ocr_runs r ON r.id=d.current_ocr_run_id
        JOIN health_compass.document_ocr_patient_decisions pd
          ON pd.id=r.review_patient_decision_id WHERE d.id=%s
        """,
        (ids["document"],),
    ).fetchone()


def _create_ready_draft(
    connection: psycopg.Connection,
    ids: dict[str, object],
    *,
    actor: uuid.UUID | None = None,
) -> tuple[uuid.UUID, object, object, object, object]:
    _set_user(connection, actor or ids["owner"])
    document_at, finalized_at, decision_at = _context_versions(connection, ids)
    draft_id = uuid.uuid4()
    assert connection.execute(
        "SELECT health_compass.app_create_lab_observation_draft("
        "%s,%s,%s,%s,%s,%s::jsonb,%s,'lab-test')",
        (
            draft_id,
            ids["document"],
            document_at,
            finalized_at,
            decision_at,
            json.dumps(_draft_payload()),
            uuid.uuid4(),
        ),
    ).fetchone() == (draft_id,)
    draft_at = connection.execute(
        "SELECT updated_at FROM health_compass.lab_observation_drafts "
        "WHERE id=%s",
        (draft_id,),
    ).fetchone()[0]
    candidates = connection.execute(
        "SELECT id,updated_at FROM health_compass.document_ocr_candidates "
        "WHERE run_id=%s ORDER BY candidate_index",
        (ids["ocr_run"],),
    ).fetchall()
    manifest = [
        {
            "candidate_id": str(candidates[0][0]),
            "source_role": "analyte",
            "expected_updated_at": candidates[0][1].isoformat(),
        },
        {
            "candidate_id": str(candidates[1][0]),
            "source_role": "value",
            "expected_updated_at": candidates[1][1].isoformat(),
        },
    ]
    assert connection.execute(
        "SELECT health_compass.app_set_lab_draft_sources("
        "%s,%s,%s,%s,%s,%s::jsonb,%s,'lab-test')",
        (
            draft_id,
            draft_at,
            document_at,
            finalized_at,
            decision_at,
            json.dumps(manifest),
            uuid.uuid4(),
        ),
    ).fetchone() == (True,)
    draft_at = connection.execute(
        "SELECT updated_at FROM health_compass.lab_observation_drafts "
        "WHERE id=%s",
        (draft_id,),
    ).fetchone()[0]
    assert connection.execute(
        "SELECT health_compass.app_set_lab_observation_draft_status("
        "%s,'ready',%s,%s,%s,%s,%s,'lab-test')",
        (
            draft_id,
            draft_at,
            document_at,
            finalized_at,
            decision_at,
            uuid.uuid4(),
        ),
    ).fetchone() == (True,)
    ready_at = connection.execute(
        "SELECT updated_at FROM health_compass.lab_observation_drafts "
        "WHERE id=%s",
        (draft_id,),
    ).fetchone()[0]
    return draft_id, ready_at, document_at, finalized_at, decision_at


def test_ready_draft_remains_non_clinical(lab_fixture: dict[str, object]) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        draft_id, *_ = _create_ready_draft(connection, ids)
    for role, expected in (
        ("owner", 1),
        ("editor", 1),
        ("viewer", 0),
        ("analyzer", 0),
        ("outsider", 0),
    ):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ids[role])
            assert connection.execute(
                "SELECT count(*) FROM health_compass.lab_observation_drafts "
                "WHERE id=%s",
                (draft_id,),
            ).fetchone() == (expected,)
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        row = connection.execute(
            "SELECT status,source_analyte_text,source_value_text,source_unit_text,"
            "numeric_value FROM health_compass.lab_observation_drafts WHERE id=%s",
            (draft_id,),
        ).fetchone()
        assert row == (
            "ready",
            "Глюкоза",
            "5.4",
            "ммоль/л",
            Decimal("5.400000000000"),
        )
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observations "
            "WHERE source_draft_id=%s",
            (draft_id,),
        ).fetchone() == (0,)


def test_revoked_consent_blocks_new_draft(lab_fixture: dict[str, object]) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "UPDATE health_compass.user_consents SET revoked_at=now() WHERE id=%s",
            (ids["consent"],),
        )
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        document_at, finalized_at, decision_at = _context_versions(connection, ids)
        with pytest.raises(psycopg.DatabaseError) as denied:
            connection.execute(
                "SELECT health_compass.app_create_lab_observation_draft("
                "%s,%s,%s,%s,%s,%s::jsonb,%s,'lab-test')",
                (
                    uuid.uuid4(),
                    ids["document"],
                    document_at,
                    finalized_at,
                    decision_at,
                    json.dumps(_draft_payload()),
                    uuid.uuid4(),
                ),
            ).fetchone()
        assert denied.value.sqlstate == "HC409"
