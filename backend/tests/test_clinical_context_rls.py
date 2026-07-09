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


def _context(connection: psycopg.Connection, user_id: uuid.UUID) -> None:
    connection.execute("SELECT set_config('app.current_user_id', %s, true)", (str(user_id),))


def test_clinical_context_rls_and_consent_gate() -> None:
    admin = _url("TEST_DATABASE_ADMIN_URL")
    app = _url("TEST_DATABASE_URL")
    owner, editor, viewer, outsider, no_consent_owner = [uuid.uuid4() for _ in range(5)]
    workspace, profile = uuid.uuid4(), uuid.uuid4()
    no_consent_workspace, no_consent_profile = uuid.uuid4(), uuid.uuid4()
    users = [owner, editor, viewer, outsider, no_consent_owner]

    with psycopg.connect(admin, autocommit=True) as db:
        for index, user_id in enumerate(users):
            db.execute(
                "INSERT INTO health_compass.users (id, email, display_name, status) VALUES (%s, %s, %s, 'active')",
                (user_id, f"clinical-{index}-{user_id}@example.test", f"user-{index}"),
            )
        db.execute(
            "INSERT INTO health_compass.workspaces (id, name, slug, created_by_user_id) VALUES (%s, 'Clinical', %s, %s)",
            (workspace, f"clinical-{workspace}", owner),
        )
        db.execute(
            "INSERT INTO health_compass.health_profiles (id, workspace_id, owner_user_id, display_name) VALUES (%s, %s, %s, 'Clinical')",
            (profile, workspace, owner),
        )
        for user_id, permission in ((editor, "edit"), (viewer, "view")):
            db.execute(
                "INSERT INTO health_compass.profile_permissions (id, profile_id, user_id, permission, granted_by_user_id) VALUES (%s, %s, %s, %s, %s)",
                (uuid.uuid4(), profile, user_id, permission, owner),
            )
        db.execute(
            "INSERT INTO health_compass.user_consents (id, user_id, consent_type, document_version, accepted_at) VALUES (%s, %s, 'health_data_processing', 'health-data-processing-v1', now())",
            (uuid.uuid4(), owner),
        )
        db.execute(
            "INSERT INTO health_compass.workspaces (id, name, slug, created_by_user_id) VALUES (%s, 'No consent', %s, %s)",
            (no_consent_workspace, f"no-consent-{no_consent_workspace}", no_consent_owner),
        )
        db.execute(
            "INSERT INTO health_compass.health_profiles (id, workspace_id, owner_user_id, display_name) VALUES (%s, %s, %s, 'No consent')",
            (no_consent_profile, no_consent_workspace, no_consent_owner),
        )

    try:
        with psycopg.connect(admin) as db:
            rows = db.execute(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='health_compass' AND relname IN ('profile_allergies','profile_medications') ORDER BY relname"
            ).fetchall()
            assert rows == [("profile_allergies", True, True), ("profile_medications", True, True)]
            assert db.execute(
                "SELECT has_function_privilege('public','health_compass.app_profile_has_active_health_consent(uuid)','EXECUTE')"
            ).fetchone()[0] is False

        with psycopg.connect(app) as db:
            _context(db, owner)
            db.execute(
                "INSERT INTO health_compass.profile_allergies (id,profile_id,allergen,severity,status,source_kind,created_by_user_id,updated_by_user_id) VALUES (%s,%s,'Пенициллин','severe','active','manual',%s,%s)",
                (uuid.uuid4(), profile, owner, owner),
            )
        with psycopg.connect(app) as db:
            _context(db, editor)
            db.execute(
                "INSERT INTO health_compass.profile_medications (id,profile_id,medication_name,status,source_kind,created_by_user_id,updated_by_user_id) VALUES (%s,%s,'Метформин','active','manual',%s,%s)",
                (uuid.uuid4(), profile, editor, editor),
            )
        with psycopg.connect(app) as db:
            _context(db, viewer)
            assert db.execute(
                "SELECT count(*) FROM health_compass.profile_allergies WHERE profile_id=%s", (profile,)
            ).fetchone()[0] == 1
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute(
                    "INSERT INTO health_compass.profile_allergies (id,profile_id,allergen,severity,status,source_kind,created_by_user_id,updated_by_user_id) VALUES (%s,%s,'X','unknown','active','manual',%s,%s)",
                    (uuid.uuid4(), profile, viewer, viewer),
                )
        with psycopg.connect(app) as db:
            _context(db, outsider)
            assert db.execute(
                "SELECT count(*) FROM health_compass.profile_medications WHERE profile_id=%s", (profile,)
            ).fetchone()[0] == 0
        with psycopg.connect(app) as db:
            _context(db, no_consent_owner)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute(
                    "INSERT INTO health_compass.profile_medications (id,profile_id,medication_name,status,source_kind,created_by_user_id,updated_by_user_id) VALUES (%s,%s,'Blocked','active','manual',%s,%s)",
                    (uuid.uuid4(), no_consent_profile, no_consent_owner, no_consent_owner),
                )
    finally:
        with psycopg.connect(admin, autocommit=True) as db:
            db.execute("DELETE FROM health_compass.profile_permissions WHERE profile_id IN (%s,%s)", (profile, no_consent_profile))
            db.execute("DELETE FROM health_compass.health_profiles WHERE id IN (%s,%s)", (profile, no_consent_profile))
            db.execute("DELETE FROM health_compass.workspaces WHERE id IN (%s,%s)", (workspace, no_consent_workspace))
            db.execute("DELETE FROM health_compass.user_consents WHERE user_id = ANY(%s)", (users,))
            db.execute("DELETE FROM health_compass.users WHERE id = ANY(%s)", (users,))
