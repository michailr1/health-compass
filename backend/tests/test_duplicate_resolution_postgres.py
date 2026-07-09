from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

APP_DSN = os.getenv("HC_TEST_DATABASE_APP_DSN")
MIGRATOR_DSN = os.getenv("HC_TEST_DATABASE_MIGRATOR_DSN")

pytestmark = pytest.mark.integration


def require_dsn(value: str | None, name: str) -> str:
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def test_concurrent_empty_duplicate_absorption_is_idempotent() -> None:
    app_dsn = require_dsn(APP_DSN, "HC_TEST_DATABASE_APP_DSN")
    migrator_dsn = require_dsn(MIGRATOR_DSN, "HC_TEST_DATABASE_MIGRATOR_DSN")

    canonical_user_id = uuid.uuid4()
    absorbed_user_id = uuid.uuid4()
    canonical_identity_id = uuid.uuid4()
    absorbed_identity_id = uuid.uuid4()
    canonical_workspace_id = uuid.uuid4()
    absorbed_workspace_id = uuid.uuid4()
    canonical_workspace_member_id = uuid.uuid4()
    absorbed_workspace_member_id = uuid.uuid4()
    canonical_profile_id = uuid.uuid4()
    absorbed_profile_id = uuid.uuid4()
    canonical_permission_id = uuid.uuid4()
    absorbed_permission_id = uuid.uuid4()
    absorbed_session_id = uuid.uuid4()
    email = f"hc-duplicate-{canonical_user_id.hex}@example.test"
    google_subject = f"google-{canonical_user_id.hex}"
    browser_hash = "d" * 64
    token_hash = "r" * 64

    with psycopg.connect(migrator_dsn) as connection, connection.cursor() as cursor:
        cursor.execute("SET ROLE health_compass_rls_definer")
        cursor.execute(
            """
            INSERT INTO health_compass.users (
              id, email, display_name, status, created_at, updated_at
            ) VALUES
              (%s, %s, 'Canonical duplicate test', 'active', now() - interval '2 minutes', now()),
              (%s, %s, 'Absorbed duplicate test', 'active', now() - interval '1 minute', now())
            """,
            (canonical_user_id, email, absorbed_user_id, email),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.user_identities (
              id, user_id, provider, subject, issuer, claims, last_seen_at
            ) VALUES
              (
                %s, %s, 'google', %s, 'https://accounts.google.com',
                jsonb_build_object('email', %s, 'email_verified', true), now()
              ),
              (
                %s, %s, 'email', %s, 'health-compass-email',
                jsonb_build_object('email', %s, 'email_verified', true), now()
              )
            """,
            (
                canonical_identity_id,
                canonical_user_id,
                google_subject,
                email,
                absorbed_identity_id,
                absorbed_user_id,
                email,
                email,
            ),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.workspaces (id, name, slug, created_by_user_id)
            VALUES
              (%s, 'Canonical workspace', %s, %s),
              (%s, 'Absorbed workspace', %s, %s)
            """,
            (
                canonical_workspace_id,
                f"canonical-{canonical_user_id.hex}",
                canonical_user_id,
                absorbed_workspace_id,
                f"absorbed-{absorbed_user_id.hex}",
                absorbed_user_id,
            ),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.workspace_members (
              id, workspace_id, user_id, role
            ) VALUES
              (%s, %s, %s, 'owner'),
              (%s, %s, %s, 'owner')
            """,
            (
                canonical_workspace_member_id,
                canonical_workspace_id,
                canonical_user_id,
                absorbed_workspace_member_id,
                absorbed_workspace_id,
                absorbed_user_id,
            ),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.health_profiles (
              id, workspace_id, owner_user_id, display_name
            ) VALUES
              (%s, %s, %s, 'Canonical profile'),
              (%s, %s, %s, 'Absorbed profile')
            """,
            (
                canonical_profile_id,
                canonical_workspace_id,
                canonical_user_id,
                absorbed_profile_id,
                absorbed_workspace_id,
                absorbed_user_id,
            ),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.profile_permissions (
              id, profile_id, user_id, permission
            ) VALUES
              (%s, %s, %s, 'owner'),
              (%s, %s, %s, 'owner')
            """,
            (
                canonical_permission_id,
                canonical_profile_id,
                canonical_user_id,
                absorbed_permission_id,
                absorbed_profile_id,
                absorbed_user_id,
            ),
        )
        cursor.execute(
            """
            INSERT INTO health_compass.auth_sessions (
              id, user_id, session_token_hash, expires_at
            ) VALUES (%s, %s, %s, now() + interval '1 hour')
            """,
            (absorbed_session_id, absorbed_user_id, f"session-{absorbed_user_id.hex}",),
        )

    intent_id: uuid.UUID | None = None
    try:
        with psycopg.connect(app_dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_user_id', %s, true)",
                (str(canonical_user_id),),
            )
            cursor.execute(
                """
                SELECT health_compass.app_create_duplicate_resolution_intent(
                  %s, %s, now() + interval '15 minutes'
                )
                """,
                (canonical_user_id, browser_hash),
            )
            resolution = cursor.fetchone()[0]
            assert resolution["available"] is True
            assert resolution["required_provider"] == "email"
            assert resolution["canonical_is_current"] is True
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

        def complete() -> dict:
            with psycopg.connect(app_dsn) as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT health_compass.app_complete_duplicate_resolution_email(%s, %s)
                    """,
                    (token_hash, browser_hash),
                )
                return cursor.fetchone()[0]

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: complete(), range(2)))

        assert all(result["canonical_user_id"] == str(canonical_user_id) for result in results)
        assert all(result["intent_id"] == str(intent_id) for result in results)
        assert sorted(result["replayed"] for result in results) == [False, True]

        with psycopg.connect(migrator_dsn) as connection, connection.cursor() as cursor:
            cursor.execute("SET ROLE health_compass_rls_definer")
            cursor.execute(
                "SELECT count(*) FROM health_compass.users WHERE id = %s",
                (absorbed_user_id,),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                """
                SELECT provider, count(*)
                FROM health_compass.user_identities
                WHERE user_id = %s
                GROUP BY provider
                ORDER BY provider
                """,
                (canonical_user_id,),
            )
            assert cursor.fetchall() == [("email", 1), ("google", 1)]
            cursor.execute(
                "SELECT count(*) FROM health_compass.workspaces WHERE created_by_user_id = %s",
                (absorbed_user_id,),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "SELECT count(*) FROM health_compass.health_profiles WHERE owner_user_id = %s",
                (absorbed_user_id,),
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                """
                SELECT user_id, revoked_at IS NOT NULL
                FROM health_compass.auth_sessions
                WHERE id = %s
                """,
                (absorbed_session_id,),
            )
            assert cursor.fetchone() == (canonical_user_id, True)
            cursor.execute(
                "SELECT status FROM health_compass.duplicate_resolution_intents WHERE id = %s",
                (intent_id,),
            )
            assert cursor.fetchone()[0] == "completed"
    finally:
        with psycopg.connect(migrator_dsn) as connection, connection.cursor() as cursor:
            cursor.execute("SET ROLE health_compass_rls_definer")
            cursor.execute(
                "DELETE FROM health_compass.profile_permissions WHERE profile_id = %s",
                (canonical_profile_id,),
            )
            cursor.execute(
                "DELETE FROM health_compass.health_profiles WHERE id = %s",
                (canonical_profile_id,),
            )
            cursor.execute(
                "DELETE FROM health_compass.workspace_members WHERE workspace_id = %s",
                (canonical_workspace_id,),
            )
            cursor.execute(
                "DELETE FROM health_compass.workspaces WHERE id = %s",
                (canonical_workspace_id,),
            )
            cursor.execute(
                "DELETE FROM health_compass.users WHERE id IN (%s, %s)",
                (canonical_user_id, absorbed_user_id),
            )
