"""Concurrency and stale-version tests for HC-017 E3 lifecycle mutations."""

from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor

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


def _payload(value: str) -> str:
    payload = _draft_payload()
    payload["source_value_text"] = value
    payload["numeric_value"] = value
    return json.dumps(payload)


def _correct(
    ids: dict[str, object],
    observation_id: uuid.UUID,
    value: str,
) -> tuple[str, uuid.UUID | str]:
    replacement_id = uuid.uuid4()
    try:
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ids["owner"])
            result = connection.execute(
                """
                SELECT health_compass.app_correct_lab_observation(
                  %s,%s,1,%s,%s,%s::jsonb,
                  true,true,true,true,true,false,%s,
                  'concurrent-correction-test'
                )
                """,
                (
                    replacement_id,
                    observation_id,
                    f"correct:{uuid.uuid4()}",
                    f"Исправлено значение на {value}",
                    _payload(value),
                    uuid.uuid4(),
                ),
            ).fetchone()[0]
            return ("ok", result)
    except psycopg.DatabaseError as exc:
        return ("error", exc.sqlstate or "")


def _void(
    ids: dict[str, object],
    observation_id: uuid.UUID,
) -> tuple[str, bool | str]:
    try:
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, ids["owner"])
            result = connection.execute(
                """
                SELECT health_compass.app_void_lab_observation(
                  %s,1,%s,%s,'concurrent-void-test'
                )
                """,
                (
                    observation_id,
                    "Запись больше не должна считаться актуальной",
                    uuid.uuid4(),
                ),
            ).fetchone()[0]
            return ("ok", result)
    except psycopg.DatabaseError as exc:
        return ("error", exc.sqlstate or "")


def test_two_concurrent_corrections_create_exactly_one_successor(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        observation_id = _create_confirmed(connection, ids)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda value: _correct(ids, observation_id, value),
                ("5.6", "5.8"),
            )
        )

    assert sum(result[0] == "ok" for result in results) == 1
    assert sum(result == ("error", "HC409") for result in results) == 1

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        original = connection.execute(
            """
            SELECT status, lifecycle_version, superseded_by_observation_id
            FROM health_compass.lab_observations WHERE id=%s
            """,
            (observation_id,),
        ).fetchone()
        assert original[0:2] == ("superseded", 2)
        assert original[2] is not None
        successors = connection.execute(
            """
            SELECT id, status, supersedes_observation_id
            FROM health_compass.lab_observations
            WHERE supersedes_observation_id=%s
            """,
            (observation_id,),
        ).fetchall()
        assert successors == [(original[2], "active", observation_id)]


def test_sequential_correction_writes_one_content_free_audit_event(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        observation_id = _create_confirmed(connection, ids)

    result = _correct(ids, observation_id, "5.6")
    assert result[0] == "ok"
    replacement_id = result[1]
    assert isinstance(replacement_id, uuid.UUID)

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            """
            SELECT action, changed_fields
            FROM health_compass.profile_audit_events
            WHERE entity_type='lab_observation' AND entity_id=%s
            """,
            (replacement_id,),
        ).fetchall() == [("lab.observation.corrected", {})]


def test_concurrent_correction_and_void_have_one_atomic_winner(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        observation_id = _create_confirmed(connection, ids)

    with ThreadPoolExecutor(max_workers=2) as pool:
        correction_future = pool.submit(_correct, ids, observation_id, "5.7")
        void_future = pool.submit(_void, ids, observation_id)
        results = [correction_future.result(), void_future.result()]

    assert sum(result[0] == "ok" for result in results) == 1
    assert sum(result == ("error", "HC409") for result in results) == 1

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        original = connection.execute(
            """
            SELECT status, lifecycle_version, superseded_by_observation_id,
                   voided_at IS NOT NULL
            FROM health_compass.lab_observations WHERE id=%s
            """,
            (observation_id,),
        ).fetchone()
        assert original[1] == 2
        if original[0] == "superseded":
            assert original[2] is not None
            assert original[3] is False
            assert connection.execute(
                "SELECT count(*) FROM health_compass.lab_observations "
                "WHERE supersedes_observation_id=%s AND status='active'",
                (observation_id,),
            ).fetchone() == (1,)
        else:
            assert original == ("voided", 2, None, True)
            assert connection.execute(
                "SELECT count(*) FROM health_compass.lab_observations "
                "WHERE supersedes_observation_id=%s",
                (observation_id,),
            ).fetchone() == (0,)


def test_stale_void_and_erase_versions_fail_without_partial_changes(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        observation_id = _create_confirmed(connection, ids)

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        with pytest.raises(psycopg.DatabaseError) as stale_void:
            connection.execute(
                "SELECT health_compass.app_void_lab_observation(%s,2,%s,%s,%s)",
                (
                    observation_id,
                    "Устаревшая версия",
                    uuid.uuid4(),
                    "stale-void-test",
                ),
            ).fetchone()
        assert stale_void.value.sqlstate == "HC409"

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        with pytest.raises(psycopg.DatabaseError) as stale_erase:
            connection.execute(
                "SELECT health_compass.app_erase_lab_observation(%s,2,true,%s,%s)",
                (observation_id, uuid.uuid4(), "stale-erasure-test"),
            ).fetchone()
        assert stale_erase.value.sqlstate == "HC409"

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            """
            SELECT status, lifecycle_version, superseded_by_observation_id,
                   voided_at, void_reason
            FROM health_compass.lab_observations WHERE id=%s
            """,
            (observation_id,),
        ).fetchone() == ("active", 1, None, None, None)
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observation_sources "
            "WHERE observation_id=%s",
            (observation_id,),
        ).fetchone() == (2,)
