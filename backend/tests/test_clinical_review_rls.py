"""PostgreSQL RLS tests for explicit Clinical Context review state."""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"
APP_ENV = "TEST_DATABASE_URL"

pytestmark = pytest.mark.integration


def _sync_url(env_name: str) -> str:
    url = os.environ.get(env_name, "").strip()
    if not url:
        pytest.skip(f"{env_name} is not configured")
    return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _set_user(connection: psycopg.Connection, user_id: uuid.UUID) -> None:
    connection.execute(
        "SELECT set_config('app.current_user_id', %s, true)",
        (str(user_id),),
    )


def test_review_state_obeys_profile_permissions_and_has_no_delete_grant() -> None:
    owner = uuid.uuid4()
    viewer = uuid.uuid4()
    outsider = uuid.uuid4()
    workspace = uuid.uuid4()
    profile = uuid.uuid4()
    review = uuid.uuid4()

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        for user_id, name in ((owner, "owner"), (viewer, "viewer"), (outsider, "outsider")):
            connection.execute(
                """
                INSERT INTO health_compass.users (id, email, display_name, status)
                VALUES (%s, %s, %s, 'active')
                """,
                (user_id, f"review-{name}-{user_id}@example.test", name),
            )
        connection.execute(
            """
            INSERT INTO health_compass.workspaces (id, name, slug, created_by_user_id)
            VALUES (%s, 'Review RLS test', %s, %s)
            """,
            (workspace, f"review-{workspace}", owner),
        )
        connection.execute(
            """
            INSERT INTO health_compass.workspace_members (id, workspace_id, user_id, role)
            VALUES (%s, %s, %s, 'owner')
            """,
            (uuid.uuid4(), workspace, owner),
        )
        connection.execute(
            """
            INSERT INTO health_compass.health_profiles
              (id, workspace_id, owner_user_id, display_name)
            VALUES (%s, %s, %s, 'Review profile')
            """,
            (profile, workspace, owner),
        )
        connection.execute(
            """
            INSERT INTO health_compass.profile_permissions
              (id, profile_id, user_id, permission, granted_by_user_id)
            VALUES (%s, %s, %s, 'owner', %s),
                   (%s, %s, %s, 'view', %s)
            """,
            (
                uuid.uuid4(), profile, owner, owner,
                uuid.uuid4(), profile, viewer, owner,
            ),
        )

    try:
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, owner)
            connection.execute(
                """
                INSERT INTO health_compass.profile_clinical_reviews (
                  id, profile_id, section, confirmed_empty, reviewed_by_user_id
                ) VALUES (%s, %s, 'allergies', true, %s)
                """,
                (review, profile, owner),
            )

        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, viewer)
            row = connection.execute(
                """
                SELECT section, confirmed_empty
                FROM health_compass.profile_clinical_reviews
                WHERE id = %s
                """,
                (review,),
            ).fetchone()
            assert row == ("allergies", True)
            result = connection.execute(
                """
                UPDATE health_compass.profile_clinical_reviews
                SET confirmed_empty = false, updated_at = now()
                WHERE id = %s
                """,
                (review,),
            )
            assert result.rowcount == 0

        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, outsider)
            assert connection.execute(
                "SELECT id FROM health_compass.profile_clinical_reviews WHERE id = %s",
                (review,),
            ).fetchone() is None

        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, owner)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(
                    "DELETE FROM health_compass.profile_clinical_reviews WHERE id = %s",
                    (review,),
                )
    finally:
        with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
            connection.execute(
                "DELETE FROM health_compass.profile_clinical_reviews WHERE profile_id = %s",
                (profile,),
            )
            connection.execute(
                "DELETE FROM health_compass.profile_permissions WHERE profile_id = %s",
                (profile,),
            )
            connection.execute(
                "DELETE FROM health_compass.health_profiles WHERE id = %s",
                (profile,),
            )
            connection.execute(
                "DELETE FROM health_compass.workspace_members WHERE workspace_id = %s",
                (workspace,),
            )
            connection.execute(
                "DELETE FROM health_compass.workspaces WHERE id = %s",
                (workspace,),
            )
            connection.execute(
                "DELETE FROM health_compass.users WHERE id = ANY(%s)",
                ([owner, viewer, outsider],),
            )
