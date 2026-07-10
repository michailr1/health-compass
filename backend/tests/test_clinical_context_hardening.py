"""Integration tests for Clinical Context write hardening."""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

pytestmark = pytest.mark.integration


def _url(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is not configured")
    return value.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _set_user(connection: psycopg.Connection, user_id: uuid.UUID) -> None:
    connection.execute(
        "SELECT set_config('app.current_user_id', %s, true)",
        (str(user_id),),
    )


def test_app_cannot_spoof_document_provenance_or_rewrite_voided_rows() -> None:
    owner = uuid.uuid4()
    other = uuid.uuid4()
    workspace = uuid.uuid4()
    profile = uuid.uuid4()
    condition = uuid.uuid4()

    with psycopg.connect(_url("TEST_DATABASE_ADMIN_URL"), autocommit=True) as connection:
        for user_id, label in ((owner, "owner"), (other, "other")):
            connection.execute(
                "INSERT INTO health_compass.users (id, email, display_name, status) "
                "VALUES (%s, %s, %s, 'active')",
                (user_id, f"hardening-{label}-{user_id}@example.test", label),
            )
        connection.execute(
            "INSERT INTO health_compass.workspaces (id, name, slug, created_by_user_id) "
            "VALUES (%s, 'Hardening', %s, %s)",
            (workspace, f"hardening-{workspace}", owner),
        )
        connection.execute(
            "INSERT INTO health_compass.workspace_members (id, workspace_id, user_id, role) "
            "VALUES (%s, %s, %s, 'owner')",
            (uuid.uuid4(), workspace, owner),
        )
        connection.execute(
            "INSERT INTO health_compass.health_profiles "
            "(id, workspace_id, owner_user_id, display_name) VALUES (%s, %s, %s, 'Profile')",
            (profile, workspace, owner),
        )
        connection.execute(
            "INSERT INTO health_compass.profile_permissions "
            "(id, profile_id, user_id, permission, granted_by_user_id) "
            "VALUES (%s, %s, %s, 'owner', %s)",
            (uuid.uuid4(), profile, owner, owner),
        )

    try:
        with psycopg.connect(_url("TEST_DATABASE_URL")) as connection:
            _set_user(connection, owner)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(
                    """
                    INSERT INTO health_compass.profile_conditions (
                      id, profile_id, display_name, clinical_status,
                      source_type, confirmation_status, created_by_user_id
                    ) VALUES (%s, %s, 'Spoofed import', 'active',
                              'document', 'needs_review', %s)
                    """,
                    (uuid.uuid4(), profile, owner),
                )

        with psycopg.connect(_url("TEST_DATABASE_URL")) as connection:
            _set_user(connection, owner)
            connection.execute(
                """
                INSERT INTO health_compass.profile_conditions (
                  id, profile_id, display_name, clinical_status,
                  source_type, confirmation_status, created_by_user_id
                ) VALUES (%s, %s, 'Manual', 'active', 'manual', 'confirmed', %s)
                """,
                (condition, profile, owner),
            )
            connection.execute(
                """
                UPDATE health_compass.profile_conditions
                SET voided_at = now(), voided_by_user_id = %s,
                    void_reason = 'Ошибка', updated_at = now()
                WHERE id = %s
                """,
                (owner, condition),
            )

        with psycopg.connect(_url("TEST_DATABASE_URL")) as connection:
            _set_user(connection, owner)
            result = connection.execute(
                "UPDATE health_compass.profile_conditions "
                "SET notes = 'Rewrite' WHERE id = %s",
                (condition,),
            )
            assert result.rowcount == 0

        with psycopg.connect(_url("TEST_DATABASE_ADMIN_URL")) as connection:
            actor = connection.execute(
                "SELECT voided_by_user_id FROM health_compass.profile_conditions WHERE id = %s",
                (condition,),
            ).fetchone()[0]
            assert actor == owner
    finally:
        with psycopg.connect(_url("TEST_DATABASE_ADMIN_URL"), autocommit=True) as connection:
            connection.execute(
                "DELETE FROM health_compass.profile_conditions WHERE profile_id = %s",
                (profile,),
            )
            connection.execute(
                "DELETE FROM health_compass.profile_permissions WHERE profile_id = %s",
                (profile,),
            )
            connection.execute("DELETE FROM health_compass.health_profiles WHERE id = %s", (profile,))
            connection.execute(
                "DELETE FROM health_compass.workspace_members WHERE workspace_id = %s",
                (workspace,),
            )
            connection.execute("DELETE FROM health_compass.workspaces WHERE id = %s", (workspace,))
            connection.execute(
                "DELETE FROM health_compass.users WHERE id = ANY(%s)",
                ([owner, other],),
            )
