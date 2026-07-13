"""Security tests for the HC-017 E3 document-state read guard."""

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
from tests.test_lab_observations_rls import _confirm

pytest_plugins = ("tests.test_lab_observation_drafts_rls",)
pytestmark = pytest.mark.integration

GUARD_SIGNATURE = "health_compass.app_lab_document_available(uuid,uuid)"
TRIGGER_SIGNATURE = "health_compass.app_guard_document_lab_erasure_transition()"
DOCUMENT_ERASURE_SIGNATURE = (
    "health_compass.app_request_document_lab_erasure("
    "uuid,timestamp with time zone,boolean,uuid,text)"
)


def _create_confirmed(
    connection: psycopg.Connection,
    ids: dict[str, object],
) -> uuid.UUID:
    draft = _create_ready_draft(connection, ids)
    observation_id = uuid.uuid4()
    assert (
        _confirm(
            connection,
            observation_id=observation_id,
            draft_id=draft[0],
            idempotency_key=f"confirm:{uuid.uuid4()}",
            draft_updated_at=draft[1],
            document_updated_at=draft[2],
            finalized_at=draft[3],
            decision_updated_at=draft[4],
        )
        == observation_id
    )
    return observation_id


def test_deletion_pending_document_hides_lab_rows_even_outside_e3_erasure(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        observation_id = _create_confirmed(connection, ids)

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            """
            UPDATE health_compass.profile_documents
            SET status='deletion_pending',
                deletion_requested_at=clock_timestamp(),
                updated_at=clock_timestamp()
            WHERE id=%s
            """,
            (ids["document"],),
        )

    for role in ("owner", "editor", "viewer", "analyzer", "outsider"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ids[role])
            assert connection.execute(
                "SELECT count(*) FROM health_compass.lab_observations WHERE id=%s",
                (observation_id,),
            ).fetchone() == (0,), role
            assert connection.execute(
                "SELECT count(*) FROM health_compass.lab_observation_sources "
                "WHERE observation_id=%s",
                (observation_id,),
            ).fetchone() == (0,), role

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observations WHERE id=%s",
            (observation_id,),
        ).fetchone() == (1,)


def test_document_erasure_returns_hc409_while_lab_row_is_locked(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as setup_connection:
        observation_id = _create_confirmed(setup_connection, ids)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as lock_connection:
        document_updated_at = lock_connection.execute(
            "SELECT updated_at FROM health_compass.profile_documents WHERE id=%s",
            (ids["document"],),
        ).fetchone()[0]
        assert lock_connection.execute(
            "SELECT id FROM health_compass.lab_observations WHERE id=%s FOR UPDATE",
            (observation_id,),
        ).fetchone() == (observation_id,)

        with psycopg.connect(_sync_url(APP_ENV)) as erase_connection:
            _set_user(erase_connection, ids["owner"])
            with pytest.raises(psycopg.DatabaseError) as busy:
                erase_connection.execute(
                    """
                    SELECT health_compass.app_request_document_lab_erasure(
                      %s,%s,true,%s,'document-lock-test'
                    )
                    """,
                    (ids["document"], document_updated_at, uuid.uuid4()),
                ).fetchone()
            assert busy.value.sqlstate == "HC409"

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            """
            SELECT status, deletion_requested_at, erased_at
            FROM health_compass.profile_documents WHERE id=%s
            """,
            (ids["document"],),
        ).fetchone() == ("accepted", None, None)
        assert connection.execute(
            "SELECT status, lifecycle_version "
            "FROM health_compass.lab_observations WHERE id=%s",
            (observation_id,),
        ).fetchone() == ("active", 1)


def test_document_guards_have_exact_ownership_configuration_and_grants(
    lab_fixture: dict[str, object],
) -> None:
    del lab_fixture
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        guard = connection.execute(
            """
            SELECT r.rolname, p.prosecdef,
                   EXISTS (
                     SELECT 1 FROM unnest(p.proconfig) AS config
                     WHERE config ~ '^search_path=(""|)$'
                   ),
                   p.proconfig @> ARRAY['row_security=off'],
                   has_function_privilege('public', %s::regprocedure, 'EXECUTE'),
                   has_function_privilege('health_compass_app', %s::regprocedure, 'EXECUTE')
            FROM pg_proc p
            JOIN pg_roles r ON r.oid=p.proowner
            WHERE p.oid=%s::regprocedure
            """,
            (GUARD_SIGNATURE, GUARD_SIGNATURE, GUARD_SIGNATURE),
        ).fetchone()
        assert guard == (
            "health_compass_rls_definer",
            True,
            True,
            True,
            False,
            True,
        )

        trigger_function = connection.execute(
            """
            SELECT r.rolname, p.prosecdef,
                   EXISTS (
                     SELECT 1 FROM unnest(p.proconfig) AS config
                     WHERE config ~ '^search_path=(""|)$'
                   ),
                   p.proconfig @> ARRAY['row_security=off'],
                   has_function_privilege('public', %s::regprocedure, 'EXECUTE'),
                   has_function_privilege('health_compass_app', %s::regprocedure, 'EXECUTE')
            FROM pg_proc p
            JOIN pg_roles r ON r.oid=p.proowner
            WHERE p.oid=%s::regprocedure
            """,
            (TRIGGER_SIGNATURE, TRIGGER_SIGNATURE, TRIGGER_SIGNATURE),
        ).fetchone()
        assert trigger_function == (
            "health_compass_rls_definer",
            True,
            True,
            True,
            False,
            False,
        )
        assert connection.execute(
            """
            SELECT count(*)
            FROM pg_trigger t
            JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='health_compass'
              AND c.relname='profile_documents'
              AND t.tgname='trg_profile_documents_guard_lab_erasure'
              AND NOT t.tgisinternal
              AND t.tgenabled='O'
            """
        ).fetchone() == (1,)

        for worker in (
            "health_compass_worker",
            "health_compass_renderer",
            "health_compass_reconciler",
            "health_compass_ocr_worker",
        ):
            for signature in (
                GUARD_SIGNATURE,
                TRIGGER_SIGNATURE,
                DOCUMENT_ERASURE_SIGNATURE,
            ):
                assert connection.execute(
                    "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
                    (worker, signature),
                ).fetchone() == (False,)
