"""HC-015 (CR-19/FBL-06): runtime role cannot rewrite identity-critical users columns."""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from psycopg import errors

ADMIN_DSN = os.getenv("HC_TEST_DATABASE_ADMIN_DSN")
APP_DSN = os.getenv("HC_TEST_DATABASE_APP_DSN")

pytestmark = pytest.mark.integration


def _require_dsn(value: str | None, name: str) -> str:
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def _seed_user() -> uuid.UUID:
    user_id = uuid.uuid4()
    with psycopg.connect(_require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN"), autocommit=True) as conn:
        conn.execute(
            "INSERT INTO health_compass.users (id, email, display_name, status) "
            "VALUES (%s, %s, 'Grant test', 'active')",
            (user_id, f"grant-{user_id.hex}@example.test"),
        )
    return user_id


def _cleanup(user_id: uuid.UUID) -> None:
    with psycopg.connect(_require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN"), autocommit=True) as conn:
        conn.execute("DELETE FROM health_compass.users WHERE id = %s", (user_id,))


def test_app_role_can_update_display_name_but_not_identity_columns() -> None:
    app_dsn = _require_dsn(APP_DSN, "HC_TEST_DATABASE_APP_DSN")
    user_id = _seed_user()
    try:
        with psycopg.connect(app_dsn) as conn:
            conn.execute(
                "SELECT set_config('app.current_user_id', %s, false)", (str(user_id),)
            )
            conn.execute(
                "UPDATE health_compass.users SET display_name = 'Renamed', updated_at = now() "
                "WHERE id = %s",
                (user_id,),
            )
            conn.commit()

            for column, value in (("email", "'stolen@example.test'"), ("status", "'disabled'")):
                with pytest.raises(errors.InsufficientPrivilege):
                    conn.execute(
                        f"UPDATE health_compass.users SET {column} = {value} WHERE id = %s",
                        (user_id,),
                    )
                conn.rollback()
                conn.execute(
                    "SELECT set_config('app.current_user_id', %s, false)", (str(user_id),)
                )

        with psycopg.connect(_require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN")) as conn:
            row = conn.execute(
                "SELECT display_name, status FROM health_compass.users WHERE id = %s",
                (user_id,),
            ).fetchone()
            assert row == ("Renamed", "active")
    finally:
        _cleanup(user_id)


def test_users_table_has_no_broad_update_grant() -> None:
    with psycopg.connect(_require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN")) as conn:
        allowed = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.column_privileges "
                "WHERE grantee = 'health_compass_app' "
                "AND table_schema = 'health_compass' AND table_name = 'users' "
                "AND privilege_type = 'UPDATE'"
            )
        }
        assert allowed == {"display_name", "updated_at"}
        table_wide = conn.execute(
            "SELECT count(*) FROM information_schema.role_table_grants "
            "WHERE grantee = 'health_compass_app' "
            "AND table_schema = 'health_compass' AND table_name = 'users' "
            "AND privilege_type = 'UPDATE'"
        ).fetchone()[0]
        assert table_wide == 0
