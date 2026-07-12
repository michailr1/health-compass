"""PostgreSQL acceptance tests for HC-017 E1 Lab drafts."""

from __future__ import annotations

from decimal import Decimal

import json
import os
import uuid

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
        "SELECT set_config('app.current_user_id', %s, true)",
        (str(user_id),),
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
    ids: dict[str, object] = {
        "owner": uuid.uuid4(),
        "editor": uuid.uuid4(),
        "viewer": uuid.uuid4(),
        "analyzer": uuid.uuid4(),
        "outsider": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "profile": uuid.uuid4(),
        "document": uuid.uuid4(),
        "render_run": uuid.uuid4(),
        "ocr_run": uuid.uuid4(),
        "page_artifact": uuid.uuid4(),
        "candidate_analyte": uuid.uuid4(),
        "candidate_value": uuid.uuid4(),
        "patient_decision": uuid.uuid4(),
        "consent": uuid.uuid4(),
    }
    quarantine_key = f"quarantine/{ids['document']}/original.hcenc"
    accepted_key = f"accepted/{ids['document']}/original.hcenc"
    page_key = f"derived/{ids['document']}/{ids['render_run']}/page-1.png.hcenc"

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        for role in ("owner", "editor", "viewer", "analyzer", "outsider"):
            connection.execute(
                """
                INSERT INTO health_compass.users (id, email, display_name, status)
                VALUES (%s, %s, %s, 'active')
                """,
                (ids[role], f"lab-draft-{role}-{ids[role]}@example.test", role),
            )
        connection.execute(
            """
            INSERT INTO health_compass.workspaces
              (id, name, slug, created_by_user_id)
            VALUES (%s, 'Lab draft test', %s, %s)
            """,
            (ids["workspace"], f"lab-draft-{ids['workspace']}", ids["owner"]),
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
            VALUES (%s, %s, %s, 'Lab draft profile')
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
            INSERT INTO health_compass.user_consents
              (id, user_id, consent_type, document_version, accepted_at)
            VALUES (%s, %s, 'health_data_processing', 'v1', now())
            """,
            (ids["consent"], ids["owner"]),
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
              render_version, render_completed_at, ocr_status, current_ocr_run_id,
              ocr_completed_at, page_count
            ) VALUES (
              %s, %s, %s, 'accepted', 'analysis.pdf',
              'application/pdf', 'application/pdf', 10, 64,
              %s, 'local_encrypted', %s, %s, %s, 'hcenc1', 'test-key',
              'clean', 'clamav', '1.4.3', '27800', now() - interval '10 minutes',
              now() - interval '9 minutes', 'ready', %s, 'hc-safe-renderer',
              '1', now() - interval '5 minutes', 'review_required', %s,
              now() - interval '1 minute', 1
            )
            """,
            (
                ids["document"],
                ids["profile"],
                ids["owner"],
                "a" * 64,
                quarantine_key,
                accepted_key,
                accepted_key,
                ids["render_run"],
                ids["ocr_run"],
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
                ids["page_artifact"],
                ids["document"],
                ids["profile"],
                ids["render_run"],
                page_key,
                "b" * 64,
            ),
        )
        connection.execute(
            """
            INSERT INTO health_compass.document_ocr_runs (
              id, document_id, profile_id, render_run_id, status, attempt,
              idempotency_key, input_manifest_sha256, output_manifest_sha256,
              engine_name, engine_version, language_spec,
              traineddata_manifest_sha256, psm, completed_at
            ) VALUES (
              %s, %s, %s, %s, 'succeeded', 1,
              %s, %s, %s, 'tesseract', '5.3.0', 'rus+eng', %s, 6, now()
            )
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
        for candidate_id, candidate_index, text_value in (
            (ids["candidate_analyte"], 0, "Глюкоза"),
            (ids["candidate_value"], 1, "5.4 ммоль/л"),
        ):
            connection.execute(
                """
                INSERT INTO health_compass.document_ocr_candidates (
                  id, run_id, document_id, profile_id, page_artifact_id,
                  page_number, candidate_index, status, original_text,
                  reviewed_text, confidence_min, confidence_mean,
                  left_px, top_px, width_px, height_px, source_word_count,
                  reviewed_by_user_id, reviewed_at
                ) VALUES (
                  %s, %s, %s, %s, %s, 1, %s, 'accepted', %s, %s,
                  85, 92, 10, %s, 70, 15, 2, %s, now()
                )
                """,
                (
                    candidate_id,
                    ids["ocr_run"],
                    ids["document"],
                    ids["profile"],
                    ids["page_artifact"],
                    candidate_index,
                    text_value,
                    text_value,
                    20 + candidate_index * 20,
                    ids["owner"],
                ),
            )
        connection.execute(
            """
            INSERT INTO health_compass.document_ocr_patient_decisions (
              id, run_id, document_id, profile_id, decision, note,
              decided_by_user_id, decided_at
            ) VALUES (%s, %s, %s, %s, 'match', NULL, %s, now())
            """,
            (
                ids["patient_decision"],
                ids["ocr_run"],
                ids["document"],
                ids["profile"],
                ids["owner"],
            ),
        )
        versions = connection.execute(
            """
            SELECT jsonb_agg(jsonb_build_object(
              'id', id::text, 'updated_at', updated_at::text
            ) ORDER BY candidate_index)
            FROM health_compass.document_ocr_candidates WHERE run_id = %s
            """,
            (ids["ocr_run"],),
        ).fetchone()[0]
        connection.execute(
            """
            UPDATE health_compass.document_ocr_runs
            SET review_status = 'finalized',
                review_finalized_by_user_id = %s,
                review_finalized_at = now(),
                review_source_document_updated_at = (
                  SELECT updated_at FROM health_compass.profile_documents WHERE id = %s
                ),
                review_candidate_versions = %s,
                review_patient_decision_id = %s,
                review_patient_decision_updated_at = (
                  SELECT updated_at FROM health_compass.document_ocr_patient_decisions
                  WHERE id = %s
                ),
                updated_at = now()
            WHERE id = %s
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
            "UPDATE health_compass.profile_documents "
            "SET ocr_status = 'reviewed', updated_at = clock_timestamp() WHERE id = %s",
            (ids["document"],),
        )

    yield ids

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "DELETE FROM health_compass.lab_observation_draft_sources WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.lab_observation_drafts WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "UPDATE health_compass.document_ocr_runs "
            "SET review_status = 'not_started', review_finalized_by_user_id = NULL, "
            "review_finalized_at = NULL, review_source_document_updated_at = NULL, "
            "review_candidate_versions = NULL, review_patient_decision_id = NULL, "
            "review_patient_decision_updated_at = NULL WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.document_ocr_patient_decisions WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.document_ocr_candidates WHERE profile_id = %s",
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
            "DELETE FROM health_compass.user_consents WHERE user_id = %s",
            (ids["owner"],),
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


def _context_versions(connection: psycopg.Connection, ids: dict[str, object]):
    return connection.execute(
        """
        SELECT d.updated_at, r.review_finalized_at, pd.updated_at
        FROM health_compass.profile_documents d
        JOIN health_compass.document_ocr_runs r ON r.id = d.current_ocr_run_id
        JOIN health_compass.document_ocr_patient_decisions pd
          ON pd.id = r.review_patient_decision_id
        WHERE d.id = %s
        """,
        (ids["document"],),
    ).fetchone()


def test_lab_draft_source_preserving_flow(lab_fixture: dict[str, object]) -> None:
    ids = lab_fixture
    draft_id = uuid.uuid4()

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "INSERT INTO health_compass.lab_observation_drafts "
                "(id, profile_id, document_id, ocr_run_id, patient_decision_id, "
                "status, source_analyte_text, source_value_text, value_kind, "
                "unit_not_present, reference_range_not_present, observed_time_unknown, "
                "observed_precision, created_by_user_id, updated_by_user_id) "
                "VALUES (%s,%s,%s,%s,%s,'draft','x','1','numeric',true,true,true,"
                "'unknown',%s,%s)",
                (
                    draft_id,
                    ids["profile"],
                    ids["document"],
                    ids["ocr_run"],
                    ids["patient_decision"],
                    ids["owner"],
                    ids["owner"],
                ),
            )

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        document_updated_at, finalized_at, decision_updated_at = _context_versions(
            connection, ids
        )
        created = connection.execute(
            """
            SELECT health_compass.app_create_lab_observation_draft(
              %s,%s,%s,%s,%s,%s::jsonb,%s,'lab-draft-test'
            )
            """,
            (
                draft_id,
                ids["document"],
                document_updated_at,
                finalized_at,
                decision_updated_at,
                json.dumps(_draft_payload()),
                uuid.uuid4(),
            ),
        ).fetchone()
        assert created == (draft_id,)
        initial_updated_at = connection.execute(
            "SELECT updated_at FROM health_compass.lab_observation_drafts WHERE id = %s",
            (draft_id,),
        ).fetchone()[0]
        candidates = connection.execute(
            "SELECT id, updated_at FROM health_compass.document_ocr_candidates "
            "WHERE run_id = %s ORDER BY candidate_index",
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
            """
            SELECT health_compass.app_set_lab_draft_sources(
              %s,%s,%s::jsonb,%s,'lab-draft-test'
            )
            """,
            (draft_id, initial_updated_at, json.dumps(manifest), uuid.uuid4()),
        ).fetchone() == (True,)
        after_sources = connection.execute(
            "SELECT updated_at FROM health_compass.lab_observation_drafts WHERE id = %s",
            (draft_id,),
        ).fetchone()[0]

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        document_updated_at, finalized_at, decision_updated_at = _context_versions(
            connection, ids
        )
        with pytest.raises(psycopg.DatabaseError) as stale:
            connection.execute(
                """
                SELECT health_compass.app_update_lab_observation_draft(
                  %s,%s,%s,%s,%s,%s::jsonb,%s,'lab-draft-test'
                )
                """,
                (
                    draft_id,
                    initial_updated_at,
                    document_updated_at,
                    finalized_at,
                    decision_updated_at,
                    json.dumps(_draft_payload()),
                    uuid.uuid4(),
                ),
            ).fetchone()
        assert stale.value.sqlstate == "HC409"

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["editor"])
        assert connection.execute(
            """
            SELECT health_compass.app_set_lab_observation_draft_status(
              %s,'ready',%s,%s,'lab-draft-test'
            )
            """,
            (draft_id, after_sources, uuid.uuid4()),
        ).fetchone() == (True,)

    for role, expected in (
        ("owner", 1),
        ("editor", 1),
        ("viewer", 0),
        ("analyzer", 0),
        ("outsider", 0),
    ):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ids[role])
            count = connection.execute(
                "SELECT count(*) FROM health_compass.lab_observation_drafts "
                "WHERE profile_id = %s",
                (ids["profile"],),
            ).fetchone()[0]
            assert count == expected, role

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        row = connection.execute(
            """
            SELECT status, source_analyte_text, source_value_text,
                   source_unit_text, numeric_value
            FROM health_compass.lab_observation_drafts WHERE id = %s
            """,
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
            "SELECT count(*) FROM health_compass.lab_observation_draft_sources "
            "WHERE draft_id = %s",
            (draft_id,),
        ).fetchone() == (2,)
        audit_rows = connection.execute(
            "SELECT action, changed_fields FROM health_compass.profile_audit_events "
            "WHERE entity_id = %s ORDER BY occurred_at",
            (draft_id,),
        ).fetchall()
        assert [row[0] for row in audit_rows] == [
            "lab.draft_created",
            "lab.draft_sources_changed",
            "lab.draft_status_changed",
        ]
        assert all(row[1] == {} for row in audit_rows)
        assert connection.execute(
            "SELECT to_regclass('health_compass.lab_observations')"
        ).fetchone() == (None,)
        for table in ("profile_conditions", "body_measurements"):
            assert connection.execute(
                f"SELECT count(*) FROM health_compass.{table} WHERE profile_id = %s",
                (ids["profile"],),
            ).fetchone() == (0,)


def test_lab_draft_security_catalog_and_consent(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    signatures = (
        "app_create_lab_observation_draft(uuid,uuid,timestamp with time zone,"
        "timestamp with time zone,timestamp with time zone,jsonb,uuid,text)",
        "app_update_lab_observation_draft(uuid,timestamp with time zone,"
        "timestamp with time zone,timestamp with time zone,"
        "timestamp with time zone,jsonb,uuid,text)",
        "app_set_lab_draft_sources(uuid,timestamp with time zone,jsonb,uuid,text)",
        "app_set_lab_observation_draft_status(uuid,text,timestamp with time zone,uuid,text)",
    )
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        rls = connection.execute(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'health_compass'
              AND relname IN ('lab_observation_drafts','lab_observation_draft_sources')
            ORDER BY relname
            """
        ).fetchall()
        assert len(rls) == 2
        assert all(row[1] and row[2] for row in rls)
        for signature in signatures:
            qualified = f"health_compass.{signature}"
            assert connection.execute(
                "SELECT has_function_privilege('health_compass_app', %s, 'EXECUTE')",
                (qualified,),
            ).fetchone() == (True,)
            assert connection.execute(
                "SELECT has_function_privilege('public', %s, 'EXECUTE')",
                (qualified,),
            ).fetchone() == (False,)
            for worker in (
                "health_compass_worker",
                "health_compass_renderer",
                "health_compass_reconciler",
                "health_compass_ocr_worker",
            ):
                assert connection.execute(
                    "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
                    (worker, qualified),
                ).fetchone() == (False,)
        mutations = connection.execute(
            """
            SELECT table_name, privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee = 'health_compass_app'
              AND table_schema = 'health_compass'
              AND table_name IN ('lab_observation_drafts','lab_observation_draft_sources')
              AND privilege_type IN ('INSERT','UPDATE','DELETE')
            """
        ).fetchall()
        assert mutations == []

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "UPDATE health_compass.user_consents SET revoked_at = now() WHERE id = %s",
            (ids["consent"],),
        )
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        document_updated_at, finalized_at, decision_updated_at = _context_versions(
            connection, ids
        )
        with pytest.raises(psycopg.DatabaseError) as denied:
            connection.execute(
                """
                SELECT health_compass.app_create_lab_observation_draft(
                  %s,%s,%s,%s,%s,%s::jsonb,%s,'lab-draft-test'
                )
                """,
                (
                    uuid.uuid4(),
                    ids["document"],
                    document_updated_at,
                    finalized_at,
                    decision_updated_at,
                    json.dumps(_draft_payload()),
                    uuid.uuid4(),
                ),
            ).fetchone()
        assert denied.value.sqlstate == "HC409"
