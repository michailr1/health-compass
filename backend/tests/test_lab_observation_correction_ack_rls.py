"""Fresh acknowledgement tests for HC-017 E3 Lab corrections."""

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
from tests.test_lab_observation_lifecycle_rls import _correct
from tests.test_lab_observations_rls import _confirm

pytest_plugins = ("tests.test_lab_observation_drafts_rls",)
pytestmark = pytest.mark.integration


def test_not_present_correction_requires_fresh_profile_assignment_ack(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        decision_updated_at = connection.execute(
            """
            UPDATE health_compass.document_ocr_patient_decisions
            SET decision='not_present', updated_at=clock_timestamp()
            WHERE id=%s
            RETURNING updated_at
            """,
            (ids["patient_decision"],),
        ).fetchone()[0]
        connection.execute(
            """
            UPDATE health_compass.document_ocr_runs
            SET review_patient_decision_updated_at=%s
            WHERE id=%s
            """,
            (decision_updated_at, ids["ocr_run"]),
        )

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        draft = _create_ready_draft(connection, ids)
        original_id = uuid.uuid4()
        assert (
            _confirm(
                connection,
                observation_id=original_id,
                draft_id=draft[0],
                idempotency_key=f"confirm:{uuid.uuid4()}",
                draft_updated_at=draft[1],
                document_updated_at=draft[2],
                finalized_at=draft[3],
                decision_updated_at=draft[4],
                not_present_ack=True,
            )
            == original_id
        )

    rejected_replacement = uuid.uuid4()
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        with pytest.raises(psycopg.DatabaseError) as denied:
            _correct(
                connection,
                replacement_id=rejected_replacement,
                original_id=original_id,
                idempotency_key=f"correct:{uuid.uuid4()}",
                acknowledgements=(True, True, True, True, True, False),
            )
        assert denied.value.sqlstate == "HC422"

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            "SELECT count(*) FROM health_compass.lab_observations WHERE id=%s",
            (rejected_replacement,),
        ).fetchone() == (0,)
        assert connection.execute(
            """
            SELECT status, lifecycle_version, superseded_by_observation_id
            FROM health_compass.lab_observations WHERE id=%s
            """,
            (original_id,),
        ).fetchone() == ("active", 1, None)

    accepted_replacement = uuid.uuid4()
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        assert (
            _correct(
                connection,
                replacement_id=accepted_replacement,
                original_id=original_id,
                idempotency_key=f"correct:{uuid.uuid4()}",
                acknowledgements=(True, True, True, True, True, True),
            )
            == accepted_replacement
        )

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            """
            SELECT patient_decision, ack_not_present_assignment,
                   supersedes_observation_id, status
            FROM health_compass.lab_observations WHERE id=%s
            """,
            (accepted_replacement,),
        ).fetchone() == ("not_present", True, original_id, "active")
