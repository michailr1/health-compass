"""PostgreSQL acceptance tests for HC-017 E2 confirmed observations."""

from __future__ import annotations

import uuid

import psycopg
import pytest

from tests.test_lab_observation_drafts_rls import (
    ADMIN_ENV,
    APP_ENV,
    _create_ready_draft,
    _set_user,
    _sync_url,
)

pytest_plugins = ("tests.test_lab_observation_drafts_rls",)
pytestmark = pytest.mark.integration

CONFIRM_SIGNATURE = (
    "health_compass.app_confirm_lab_observation("
    "uuid,uuid,text,timestamp with time zone,timestamp with time zone,"
    "timestamp with time zone,timestamp with time zone,"
    "boolean,boolean,boolean,boolean,boolean,boolean,uuid,text)"
)


def _confirm(
    connection: psycopg.Connection,
    *,
    observation_id: uuid.UUID,
    draft_id: uuid.UUID,
    idempotency_key: str,
    draft_updated_at: object,
    document_updated_at: object,
    finalized_at: object,
    decision_updated_at: object,
    not_present_ack: bool = False,
) -> uuid.UUID:
    return connection.execute(
        """
        SELECT health_compass.app_confirm_lab_observation(
          %s,%s,%s,%s,%s,%s,%s,
          true,true,true,true,true,%s,%s,'lab-confirmation-test'
        )
        """,
        (
            observation_id,
            draft_id,
            idempotency_key,
            draft_updated_at,
            document_updated_at,
            finalized_at,
            decision_updated_at,
            not_present_ack,
            uuid.uuid4(),
        ),
    ).fetchone()[0]


def test_confirmation_is_atomic_immutable_and_visible_only_when_confirmed(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    observation_id = uuid.uuid4()
    idempotency_key = f"confirm:{uuid.uuid4()}"

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        (
            draft_id,
            draft_updated_at,
            document_updated_at,
            finalized_at,
            decision_updated_at,
        ) = _create_ready_draft(connection, ids)
        confirmed = _confirm(
            connection,
            observation_id=observation_id,
            draft_id=draft_id,
            idempotency_key=idempotency_key,
            draft_updated_at=draft_updated_at,
            document_updated_at=document_updated_at,
            finalized_at=finalized_at,
            decision_updated_at=decision_updated_at,
        )
        assert confirmed == observation_id

        replay = _confirm(
            connection,
            observation_id=uuid.uuid4(),
            draft_id=draft_id,
            idempotency_key=idempotency_key,
            draft_updated_at=draft_updated_at,
            document_updated_at=document_updated_at,
            finalized_at=finalized_at,
            decision_updated_at=decision_updated_at,
        )
        assert replay == observation_id

        different_key_replay = _confirm(
            connection,
            observation_id=uuid.uuid4(),
            draft_id=draft_id,
            idempotency_key=f"confirm:{uuid.uuid4()}",
            draft_updated_at=draft_updated_at,
            document_updated_at=document_updated_at,
            finalized_at=finalized_at,
            decision_updated_at=decision_updated_at,
        )
        assert different_key_replay == observation_id

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                """
                UPDATE health_compass.lab_observations
                SET source_value_text = 'tampered'
                WHERE id = %s
                """,
                (observation_id,),
            )

    for role, expected in (
        ("owner", 1),
        ("editor", 1),
        ("viewer", 1),
        ("analyzer", 1),
        ("outsider", 0),
    ):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ids[role])
            count = connection.execute(
                """
                SELECT count(*) FROM health_compass.lab_observations
                WHERE id = %s
                """,
                (observation_id,),
            ).fetchone()[0]
            assert count == expected, role
            source_count = connection.execute(
                """
                SELECT count(*) FROM health_compass.lab_observation_sources
                WHERE observation_id = %s
                """,
                (observation_id,),
            ).fetchone()[0]
            assert source_count == expected * 2, role

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observations WHERE id=%s",
            (observation_id,),
        ).fetchone() == (0,)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        draft_row = connection.execute(
            """
            SELECT status, confirmed_observation_id, confirmed_at
            FROM health_compass.lab_observation_drafts
            WHERE id = %s
            """,
            (draft_id,),
        ).fetchone()
        assert draft_row[0] == "confirmed"
        assert draft_row[1] == observation_id
        assert draft_row[2] is not None

        observation = connection.execute(
            """
            SELECT source_analyte_text, source_value_text, source_unit_text,
                   patient_decision, ack_source, ack_unit_range,
                   ack_observed_at, ack_profile, ack_structured_record
            FROM health_compass.lab_observations
            WHERE id = %s
            """,
            (observation_id,),
        ).fetchone()
        assert observation == (
            "Глюкоза",
            "5.4",
            "ммоль/л",
            "match",
            True,
            True,
            True,
            True,
            True,
        )
        snapshots = connection.execute(
            """
            SELECT source_role, reviewed_text_snapshot
            FROM health_compass.lab_observation_sources
            WHERE observation_id = %s
            ORDER BY source_role
            """,
            (observation_id,),
        ).fetchall()
        assert snapshots == [
            ("analyte", "Глюкоза"),
            ("value", "5.4 ммоль/л"),
        ]
        audit = connection.execute(
            """
            SELECT action, changed_fields
            FROM health_compass.profile_audit_events
            WHERE entity_id = %s
            """,
            (observation_id,),
        ).fetchone()
        assert audit == ("lab.observation_confirmed", {})


def test_confirmation_requires_edit_access_current_sources_and_consent(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        (
            draft_id,
            draft_updated_at,
            document_updated_at,
            finalized_at,
            decision_updated_at,
        ) = _create_ready_draft(connection, ids)

    for role in ("viewer", "analyzer", "outsider"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ids[role])
            with pytest.raises(psycopg.DatabaseError) as denied:
                _confirm(
                    connection,
                    observation_id=uuid.uuid4(),
                    draft_id=draft_id,
                    idempotency_key=f"confirm:{uuid.uuid4()}",
                    draft_updated_at=draft_updated_at,
                    document_updated_at=document_updated_at,
                    finalized_at=finalized_at,
                    decision_updated_at=decision_updated_at,
                )
            assert denied.value.sqlstate == "HC404"

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            """
            UPDATE health_compass.document_ocr_candidates
            SET reviewed_text = 'изменено', updated_at = clock_timestamp()
            WHERE id = %s
            """,
            (ids["candidate_value"],),
        )
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        with pytest.raises(psycopg.DatabaseError) as stale:
            _confirm(
                connection,
                observation_id=uuid.uuid4(),
                draft_id=draft_id,
                idempotency_key=f"confirm:{uuid.uuid4()}",
                draft_updated_at=draft_updated_at,
                document_updated_at=document_updated_at,
                finalized_at=finalized_at,
                decision_updated_at=decision_updated_at,
            )
        assert stale.value.sqlstate == "HC409"


def test_not_present_requires_additional_assignment_acknowledgement(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        decision_updated_at = connection.execute(
            """
            UPDATE health_compass.document_ocr_patient_decisions
            SET decision = 'not_present', updated_at = clock_timestamp()
            WHERE id = %s
            RETURNING updated_at
            """,
            (ids["patient_decision"],),
        ).fetchone()[0]
        connection.execute(
            """
            UPDATE health_compass.document_ocr_runs
            SET review_patient_decision_updated_at = %s
            WHERE id = %s
            """,
            (decision_updated_at, ids["ocr_run"]),
        )

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        (
            draft_id,
            draft_updated_at,
            document_updated_at,
            finalized_at,
            decision_updated_at,
        ) = _create_ready_draft(connection, ids)
        with pytest.raises(psycopg.DatabaseError) as missing_ack:
            _confirm(
                connection,
                observation_id=uuid.uuid4(),
                draft_id=draft_id,
                idempotency_key=f"confirm:{uuid.uuid4()}",
                draft_updated_at=draft_updated_at,
                document_updated_at=document_updated_at,
                finalized_at=finalized_at,
                decision_updated_at=decision_updated_at,
            )
        assert missing_ack.value.sqlstate == "HC422"

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["editor"])
        observation_id = _confirm(
            connection,
            observation_id=uuid.uuid4(),
            draft_id=draft_id,
            idempotency_key=f"confirm:{uuid.uuid4()}",
            draft_updated_at=draft_updated_at,
            document_updated_at=document_updated_at,
            finalized_at=finalized_at,
            decision_updated_at=decision_updated_at,
            not_present_ack=True,
        )
        assert observation_id is not None


def test_revoked_consent_blocks_confirmation_without_partial_rows(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        (
            draft_id,
            draft_updated_at,
            document_updated_at,
            finalized_at,
            decision_updated_at,
        ) = _create_ready_draft(connection, ids)

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "UPDATE health_compass.user_consents SET revoked_at=now() WHERE id=%s",
            (ids["consent"],),
        )

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        with pytest.raises(psycopg.DatabaseError) as denied:
            _confirm(
                connection,
                observation_id=uuid.uuid4(),
                draft_id=draft_id,
                idempotency_key=f"confirm:{uuid.uuid4()}",
                draft_updated_at=draft_updated_at,
                document_updated_at=document_updated_at,
                finalized_at=finalized_at,
                decision_updated_at=decision_updated_at,
            )
        assert denied.value.sqlstate == "HC409"

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observations "
            "WHERE source_draft_id=%s",
            (draft_id,),
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT status FROM health_compass.lab_observation_drafts WHERE id=%s",
            (draft_id,),
        ).fetchone() == ("ready",)


def test_same_idempotency_key_cannot_confirm_a_different_draft(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    key = f"confirm:{uuid.uuid4()}"
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        first = _create_ready_draft(connection, ids)
        second = _create_ready_draft(connection, ids)
        _confirm(
            connection,
            observation_id=uuid.uuid4(),
            draft_id=first[0],
            idempotency_key=key,
            draft_updated_at=first[1],
            document_updated_at=first[2],
            finalized_at=first[3],
            decision_updated_at=first[4],
        )
        with pytest.raises(psycopg.DatabaseError) as conflict:
            _confirm(
                connection,
                observation_id=uuid.uuid4(),
                draft_id=second[0],
                idempotency_key=key,
                draft_updated_at=second[1],
                document_updated_at=second[2],
                finalized_at=second[3],
                decision_updated_at=second[4],
            )
        assert conflict.value.sqlstate == "HC409"


def test_confirmation_security_catalog(lab_fixture: dict[str, object]) -> None:
    del lab_fixture
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        rls = connection.execute(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'health_compass'
              AND relname IN (
                'lab_observations',
                'lab_observation_sources'
              )
            ORDER BY relname
            """
        ).fetchall()
        assert len(rls) == 2
        assert all(row[1] and row[2] for row in rls)

        assert connection.execute(
            """
            SELECT has_function_privilege(
              'health_compass_app', %s, 'EXECUTE'
            )
            """,
            (CONFIRM_SIGNATURE,),
        ).fetchone() == (True,)
        assert connection.execute(
            "SELECT has_function_privilege('public', %s, 'EXECUTE')",
            (CONFIRM_SIGNATURE,),
        ).fetchone() == (False,)

        for worker in (
            "health_compass_worker",
            "health_compass_renderer",
            "health_compass_reconciler",
            "health_compass_ocr_worker",
        ):
            assert connection.execute(
                "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
                (worker, CONFIRM_SIGNATURE),
            ).fetchone() == (False,)

        mutations = connection.execute(
            """
            SELECT table_name, privilege_type
            FROM information_schema.role_table_grants
            WHERE grantee = 'health_compass_app'
              AND table_schema = 'health_compass'
              AND table_name IN (
                'lab_observations',
                'lab_observation_sources'
              )
              AND privilege_type IN ('INSERT','UPDATE','DELETE')
            """
        ).fetchall()
        assert mutations == []
