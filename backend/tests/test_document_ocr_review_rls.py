"""PostgreSQL acceptance tests for HC-017 D2 human OCR review."""

from __future__ import annotations

import datetime
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


@pytest.fixture
def review_fixture() -> dict[str, object]:
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
        "candidate_one": uuid.uuid4(),
        "candidate_two": uuid.uuid4(),
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
                (ids[role], f"ocr-review-{role}-{ids[role]}@example.test", role),
            )
        connection.execute(
            """
            INSERT INTO health_compass.workspaces
              (id, name, slug, created_by_user_id)
            VALUES (%s, 'OCR review test', %s, %s)
            """,
            (ids["workspace"], f"ocr-review-{ids['workspace']}", ids["owner"]),
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
            VALUES (%s, %s, %s, 'OCR review profile')
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
        for candidate_id, candidate_index, original_text in (
            (ids["candidate_one"], 0, "Глюкоза 5.4 ммоль/л"),
            (ids["candidate_two"], 1, "Гемоглобин 145 г/л"),
        ):
            connection.execute(
                """
                INSERT INTO health_compass.document_ocr_candidates (
                  id, run_id, document_id, profile_id, page_artifact_id,
                  page_number, candidate_index, status, original_text,
                  confidence_min, confidence_mean, left_px, top_px,
                  width_px, height_px, source_word_count
                ) VALUES (
                  %s, %s, %s, %s, %s, 1, %s, 'needs_review', %s,
                  85, 92, 10, %s, 70, 15, 3
                )
                """,
                (
                    candidate_id,
                    ids["ocr_run"],
                    ids["document"],
                    ids["profile"],
                    ids["page_artifact"],
                    candidate_index,
                    original_text,
                    20 + candidate_index * 20,
                ),
            )

    yield ids

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "UPDATE health_compass.document_ocr_runs "
            "SET review_patient_decision_id = NULL "
            "WHERE profile_id = %s",
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


def _candidate_state(
    connection: psycopg.Connection,
    candidate_id: uuid.UUID,
) -> tuple[str, str | None, datetime.datetime]:
    return connection.execute(
        """
        SELECT status, reviewed_text, updated_at
        FROM health_compass.document_ocr_candidates WHERE id = %s
        """,
        (candidate_id,),
    ).fetchone()


def test_owner_editor_review_patient_decision_and_finalization(
    review_fixture: dict[str, object],
) -> None:
    ids = review_fixture

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "UPDATE health_compass.document_ocr_candidates "
                "SET status = 'accepted' WHERE id = %s",
                (ids["candidate_one"],),
            )

    for role, expected_count in (
        ("owner", 2),
        ("editor", 2),
        ("viewer", 0),
        ("analyzer", 0),
        ("outsider", 0),
    ):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ids[role])
            count = connection.execute(
                "SELECT count(*) FROM health_compass.document_ocr_candidates "
                "WHERE profile_id = %s",
                (ids["profile"],),
            ).fetchone()[0]
            assert count == expected_count, role

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        first = _candidate_state(connection, ids["candidate_one"])
        assert connection.execute(
            """
            SELECT health_compass.app_review_document_ocr_candidate(
              %s, 'accept', NULL, NULL, %s, %s, 'review-test'
            )
            """,
            (ids["candidate_one"], first[2], uuid.uuid4()),
        ).fetchone() == (True,)

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        with pytest.raises(psycopg.DatabaseError) as stale:
            connection.execute(
                """
                SELECT health_compass.app_review_document_ocr_candidate(
                  %s, 'accept', NULL, NULL, %s, %s, 'review-test'
                )
                """,
                (ids["candidate_one"], first[2], uuid.uuid4()),
            ).fetchone()
        assert stale.value.sqlstate == "HC409"

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["editor"])
        second = _candidate_state(connection, ids["candidate_two"])
        assert connection.execute(
            """
            SELECT health_compass.app_review_document_ocr_candidate(
              %s, 'defer', NULL, 'Нужно проверить позже', %s, %s, 'review-test'
            )
            """,
            (ids["candidate_two"], second[2], uuid.uuid4()),
        ).fetchone() == (True,)

    decision_id = uuid.uuid4()
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        document_updated_at = connection.execute(
            "SELECT updated_at FROM health_compass.profile_documents WHERE id = %s",
            (ids["document"],),
        ).fetchone()[0]
        assert connection.execute(
            """
            SELECT health_compass.app_set_document_ocr_patient_decision(
              %s, %s, 'mismatch', NULL, %s, NULL, %s, 'review-test'
            )
            """,
            (ids["document"], decision_id, document_updated_at, uuid.uuid4()),
        ).fetchone() == (True,)

    def current_versions(connection: psycopg.Connection) -> list[dict[str, str]]:
        rows = connection.execute(
            """
            SELECT id, updated_at FROM health_compass.document_ocr_candidates
            WHERE run_id = %s ORDER BY id
            """,
            (ids["ocr_run"],),
        ).fetchall()
        return [
            {"id": str(row[0]), "updated_at": row[1].isoformat()}
            for row in rows
        ]

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        document_updated_at = connection.execute(
            "SELECT updated_at FROM health_compass.profile_documents WHERE id = %s",
            (ids["document"],),
        ).fetchone()[0]
        decision_updated_at = connection.execute(
            "SELECT updated_at FROM health_compass.document_ocr_patient_decisions "
            "WHERE id = %s",
            (decision_id,),
        ).fetchone()[0]
        with pytest.raises(psycopg.DatabaseError) as mismatch:
            connection.execute(
                """
                SELECT health_compass.app_finalize_document_ocr_review(
                  %s, %s, %s::jsonb, %s, %s, 'review-test'
                )
                """,
                (
                    ids["document"],
                    document_updated_at,
                    json.dumps(current_versions(connection)),
                    decision_updated_at,
                    uuid.uuid4(),
                ),
            ).fetchone()
        assert mismatch.value.sqlstate == "HC409"

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["editor"])
        deferred = _candidate_state(connection, ids["candidate_two"])
        assert connection.execute(
            """
            SELECT health_compass.app_review_document_ocr_candidate(
              %s, 'edit', 'Гемоглобин 146 г/л', NULL, %s, %s, 'review-test'
            )
            """,
            (ids["candidate_two"], deferred[2], uuid.uuid4()),
        ).fetchone() == (True,)

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        document_updated_at = connection.execute(
            "SELECT updated_at FROM health_compass.profile_documents WHERE id = %s",
            (ids["document"],),
        ).fetchone()[0]
        decision_updated_at = connection.execute(
            "SELECT updated_at FROM health_compass.document_ocr_patient_decisions "
            "WHERE id = %s",
            (decision_id,),
        ).fetchone()[0]
        assert connection.execute(
            """
            SELECT health_compass.app_set_document_ocr_patient_decision(
              %s, %s, 'match', NULL, %s, %s, %s, 'review-test'
            )
            """,
            (
                ids["document"],
                decision_id,
                document_updated_at,
                decision_updated_at,
                uuid.uuid4(),
            ),
        ).fetchone() == (True,)

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        document_updated_at = connection.execute(
            "SELECT updated_at FROM health_compass.profile_documents WHERE id = %s",
            (ids["document"],),
        ).fetchone()[0]
        decision_updated_at = connection.execute(
            "SELECT updated_at FROM health_compass.document_ocr_patient_decisions "
            "WHERE id = %s",
            (decision_id,),
        ).fetchone()[0]
        versions = current_versions(connection)
        finalize_args = (
            ids["document"],
            document_updated_at,
            json.dumps(versions),
            decision_updated_at,
            uuid.uuid4(),
        )
        assert connection.execute(
            """
            SELECT health_compass.app_finalize_document_ocr_review(
              %s, %s, %s::jsonb, %s, %s, 'review-test'
            )
            """,
            finalize_args,
        ).fetchone() == (True,)

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        assert connection.execute(
            """
            SELECT health_compass.app_finalize_document_ocr_review(
              %s, %s, %s::jsonb, %s, %s, 'review-test-retry'
            )
            """,
            (
                ids["document"],
                document_updated_at,
                json.dumps(versions),
                decision_updated_at,
                uuid.uuid4(),
            ),
        ).fetchone() == (True,)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            "SELECT ocr_status FROM health_compass.profile_documents WHERE id = %s",
            (ids["document"],),
        ).fetchone() == ("reviewed",)
        run = connection.execute(
            """
            SELECT review_status, review_finalized_at IS NOT NULL,
                   review_patient_decision_id
            FROM health_compass.document_ocr_runs WHERE id = %s
            """,
            (ids["ocr_run"],),
        ).fetchone()
        assert run == ("finalized", True, decision_id)
        actions = connection.execute(
            """
            SELECT action, changed_fields FROM health_compass.profile_audit_events
            WHERE profile_id = %s
              AND action IN (
                'document.ocr_candidate_reviewed',
                'document.ocr_patient_decision',
                'document.ocr_review_finalized'
              )
            ORDER BY occurred_at, id
            """,
            (ids["profile"],),
        ).fetchall()
        assert len(actions) == 6
        assert all(changed_fields == {} for _, changed_fields in actions)
        clinical_count = connection.execute(
            """
            SELECT
              (SELECT count(*) FROM health_compass.profile_conditions WHERE profile_id = %s)
              + (SELECT count(*) FROM health_compass.profile_allergies WHERE profile_id = %s)
              + (SELECT count(*) FROM health_compass.profile_medications WHERE profile_id = %s)
              + (SELECT count(*) FROM health_compass.profile_supplements WHERE profile_id = %s)
              + (SELECT count(*) FROM health_compass.body_measurements WHERE profile_id = %s)
            """,
            (ids["profile"],) * 5,
        ).fetchone()[0]
        assert clinical_count == 0


def test_revoked_consent_blocks_review(review_fixture: dict[str, object]) -> None:
    ids = review_fixture
    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "UPDATE health_compass.user_consents SET revoked_at = now() WHERE id = %s",
            (ids["consent"],),
        )
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        candidate = _candidate_state(connection, ids["candidate_one"])
        with pytest.raises(psycopg.DatabaseError) as revoked:
            connection.execute(
                """
                SELECT health_compass.app_review_document_ocr_candidate(
                  %s, 'accept', NULL, NULL, %s, %s, 'review-test'
                )
                """,
                (ids["candidate_one"], candidate[2], uuid.uuid4()),
            ).fetchone()
        assert revoked.value.sqlstate == "HC409"


def test_review_functions_and_table_privileges_are_restricted() -> None:
    signatures = (
        "health_compass.app_review_document_ocr_candidate("
        "uuid,text,text,text,timestamp with time zone,uuid,text)",
        "health_compass.app_set_document_ocr_patient_decision("
        "uuid,uuid,text,text,timestamp with time zone,timestamp with time zone,uuid,text)",
        "health_compass.app_finalize_document_ocr_review("
        "uuid,timestamp with time zone,jsonb,timestamp with time zone,uuid,text)",
    )
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        for signature in signatures:
            row = connection.execute(
                """
                SELECT pg_get_userbyid(p.proowner), p.prosecdef, p.proconfig,
                       has_function_privilege('public', p.oid, 'EXECUTE'),
                       has_function_privilege('health_compass_app', p.oid, 'EXECUTE')
                FROM pg_proc p WHERE p.oid = %s::regprocedure
                """,
                (signature,),
            ).fetchone()
            assert row[0] == "health_compass_rls_definer"
            assert row[1] is True
            assert "search_path=\"\"" in (row[2] or []) or "search_path=" in (row[2] or [])
            assert "row_security=off" in (row[2] or [])
            assert row[3] is False
            assert row[4] is True

        direct_mutations = connection.execute(
            """
            SELECT table_name, privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee = 'health_compass_app'
              AND table_schema = 'health_compass'
              AND table_name IN (
                'document_ocr_candidates',
                'document_ocr_patient_decisions',
                'document_ocr_runs'
              )
              AND privilege_type IN ('INSERT','UPDATE','DELETE')
            """
        ).fetchall()
        assert direct_mutations == []
        rls = connection.execute(
            """
            SELECT relrowsecurity, relforcerowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'health_compass'
              AND c.relname = 'document_ocr_patient_decisions'
            """
        ).fetchone()
        assert rls == (True, True)
