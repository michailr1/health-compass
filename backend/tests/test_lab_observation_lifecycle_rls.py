"""PostgreSQL security tests for HC-017 E3 observation lifecycle."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import psycopg
import pytest

from tests.test_lab_observation_drafts_rls import (
    ADMIN_ENV,
    APP_ENV,
    _create_ready_draft,
    _draft_payload,
    _set_user,
    _sync_url,
)
from tests.test_lab_observations_rls import _confirm

pytest_plugins = ("tests.test_lab_observation_drafts_rls",)
pytestmark = pytest.mark.integration

VOID_SIGNATURE = (
    "health_compass.app_void_lab_observation(uuid,integer,text,uuid,text)"
)
OLD_CORRECT_SIGNATURE = (
    "health_compass.app_correct_lab_observation("
    "uuid,uuid,integer,text,text,jsonb,uuid,text)"
)
CORRECT_SIGNATURE = (
    "health_compass.app_correct_lab_observation("
    "uuid,uuid,integer,text,text,jsonb,"
    "boolean,boolean,boolean,boolean,boolean,boolean,uuid,text)"
)
ERASE_SIGNATURE = (
    "health_compass.app_erase_lab_observation(uuid,integer,boolean,uuid,text)"
)
DOCUMENT_ERASURE_SIGNATURE = (
    "health_compass.app_request_document_lab_erasure("
    "uuid,timestamp with time zone,boolean,uuid,text)"
)


def _create_confirmed(
    connection: psycopg.Connection,
    ids: dict[str, object],
) -> tuple[uuid.UUID, uuid.UUID]:
    draft = _create_ready_draft(connection, ids)
    observation_id = uuid.uuid4()
    confirmed = _confirm(
        connection,
        observation_id=observation_id,
        draft_id=draft[0],
        idempotency_key=f"confirm:{uuid.uuid4()}",
        draft_updated_at=draft[1],
        document_updated_at=draft[2],
        finalized_at=draft[3],
        decision_updated_at=draft[4],
    )
    assert confirmed == observation_id
    return observation_id, draft[0]


def _corrected_payload(value: str = "5.6") -> dict[str, object]:
    payload = _draft_payload()
    payload["source_value_text"] = value
    payload["numeric_value"] = value
    return payload


def _correct(
    connection: psycopg.Connection,
    *,
    replacement_id: uuid.UUID,
    original_id: uuid.UUID,
    idempotency_key: str,
    payload: dict[str, object] | None = None,
    acknowledgements: tuple[bool, bool, bool, bool, bool, bool] = (
        True,
        True,
        True,
        True,
        True,
        False,
    ),
) -> uuid.UUID:
    return connection.execute(
        """
        SELECT health_compass.app_correct_lab_observation(
          %s,%s,1,%s,%s,%s::jsonb,
          %s,%s,%s,%s,%s,%s,%s,'lab-correction-test'
        )
        """,
        (
            replacement_id,
            original_id,
            idempotency_key,
            "Исправлена опечатка при переносе значения",
            json.dumps(payload or _corrected_payload()),
            *acknowledgements,
            uuid.uuid4(),
        ),
    ).fetchone()[0]


def test_source_snapshots_are_owner_editor_only(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        observation_id, _ = _create_confirmed(connection, ids)

    for role, observation_count, source_count in (
        ("owner", 1, 2),
        ("editor", 1, 2),
        ("viewer", 1, 0),
        ("analyzer", 1, 0),
        ("outsider", 0, 0),
    ):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ids[role])
            assert connection.execute(
                "SELECT count(*) FROM health_compass.lab_observations WHERE id=%s",
                (observation_id,),
            ).fetchone() == (observation_count,)
            assert connection.execute(
                "SELECT count(*) FROM health_compass.lab_observation_sources "
                "WHERE observation_id=%s",
                (observation_id,),
            ).fetchone() == (source_count,)


def test_correction_creates_replacement_with_fresh_acknowledgements(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    correction_key = f"correct:{uuid.uuid4()}"
    replacement_id = uuid.uuid4()

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        original_id, _ = _create_confirmed(connection, ids)
        _set_user(connection, ids["editor"])
        assert _correct(
            connection,
            replacement_id=replacement_id,
            original_id=original_id,
            idempotency_key=correction_key,
        ) == replacement_id
        assert _correct(
            connection,
            replacement_id=uuid.uuid4(),
            original_id=original_id,
            idempotency_key=correction_key,
        ) == replacement_id

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        original = connection.execute(
            """
            SELECT status, source_value_text, numeric_value,
                   superseded_by_observation_id, lifecycle_version
            FROM health_compass.lab_observations WHERE id=%s
            """,
            (original_id,),
        ).fetchone()
        replacement = connection.execute(
            """
            SELECT status, source_draft_id, source_value_text, numeric_value,
                   supersedes_observation_id, correction_reason,
                   lifecycle_version, ack_source, ack_unit_range,
                   ack_observed_at, ack_profile, ack_structured_record,
                   ack_not_present_assignment
            FROM health_compass.lab_observations WHERE id=%s
            """,
            (replacement_id,),
        ).fetchone()
        assert original == (
            "superseded",
            "5.4",
            Decimal("5.400000000000"),
            replacement_id,
            2,
        )
        assert replacement == (
            "active",
            None,
            "5.6",
            Decimal("5.600000000000"),
            original_id,
            "Исправлена опечатка при переносе значения",
            1,
            True,
            True,
            True,
            True,
            True,
            False,
        )
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observation_sources "
            "WHERE observation_id=%s",
            (replacement_id,),
        ).fetchone() == (2,)
        assert connection.execute(
            """
            SELECT action, changed_fields
            FROM health_compass.profile_audit_events
            WHERE entity_type='lab_observation' AND entity_id=%s
            """,
            (replacement_id,),
        ).fetchall() == [("lab.observation.corrected", {})]

    for role, expected_ids in (
        ("owner", {original_id, replacement_id}),
        ("editor", {original_id, replacement_id}),
        ("viewer", {replacement_id}),
        ("analyzer", {replacement_id}),
        ("outsider", set()),
    ):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ids[role])
            visible = {
                row[0]
                for row in connection.execute(
                    "SELECT id FROM health_compass.lab_observations "
                    "WHERE id = ANY(%s)",
                    ([original_id, replacement_id],),
                ).fetchall()
            }
            assert visible == expected_ids, role


def test_correction_rejects_missing_acknowledgement_without_partial_rows(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    replacement_id = uuid.uuid4()
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        original_id, _ = _create_confirmed(connection, ids)

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        with pytest.raises(psycopg.DatabaseError) as denied:
            _correct(
                connection,
                replacement_id=replacement_id,
                original_id=original_id,
                idempotency_key=f"correct:{uuid.uuid4()}",
                acknowledgements=(True, True, True, True, False, False),
            )
        assert denied.value.sqlstate == "HC422"

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observations WHERE id=%s",
            (replacement_id,),
        ).fetchone() == (0,)
        assert connection.execute(
            """
            SELECT status, lifecycle_version, superseded_by_observation_id
            FROM health_compass.lab_observations WHERE id=%s
            """,
            (original_id,),
        ).fetchone() == ("active", 1, None)


def test_void_hides_observation_from_view_and_analyze_without_consent(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        observation_id, _ = _create_confirmed(connection, ids)

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "UPDATE health_compass.user_consents SET revoked_at=now() WHERE id=%s",
            (ids["consent"],),
        )

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["editor"])
        assert connection.execute(
            """
            SELECT health_compass.app_void_lab_observation(
              %s,1,%s,%s,'lab-void-test'
            )
            """,
            (
                observation_id,
                "Результат относится к другому исследованию",
                uuid.uuid4(),
            ),
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
            assert connection.execute(
                "SELECT count(*) FROM health_compass.lab_observations WHERE id=%s",
                (observation_id,),
            ).fetchone() == (expected,)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            """
            SELECT status, lifecycle_version, void_reason
            FROM health_compass.lab_observations WHERE id=%s
            """,
            (observation_id,),
        ).fetchone() == (
            "voided",
            2,
            "Результат относится к другому исследованию",
        )


def test_only_owner_can_erase_complete_chain_after_consent_withdrawal(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    replacement_id = uuid.uuid4()
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        original_id, draft_id = _create_confirmed(connection, ids)
        _set_user(connection, ids["editor"])
        _correct(
            connection,
            replacement_id=replacement_id,
            original_id=original_id,
            idempotency_key=f"correct:{uuid.uuid4()}",
        )

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["editor"])
        with pytest.raises(psycopg.DatabaseError) as denied:
            connection.execute(
                "SELECT health_compass.app_erase_lab_observation(%s,1,true,%s,%s)",
                (replacement_id, uuid.uuid4(), "lab-erasure-test"),
            ).fetchone()
        assert denied.value.sqlstate == "HC404"

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "UPDATE health_compass.user_consents SET revoked_at=now() WHERE id=%s",
            (ids["consent"],),
        )

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        assert connection.execute(
            "SELECT health_compass.app_erase_lab_observation(%s,1,true,%s,%s)",
            (replacement_id, uuid.uuid4(), "lab-erasure-test"),
        ).fetchone() == (2,)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observations "
            "WHERE id = ANY(%s)",
            ([original_id, replacement_id],),
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observation_sources "
            "WHERE observation_id = ANY(%s)",
            ([original_id, replacement_id],),
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observation_drafts WHERE id=%s",
            (draft_id,),
        ).fetchone() == (0,)
        audit_rows = connection.execute(
            """
            SELECT action, changed_fields
            FROM health_compass.profile_audit_events
            WHERE entity_type='lab_observation' AND entity_id=%s
            """,
            (replacement_id,),
        ).fetchall()
        assert audit_rows == [("lab.observation.erased", {})]
        assert "5.4" not in str(audit_rows)
        assert "5.6" not in str(audit_rows)


def test_document_erasure_immediately_removes_all_lab_provenance(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        observation_id, draft_id = _create_confirmed(connection, ids)
        document_updated_at = connection.execute(
            "SELECT updated_at FROM health_compass.profile_documents WHERE id=%s",
            (ids["document"],),
        ).fetchone()[0]

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["editor"])
        with pytest.raises(psycopg.DatabaseError) as denied:
            connection.execute(
                """
                SELECT health_compass.app_request_document_lab_erasure(
                  %s,%s,true,%s,'document-lab-erasure-test'
                )
                """,
                (ids["document"], document_updated_at, uuid.uuid4()),
            ).fetchone()
        assert denied.value.sqlstate == "HC404"

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        assert connection.execute(
            """
            SELECT health_compass.app_request_document_lab_erasure(
              %s,%s,true,%s,'document-lab-erasure-test'
            )
            """,
            (ids["document"], document_updated_at, uuid.uuid4()),
        ).fetchone() == (1,)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            "SELECT status, deletion_requested_at IS NOT NULL "
            "FROM health_compass.profile_documents WHERE id=%s",
            (ids["document"],),
        ).fetchone() == ("deletion_pending", True)
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observations WHERE id=%s",
            (observation_id,),
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observation_drafts WHERE id=%s",
            (draft_id,),
        ).fetchone() == (0,)


def test_e3_functions_are_tightly_owned_and_old_correction_is_revoked(
    lab_fixture: dict[str, object],
) -> None:
    del lab_fixture
    signatures = (
        VOID_SIGNATURE,
        CORRECT_SIGNATURE,
        ERASE_SIGNATURE,
        DOCUMENT_ERASURE_SIGNATURE,
    )
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            "SELECT has_function_privilege('health_compass_app', %s, 'EXECUTE')",
            (OLD_CORRECT_SIGNATURE,),
        ).fetchone() == (False,)

        for signature in signatures:
            row = connection.execute(
                """
                SELECT r.rolname, p.prosecdef,
                       has_function_privilege('public', %s::regprocedure, 'EXECUTE'),
                       has_function_privilege('health_compass_app', %s::regprocedure, 'EXECUTE')
                FROM pg_proc p
                JOIN pg_roles r ON r.oid = p.proowner
                WHERE p.oid = %s::regprocedure
                """,
                (signature, signature, signature),
            ).fetchone()
            assert row == ("health_compass_rls_definer", True, False, True)
            for worker in (
                "health_compass_worker",
                "health_compass_renderer",
                "health_compass_reconciler",
                "health_compass_ocr_worker",
            ):
                assert connection.execute(
                    "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
                    (worker, signature),
                ).fetchone() == (False,)

        assert connection.execute(
            """
            SELECT count(*)
            FROM information_schema.role_table_grants
            WHERE grantee='health_compass_app'
              AND table_schema='health_compass'
              AND table_name IN (
                'lab_observations','lab_observation_sources',
                'lab_observation_drafts','lab_observation_draft_sources'
              )
              AND privilege_type IN ('INSERT','UPDATE','DELETE')
            """
        ).fetchone() == (0,)
