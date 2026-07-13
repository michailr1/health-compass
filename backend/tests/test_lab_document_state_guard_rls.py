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


def test_document_guard_is_definer_owned_and_not_worker_callable(
    lab_fixture: dict[str, object],
) -> None:
    del lab_fixture
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        row = connection.execute(
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
        assert row == (
            "health_compass_rls_definer",
            True,
            True,
            True,
            False,
            True,
        )
        for worker in (
            "health_compass_worker",
            "health_compass_renderer",
            "health_compass_reconciler",
            "health_compass_ocr_worker",
        ):
            assert connection.execute(
                "SELECT has_function_privilege(%s, %s, 'EXECUTE')",
                (worker, GUARD_SIGNATURE),
            ).fetchone() == (False,)
