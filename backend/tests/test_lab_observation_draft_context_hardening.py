"""Regression tests for E1 context checks after draft creation."""

from __future__ import annotations

import json
import uuid

import psycopg
import pytest

from tests.test_lab_observation_drafts_rls import (
    ADMIN_ENV,
    APP_ENV,
    _context_versions,
    _draft_payload,
    _set_user,
    _sync_url,
)

pytest_plugins = ("tests.test_lab_observation_drafts_rls",)
pytestmark = pytest.mark.integration


def test_revoked_consent_blocks_sources_and_status_after_creation(
    lab_fixture: dict[str, object],
) -> None:
    ids = lab_fixture
    draft_id = uuid.uuid4()

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        document_updated_at, finalized_at, decision_updated_at = _context_versions(
            connection, ids
        )
        assert connection.execute(
            """
            SELECT health_compass.app_create_lab_observation_draft(
              %s,%s,%s,%s,%s,%s::jsonb,%s,'lab-context-hardening'
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
        ).fetchone() == (draft_id,)
        draft_updated_at = connection.execute(
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
        with pytest.raises(psycopg.DatabaseError) as denied_sources:
            connection.execute(
                """
                SELECT health_compass.app_set_lab_draft_sources(
                  %s,%s,%s,%s,%s,%s::jsonb,%s,'lab-context-hardening'
                )
                """,
                (
                    draft_id,
                    draft_updated_at,
                    document_updated_at,
                    finalized_at,
                    decision_updated_at,
                    json.dumps(manifest),
                    uuid.uuid4(),
                ),
            ).fetchone()
        assert denied_sources.value.sqlstate == "HC409"

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, ids["owner"])
        document_updated_at, finalized_at, decision_updated_at = _context_versions(
            connection, ids
        )
        with pytest.raises(psycopg.DatabaseError) as denied_status:
            connection.execute(
                """
                SELECT health_compass.app_set_lab_observation_draft_status(
                  %s,'rejected',%s,%s,%s,%s,%s,'lab-context-hardening'
                )
                """,
                (
                    draft_id,
                    draft_updated_at,
                    document_updated_at,
                    finalized_at,
                    decision_updated_at,
                    uuid.uuid4(),
                ),
            ).fetchone()
        assert denied_status.value.sqlstate == "HC409"
