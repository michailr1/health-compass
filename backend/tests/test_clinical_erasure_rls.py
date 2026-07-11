"""PostgreSQL security tests for permanent Clinical Context erasure."""

from __future__ import annotations

import datetime
import os
import uuid

import psycopg
import pytest

ADMIN_ENV = "TEST_DATABASE_ADMIN_URL"
APP_ENV = "TEST_DATABASE_URL"
FUNCTION_SIGNATURE = (
    "health_compass.app_erase_clinical_record("
    "uuid,text,uuid,timestamp with time zone,uuid,text)"
)

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


@pytest.fixture()
def erasure_fixture() -> dict[str, object]:
    ids: dict[str, object] = {
        "owner": uuid.uuid4(),
        "editor": uuid.uuid4(),
        "workspace": uuid.uuid4(),
        "profile": uuid.uuid4(),
        "record": uuid.uuid4(),
        "audit": uuid.uuid4(),
    }
    private_label = f"Private-erasure-{uuid.uuid4()}"
    ids["private_label"] = private_label

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        for role in ("owner", "editor"):
            connection.execute(
                """
                INSERT INTO health_compass.users
                  (id, email, display_name, status)
                VALUES (%s, %s, %s, 'active')
                """,
                (
                    ids[role],
                    f"erasure-{role}-{ids[role]}@example.test",
                    role,
                ),
            )
        connection.execute(
            """
            INSERT INTO health_compass.workspaces
              (id, name, slug, created_by_user_id)
            VALUES (%s, 'Erasure test', %s, %s)
            """,
            (ids["workspace"], f"erasure-{ids['workspace']}", ids["owner"]),
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
            VALUES (%s, %s, %s, 'Erasure profile')
            """,
            (ids["profile"], ids["workspace"], ids["owner"]),
        )
        connection.execute(
            """
            INSERT INTO health_compass.profile_permissions
              (id, profile_id, user_id, permission, granted_by_user_id)
            VALUES (%s, %s, %s, 'owner', %s),
                   (%s, %s, %s, 'edit', %s)
            """,
            (
                uuid.uuid4(), ids["profile"], ids["owner"], ids["owner"],
                uuid.uuid4(), ids["profile"], ids["editor"], ids["owner"],
            ),
        )
        updated_at = connection.execute(
            """
            INSERT INTO health_compass.profile_conditions (
              id, profile_id, display_name, clinical_status,
              source_type, confirmation_status, created_by_user_id
            ) VALUES (%s, %s, %s, 'active', 'manual', 'confirmed', %s)
            RETURNING updated_at
            """,
            (ids["record"], ids["profile"], private_label, ids["owner"]),
        ).fetchone()[0]
        ids["updated_at"] = updated_at
        connection.execute(
            """
            INSERT INTO health_compass.profile_audit_events (
              id, profile_id, actor_user_id, entity_type, entity_id,
              action, changed_fields, request_id
            ) VALUES (
              %s, %s, %s, 'condition', %s,
              'condition.created',
              jsonb_build_object('display_name', jsonb_build_object('old', NULL, 'new', %s::text)),
              'erasure-fixture'
            )
            """,
            (
                ids["audit"], ids["profile"], ids["owner"], ids["record"], private_label,
            ),
        )

    yield ids

    with psycopg.connect(_sync_url(ADMIN_ENV), autocommit=True) as connection:
        connection.execute(
            "DELETE FROM health_compass.profile_audit_events WHERE profile_id = %s",
            (ids["profile"],),
        )
        connection.execute(
            "DELETE FROM health_compass.profile_conditions WHERE profile_id = %s",
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
            ([ids["owner"], ids["editor"]],),
        )


def _call_erasure(
    connection: psycopg.Connection,
    fixture: dict[str, object],
    *,
    expected_updated_at: datetime.datetime,
) -> bool:
    return bool(
        connection.execute(
            """
            SELECT health_compass.app_erase_clinical_record(
              %s, 'conditions', %s, %s, %s, 'erasure-test'
            )
            """,
            (
                fixture["profile"],
                fixture["record"],
                expected_updated_at,
                uuid.uuid4(),
            ),
        ).fetchone()[0]
    )


def test_erasure_function_is_tightly_owned_and_not_public() -> None:
    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        row = connection.execute(
            """
            SELECT r.rolname, p.prosecdef,
                   has_function_privilege('public', %s::regprocedure, 'EXECUTE'),
                   has_function_privilege('health_compass_app', %s::regprocedure, 'EXECUTE')
            FROM pg_proc p
            JOIN pg_roles r ON r.oid = p.proowner
            WHERE p.oid = %s::regprocedure
            """,
            (FUNCTION_SIGNATURE, FUNCTION_SIGNATURE, FUNCTION_SIGNATURE),
        ).fetchone()
        assert row == ("health_compass_rls_definer", True, False, True)


def test_runtime_role_still_has_no_direct_delete(
    erasure_fixture: dict[str, object],
) -> None:
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, erasure_fixture["owner"])
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "DELETE FROM health_compass.profile_conditions WHERE id = %s",
                (erasure_fixture["record"],),
            )


def test_editor_cannot_permanently_erase_owner_record(
    erasure_fixture: dict[str, object],
) -> None:
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, erasure_fixture["editor"])
        with pytest.raises(psycopg.Error) as exc_info:
            _call_erasure(
                connection,
                erasure_fixture,
                expected_updated_at=erasure_fixture["updated_at"],
            )
        assert exc_info.value.sqlstate == "HC404"


def test_stale_owner_erasure_is_rejected_without_data_loss(
    erasure_fixture: dict[str, object],
) -> None:
    stale = erasure_fixture["updated_at"] - datetime.timedelta(seconds=1)
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, erasure_fixture["owner"])
        with pytest.raises(psycopg.Error) as exc_info:
            _call_erasure(connection, erasure_fixture, expected_updated_at=stale)
        assert exc_info.value.sqlstate == "HC409"

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            "SELECT count(*) FROM health_compass.profile_conditions WHERE id = %s",
            (erasure_fixture["record"],),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT count(*) FROM health_compass.profile_audit_events WHERE entity_id = %s",
            (erasure_fixture["record"],),
        ).fetchone()[0] == 1


def test_owner_can_erase_without_active_consent_and_audit_content_is_scrubbed(
    erasure_fixture: dict[str, object],
) -> None:
    # The fixture intentionally creates no health-data consent. Erasure must
    # still remain available after consent is absent or withdrawn.
    with psycopg.connect(_sync_url(APP_ENV)) as connection:
        _set_user(connection, erasure_fixture["owner"])
        assert _call_erasure(
            connection,
            erasure_fixture,
            expected_updated_at=erasure_fixture["updated_at"],
        ) is True

    with psycopg.connect(_sync_url(ADMIN_ENV)) as connection:
        assert connection.execute(
            "SELECT count(*) FROM health_compass.profile_conditions WHERE id = %s",
            (erasure_fixture["record"],),
        ).fetchone()[0] == 0

        rows = connection.execute(
            """
            SELECT entity_type, action, changed_fields, request_id
            FROM health_compass.profile_audit_events
            WHERE profile_id = %s AND entity_id = %s
            """,
            (erasure_fixture["profile"], erasure_fixture["record"]),
        ).fetchall()
        assert rows == [
            ("clinical_record", "clinical_record.erased", {}, "erasure-test")
        ]
        assert erasure_fixture["private_label"] not in str(rows)
