"""Cross-user PostgreSQL RLS tests for Basic Health Profile Slice 1."""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"
APP_ENV = "TEST_DATABASE_URL"


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
def rls_fixture() -> dict[str, uuid.UUID]:
    ids = {
        "owner": uuid.uuid4(),
        "editor": uuid.uuid4(),
        "viewer": uuid.uuid4(),
        "analyzer": uuid.uuid4(),
        "outsider": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "profile": uuid.uuid4(),
    }

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        for role in ("owner", "editor", "viewer", "analyzer", "outsider"):
            connection.execute(
                """
                INSERT INTO health_compass.users
                  (id, email, display_name, status)
                VALUES (%s, %s, %s, 'active')
                """,
                (ids[role], f"{role}-{ids[role]}@example.test", role),
            )

        connection.execute(
            """
            INSERT INTO health_compass.workspaces
              (id, name, slug, created_by_user_id)
            VALUES (%s, 'RLS test', %s, %s)
            """,
            (ids["workspace"], f"rls-{ids['workspace']}", ids["owner"]),
        )
        connection.execute(
            """
            INSERT INTO health_compass.health_profiles
              (id, workspace_id, owner_user_id, display_name)
            VALUES (%s, %s, %s, 'RLS profile')
            """,
            (ids["profile"], ids["workspace"], ids["owner"]),
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
        connection.execute(
            "DELETE FROM health_compass.profile_audit_events WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.body_measurements WHERE profile_id = %s",
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
            "DELETE FROM health_compass.workspaces WHERE id = %s",
            (ids["workspace"],),
        )
        connection.execute(
            "DELETE FROM health_compass.users WHERE id = ANY(%s)",
            ([ids[key] for key in ("owner", "editor", "viewer", "analyzer", "outsider")],),
        )


def test_read_permissions_and_cross_user_isolation(rls_fixture: dict[str, uuid.UUID]) -> None:
    profile_id = rls_fixture["profile"]
    for role in ("owner", "editor", "viewer", "analyzer"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, rls_fixture[role])
            row = connection.execute(
                "SELECT id FROM health_compass.health_profiles WHERE id = %s",
                (profile_id,),
            ).fetchone()
            assert row == (profile_id,)

    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, rls_fixture["outsider"])
        row = connection.execute(
            "SELECT id FROM health_compass.health_profiles WHERE id = %s",
            (profile_id,),
        ).fetchone()
        assert row is None


def test_edit_helper_matches_role_permissions(rls_fixture: dict[str, uuid.UUID]) -> None:
    profile_id = rls_fixture["profile"]
    expected = {
        "owner": True,
        "editor": True,
        "viewer": False,
        "analyzer": False,
        "outsider": False,
    }
    for role, can_edit in expected.items():
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, rls_fixture[role])
            value = connection.execute(
                "SELECT health_compass.app_can_edit_profile(%s)",
                (profile_id,),
            ).fetchone()[0]
            assert value is can_edit


def test_owner_and_editor_can_update_but_read_only_roles_cannot(
    rls_fixture: dict[str, uuid.UUID],
) -> None:
    profile_id = rls_fixture["profile"]
    for role in ("owner", "editor"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, rls_fixture[role])
            result = connection.execute(
                """
                UPDATE health_compass.health_profiles
                SET display_name = %s, updated_at = now()
                WHERE id = %s
                """,
                (f"Updated by {role}", profile_id),
            )
            assert result.rowcount == 1

    for role in ("viewer", "analyzer", "outsider"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, rls_fixture[role])
            result = connection.execute(
                """
                UPDATE health_compass.health_profiles
                SET display_name = 'forbidden', updated_at = now()
                WHERE id = %s
                """,
                (profile_id,),
            )
            assert result.rowcount == 0


def test_measurement_insert_is_limited_to_owner_and_editor(
    rls_fixture: dict[str, uuid.UUID],
) -> None:
    profile_id = rls_fixture["profile"]
    for role in ("owner", "editor"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, rls_fixture[role])
            connection.execute(
                """
                INSERT INTO health_compass.body_measurements
                  (id, profile_id, measurement_type, value, unit, measured_at,
                   source_type, confirmation_status, created_by_user_id)
                VALUES (%s, %s, 'weight', 98.0, 'kg', now(),
                        'manual', 'confirmed', %s)
                """,
                (uuid.uuid4(), profile_id, rls_fixture[role]),
            )

    for role in ("viewer", "analyzer", "outsider"):
        with psycopg.connect(_sync_url(APP_ENV)) as connection:
            _set_user(connection, rls_fixture[role])
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(
                    """
                    INSERT INTO health_compass.body_measurements
                      (id, profile_id, measurement_type, value, unit, measured_at,
                       source_type, confirmation_status, created_by_user_id)
                    VALUES (%s, %s, 'weight', 98.0, 'kg', now(),
                            'manual', 'confirmed', %s)
                    """,
                    (uuid.uuid4(), profile_id, rls_fixture[role]),
                )


def test_missing_context_fails_closed_without_recursion(
    rls_fixture: dict[str, uuid.UUID],
) -> None:
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        row = connection.execute(
            "SELECT id FROM health_compass.health_profiles WHERE id = %s",
            (rls_fixture["profile"],),
        ).fetchone()
        assert row is None

        editable = connection.execute(
            "SELECT health_compass.app_can_edit_profile(%s)",
            (rls_fixture["profile"],),
        ).fetchone()[0]
        assert editable is False
