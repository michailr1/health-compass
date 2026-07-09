"""PostgreSQL RLS and HC-026 regression tests for Clinical Context Slice 2."""

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


@pytest.fixture(scope="module")
def clinical_fixture() -> dict[str, uuid.UUID]:
    ids = {
        "owner": uuid.uuid4(),
        "editor": uuid.uuid4(),
        "viewer": uuid.uuid4(),
        "analyzer": uuid.uuid4(),
        "outsider": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "profile": uuid.uuid4(),
        "condition": uuid.uuid4(),
    }

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        for role in ("owner", "editor", "viewer", "analyzer", "outsider"):
            connection.execute(
                """
                INSERT INTO health_compass.users
                  (id, email, display_name, status)
                VALUES (%s, %s, %s, 'active')
                """,
                (ids[role], f"clinical-{role}-{ids[role]}@example.test", role),
            )

        connection.execute(
            """
            INSERT INTO health_compass.workspaces
              (id, name, slug, created_by_user_id)
            VALUES (%s, 'Clinical RLS test', %s, %s)
            """,
            (ids["workspace"], f"clinical-{ids['workspace']}", ids["owner"]),
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
            VALUES (%s, %s, %s, 'Clinical profile')
            """,
            (ids["profile"], ids["workspace"], ids["owner"]),
        )
        connection.execute(
            """
            INSERT INTO health_compass.profile_permissions
              (id, profile_id, user_id, permission, granted_by_user_id)
            VALUES (%s, %s, %s, 'owner', %s)
            """,
            (uuid.uuid4(), ids["profile"], ids["owner"], ids["owner"]),
        )
        for role, permission in (
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

    yield ids

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        for table in (
            "profile_clinical_safety_flags",
            "profile_supplements",
            "profile_medications",
            "profile_allergies",
            "profile_conditions",
        ):
            connection.execute(
                f"DELETE FROM health_compass.{table} WHERE profile_id = %s",
                (ids["profile"],),
            )
        connection.execute(
            "DELETE FROM health_compass.profile_audit_events WHERE profile_id = %s",
            (ids["profile"],),
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


def test_owner_can_insert_and_visible_roles_can_read_without_recursion(
    clinical_fixture: dict[str, uuid.UUID],
) -> None:
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, clinical_fixture["owner"])
        connection.execute(
            """
            INSERT INTO health_compass.profile_conditions (
              id, profile_id, display_name, clinical_status,
              source_type, confirmation_status, created_by_user_id
            ) VALUES (%s, %s, 'Test condition', 'active', 'manual', 'confirmed', %s)
            """,
            (
                clinical_fixture["condition"],
                clinical_fixture["profile"],
                clinical_fixture["owner"],
            ),
        )

    for role in ("owner", "editor", "viewer", "analyzer"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, clinical_fixture[role])
            row = connection.execute(
                "SELECT display_name FROM health_compass.profile_conditions WHERE id = %s",
                (clinical_fixture["condition"],),
            ).fetchone()
            assert row == ("Test condition",)

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, clinical_fixture["outsider"])
        assert connection.execute(
            "SELECT id FROM health_compass.profile_conditions WHERE id = %s",
            (clinical_fixture["condition"],),
        ).fetchone() is None


def test_viewer_analyzer_and_outsider_cannot_insert(
    clinical_fixture: dict[str, uuid.UUID],
) -> None:
    for role in ("viewer", "analyzer", "outsider"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, clinical_fixture[role])
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(
                    """
                    INSERT INTO health_compass.profile_allergies (
                      id, profile_id, substance_name, allergy_type, clinical_status,
                      source_type, confirmation_status, created_by_user_id
                    ) VALUES (%s, %s, 'Test substance', 'allergy', 'active',
                              'manual', 'confirmed', %s)
                    """,
                    (uuid.uuid4(), clinical_fixture["profile"], clinical_fixture[role]),
                )


def test_editor_can_update_but_read_only_roles_cannot(
    clinical_fixture: dict[str, uuid.UUID],
) -> None:
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, clinical_fixture["editor"])
        result = connection.execute(
            """
            UPDATE health_compass.profile_conditions
            SET notes = 'Updated by editor', updated_at = now()
            WHERE id = %s
            """,
            (clinical_fixture["condition"],),
        )
        assert result.rowcount == 1

    for role in ("viewer", "analyzer", "outsider"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, clinical_fixture[role])
            result = connection.execute(
                """
                UPDATE health_compass.profile_conditions
                SET notes = 'Forbidden', updated_at = now()
                WHERE id = %s
                """,
                (clinical_fixture["condition"],),
            )
            assert result.rowcount == 0


def test_missing_context_fails_closed_on_warm_clinical_data(
    clinical_fixture: dict[str, uuid.UUID],
) -> None:
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        assert connection.execute(
            "SELECT id FROM health_compass.profile_conditions WHERE id = %s",
            (clinical_fixture["condition"],),
        ).fetchone() is None


def test_clinical_history_blocks_empty_duplicate_assessment(
    clinical_fixture: dict[str, uuid.UUID],
) -> None:
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        payload = connection.execute(
            "SELECT health_compass.app_duplicate_user_activity(%s)",
            (clinical_fixture["owner"],),
        ).fetchone()[0]
        assert payload["is_empty"] is False
        assert payload["profile_conditions"] == 1
        assert payload["meaningful_count"] >= 1


def test_app_role_cannot_delete_clinical_rows(
    clinical_fixture: dict[str, uuid.UUID],
) -> None:
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, clinical_fixture["owner"])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "DELETE FROM health_compass.profile_conditions WHERE id = %s",
                (clinical_fixture["condition"],),
            )
