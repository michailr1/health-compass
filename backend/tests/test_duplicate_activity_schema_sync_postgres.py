"""HC-015 Slice B: duplicate assessment must know every profile-owned table.

Covers CR-02/FBL-02: accounts whose only activity is a
``profile_clinical_reviews`` or ``profile_intake_decisions`` row must never be
classified as empty, absorption must be blocked as a controlled conflict, and
no scenario may surface a foreign-key violation or delete meaningful data.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager

import psycopg
import pytest

ADMIN_DSN = os.getenv("HC_TEST_DATABASE_ADMIN_DSN")
APP_DSN = os.getenv("HC_TEST_DATABASE_APP_DSN")

pytestmark = pytest.mark.integration


def _require_dsn(value: str | None, name: str) -> str:
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def _seed_empty_account(cursor: psycopg.Cursor, *, email: str, offset_minutes: int) -> dict:
    ids = {
        "user": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "profile": uuid.uuid4(),
    }
    cursor.execute(
        """
        INSERT INTO health_compass.users (id, email, display_name, status, created_at, updated_at)
        VALUES (%s, %s, 'Slice B test user', 'active', now() - make_interval(mins => %s), now())
        """,
        (ids["user"], email, offset_minutes),
    )
    cursor.execute(
        """
        INSERT INTO health_compass.workspaces (id, name, slug, created_by_user_id)
        VALUES (%s, 'Slice B workspace', %s, %s)
        """,
        (ids["workspace"], f"slice-b-{ids['workspace']}", ids["user"]),
    )
    cursor.execute(
        """
        INSERT INTO health_compass.workspace_members (id, workspace_id, user_id, role)
        VALUES (%s, %s, %s, 'owner')
        """,
        (uuid.uuid4(), ids["workspace"], ids["user"]),
    )
    cursor.execute(
        """
        INSERT INTO health_compass.health_profiles (id, workspace_id, owner_user_id, display_name)
        VALUES (%s, %s, %s, 'Slice B profile')
        """,
        (ids["profile"], ids["workspace"], ids["user"]),
    )
    cursor.execute(
        """
        INSERT INTO health_compass.profile_permissions
          (id, profile_id, user_id, permission, granted_by_user_id)
        VALUES (%s, %s, %s, 'owner', %s)
        """,
        (uuid.uuid4(), ids["profile"], ids["user"], ids["user"]),
    )
    return ids


def _insert_clinical_review(cursor: psycopg.Cursor, ids: dict) -> uuid.UUID:
    review_id = uuid.uuid4()
    cursor.execute(
        """
        INSERT INTO health_compass.profile_clinical_reviews
          (id, profile_id, section, review_state, confirmed_empty, reviewed_by_user_id)
        VALUES (%s, %s, 'allergies', 'confirmed_none', true, %s)
        """,
        (review_id, ids["profile"], ids["user"]),
    )
    return review_id


def _insert_intake_decision(cursor: psycopg.Cursor, ids: dict) -> uuid.UUID:
    decision_id = uuid.uuid4()
    cursor.execute(
        """
        INSERT INTO health_compass.profile_intake_decisions
          (id, profile_id, prompt_key, context_type, decision, proposed_section,
           decided_by_user_id)
        VALUES (%s, %s, 'slice-b-prompt', 'question', 'defer', 'medications', %s)
        """,
        (decision_id, ids["profile"], ids["user"]),
    )
    return decision_id


def _activity(cursor: psycopg.Cursor, user_id: uuid.UUID) -> dict:
    cursor.execute(
        "SELECT health_compass.app_duplicate_user_activity(%s)",
        (user_id,),
    )
    return cursor.fetchone()[0]


def _cleanup_account(cursor: psycopg.Cursor, ids: dict) -> None:
    cursor.execute(
        "DELETE FROM health_compass.profile_intake_decisions WHERE profile_id = %s",
        (ids["profile"],),
    )
    cursor.execute(
        "DELETE FROM health_compass.profile_clinical_reviews WHERE profile_id = %s",
        (ids["profile"],),
    )
    cursor.execute(
        "DELETE FROM health_compass.profile_permissions WHERE profile_id = %s",
        (ids["profile"],),
    )
    cursor.execute(
        "DELETE FROM health_compass.health_profiles WHERE id = %s",
        (ids["profile"],),
    )
    cursor.execute(
        "DELETE FROM health_compass.workspace_members WHERE workspace_id = %s",
        (ids["workspace"],),
    )
    cursor.execute(
        "DELETE FROM health_compass.workspaces WHERE id = %s",
        (ids["workspace"],),
    )
    cursor.execute(
        "DELETE FROM health_compass.duplicate_resolution_intents "
        "WHERE initiating_user_id = %s OR canonical_user_id = %s OR absorbed_user_id = %s",
        (ids["user"], ids["user"], ids["user"]),
    )
    cursor.execute(
        "DELETE FROM health_compass.user_identities WHERE user_id = %s",
        (ids["user"],),
    )
    cursor.execute("DELETE FROM health_compass.users WHERE id = %s", (ids["user"],))


@contextmanager
def _admin_cursor():
    admin_dsn = _require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN")
    with psycopg.connect(admin_dsn) as connection, connection.cursor() as cursor:
        yield cursor


def test_clinical_review_row_alone_makes_account_non_empty() -> None:
    with _admin_cursor() as cursor:
        ids = _seed_empty_account(
            cursor, email=f"slice-b-review-{uuid.uuid4().hex}@example.test", offset_minutes=2
        )
        try:
            assert _activity(cursor, ids["user"])["is_empty"] is True
            _insert_clinical_review(cursor, ids)
            activity = _activity(cursor, ids["user"])
            assert activity["is_empty"] is False
            assert activity["profile_clinical_reviews"] == 1
            assert activity["profile_intake_decisions"] == 0
        finally:
            _cleanup_account(cursor, ids)


def test_intake_decision_row_alone_makes_account_non_empty() -> None:
    with _admin_cursor() as cursor:
        ids = _seed_empty_account(
            cursor, email=f"slice-b-intake-{uuid.uuid4().hex}@example.test", offset_minutes=2
        )
        try:
            assert _activity(cursor, ids["user"])["is_empty"] is True
            _insert_intake_decision(cursor, ids)
            activity = _activity(cursor, ids["user"])
            assert activity["is_empty"] is False
            assert activity["profile_intake_decisions"] == 1
        finally:
            _cleanup_account(cursor, ids)


def test_review_and_intake_rows_together_make_account_non_empty() -> None:
    with _admin_cursor() as cursor:
        ids = _seed_empty_account(
            cursor, email=f"slice-b-both-{uuid.uuid4().hex}@example.test", offset_minutes=2
        )
        try:
            _insert_clinical_review(cursor, ids)
            _insert_intake_decision(cursor, ids)
            activity = _activity(cursor, ids["user"])
            assert activity["is_empty"] is False
            assert activity["profile_clinical_reviews"] == 1
            assert activity["profile_intake_decisions"] == 1
            assert activity["meaningful_count"] >= 2
        finally:
            _cleanup_account(cursor, ids)


def _seed_verified_email_identity(
    cursor: psycopg.Cursor, ids: dict, *, provider: str, email: str
) -> None:
    subject = email if provider == "email" else f"google-{ids['user'].hex}"
    issuer = "health-compass-email" if provider == "email" else "https://accounts.google.com"
    cursor.execute(
        """
        INSERT INTO health_compass.user_identities
          (id, user_id, provider, subject, issuer, claims, last_seen_at)
        VALUES (%s, %s, %s, %s, %s,
                jsonb_build_object('email', %s::text, 'email_verified', true), now())
        """,
        (uuid.uuid4(), ids["user"], provider, subject, issuer, email),
    )


def test_concurrent_review_row_blocks_absorption_without_fk_violation() -> None:
    """A review row created after the intent must block completion, not 500."""
    app_dsn = _require_dsn(APP_DSN, "HC_TEST_DATABASE_APP_DSN")
    email = f"slice-b-race-{uuid.uuid4().hex}@example.test"
    browser_hash = "b" * 64
    token_hash = uuid.uuid4().hex + uuid.uuid4().hex

    with _admin_cursor() as cursor:
        canonical = _seed_empty_account(cursor, email=email, offset_minutes=3)
        absorbed = _seed_empty_account(cursor, email=email, offset_minutes=1)
        _seed_verified_email_identity(cursor, canonical, provider="google", email=email)
        _seed_verified_email_identity(cursor, absorbed, provider="email", email=email)

    try:
        with psycopg.connect(app_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_user_id', %s, true)",
                (str(canonical["user"]),),
            )
            cursor.execute(
                """
                SELECT health_compass.app_create_duplicate_resolution_intent(
                  %s, %s, now() + interval '15 minutes'
                )
                """,
                (canonical["user"], browser_hash),
            )
            resolution = cursor.fetchone()[0]
            assert resolution["available"] is True, resolution
            intent_id = uuid.UUID(resolution["intent_id"])
            cursor.execute(
                """
                SELECT health_compass.app_issue_duplicate_resolution_email_token(
                  %s, %s, %s, now() + interval '15 minutes'
                )
                """,
                (intent_id, browser_hash, token_hash),
            )
            assert cursor.fetchone()[0] == email

        # Concurrent change between intent creation and confirmation: the
        # to-be-absorbed account gains a clinical review row.
        with _admin_cursor() as cursor:
            review_id = _insert_clinical_review(cursor, absorbed)

        with psycopg.connect(app_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT health_compass.app_complete_duplicate_resolution_email(%s, %s)",
                (token_hash, browser_hash),
            )
            completion = cursor.fetchone()[0]
        assert completion is None

        with _admin_cursor() as cursor:
            cursor.execute(
                "SELECT status FROM health_compass.duplicate_resolution_intents WHERE id = %s",
                (intent_id,),
            )
            assert cursor.fetchone()[0] == "blocked"
            cursor.execute(
                "SELECT count(*) FROM health_compass.users WHERE id = %s",
                (absorbed["user"],),
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                "SELECT count(*) FROM health_compass.profile_clinical_reviews WHERE id = %s",
                (review_id,),
            )
            assert cursor.fetchone()[0] == 1
    finally:
        with _admin_cursor() as cursor:
            _cleanup_account(cursor, absorbed)
            _cleanup_account(cursor, canonical)


def test_intake_only_duplicate_candidate_is_never_absorbed() -> None:
    """When the candidate holds only an intake row, it becomes canonical."""
    app_dsn = _require_dsn(APP_DSN, "HC_TEST_DATABASE_APP_DSN")
    email = f"slice-b-candidate-{uuid.uuid4().hex}@example.test"
    browser_hash = "c" * 64

    with _admin_cursor() as cursor:
        actor = _seed_empty_account(cursor, email=email, offset_minutes=3)
        candidate = _seed_empty_account(cursor, email=email, offset_minutes=1)
        _seed_verified_email_identity(cursor, actor, provider="google", email=email)
        _seed_verified_email_identity(cursor, candidate, provider="email", email=email)
        _insert_intake_decision(cursor, candidate)

    try:
        with psycopg.connect(app_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_user_id', %s, true)",
                (str(actor["user"]),),
            )
            cursor.execute(
                """
                SELECT health_compass.app_create_duplicate_resolution_intent(
                  %s, %s, now() + interval '15 minutes'
                )
                """,
                (actor["user"], browser_hash),
            )
            resolution = cursor.fetchone()[0]

        # The intake-holding candidate must be canonical, never absorbed.
        if resolution["available"]:
            assert resolution["canonical_is_current"] is False, resolution
        with _admin_cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM health_compass.profile_intake_decisions WHERE profile_id = %s",
                (candidate["profile"],),
            )
            assert cursor.fetchone()[0] == 1
    finally:
        with _admin_cursor() as cursor:
            _cleanup_account(cursor, candidate)
            _cleanup_account(cursor, actor)


def test_definer_role_can_read_new_tables() -> None:
    """The 0046 grants must survive the migration cycle."""
    with _admin_cursor() as cursor:
        for table in ("profile_clinical_reviews", "profile_intake_decisions"):
            cursor.execute(
                "SELECT has_table_privilege('health_compass_rls_definer', "
                "'health_compass.' || %s, 'SELECT')",
                (table,),
            )
            assert cursor.fetchone()[0] is True, table
