"""HC-015 Slice D: canonical concept integrity on the DB boundary (CR-04/05/19).

Uses the deterministic 0043 seed concepts:
- 11111111-1111-4111-8111-111111111101  condition_or_symptom
- 11111111-1111-4111-8111-111111111201  allergy_or_intolerance
- 11111111-1111-4111-8111-111111111301  medication
- 11111111-1111-4111-8111-111111111401  supplement
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from psycopg import errors

ADMIN_DSN = os.getenv("HC_TEST_DATABASE_ADMIN_DSN")
APP_DSN = os.getenv("HC_TEST_DATABASE_APP_DSN")

pytestmark = pytest.mark.integration

CONDITION_CONCEPT = "11111111-1111-4111-8111-111111111101"
ALLERGY_CONCEPT = "11111111-1111-4111-8111-111111111201"
MEDICATION_CONCEPT = "11111111-1111-4111-8111-111111111301"
SUPPLEMENT_CONCEPT = "11111111-1111-4111-8111-111111111401"

SECTIONS = {
    "profile_conditions": {
        "name_column": "display_name",
        "status_column": "clinical_status",
        "own_concept": CONDITION_CONCEPT,
        "wrong_concept": MEDICATION_CONCEPT,
    },
    "profile_allergies": {
        "name_column": "substance_name",
        "status_column": "clinical_status",
        "own_concept": ALLERGY_CONCEPT,
        "wrong_concept": SUPPLEMENT_CONCEPT,
        "extra_columns": {"allergy_type": "unknown"},
    },
    "profile_medications": {
        "name_column": "display_name",
        "status_column": "status",
        "own_concept": MEDICATION_CONCEPT,
        "wrong_concept": CONDITION_CONCEPT,
    },
    "profile_supplements": {
        "name_column": "display_name",
        "status_column": "status",
        "own_concept": SUPPLEMENT_CONCEPT,
        "wrong_concept": MEDICATION_CONCEPT,
        "extra_columns": {"supplement_type": "unknown"},
    },
}


def _require_dsn(value: str | None, name: str) -> str:
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


def _seed_profile() -> dict:
    ids = {"user": uuid.uuid4(), "workspace": uuid.uuid4(), "profile": uuid.uuid4()}
    with psycopg.connect(_require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN"), autocommit=True) as conn:
        conn.execute(
            "INSERT INTO health_compass.users (id, email, display_name, status) "
            "VALUES (%s, %s, 'Dict integrity', 'active')",
            (ids["user"], f"dict-{ids['user'].hex}@example.test"),
        )
        conn.execute(
            "INSERT INTO health_compass.workspaces (id, name, slug, created_by_user_id) "
            "VALUES (%s, 'Dict test', %s, %s)",
            (ids["workspace"], f"dict-{ids['workspace']}", ids["user"]),
        )
        conn.execute(
            "INSERT INTO health_compass.workspace_members (id, workspace_id, user_id, role) "
            "VALUES (%s, %s, %s, 'owner')",
            (uuid.uuid4(), ids["workspace"], ids["user"]),
        )
        conn.execute(
            "INSERT INTO health_compass.health_profiles (id, workspace_id, owner_user_id, display_name) "
            "VALUES (%s, %s, %s, 'Dict profile')",
            (ids["profile"], ids["workspace"], ids["user"]),
        )
        conn.execute(
            "INSERT INTO health_compass.profile_permissions "
            "(id, profile_id, user_id, permission, granted_by_user_id) "
            "VALUES (%s, %s, %s, 'owner', %s)",
            (uuid.uuid4(), ids["profile"], ids["user"], ids["user"]),
        )
    return ids


def _cleanup_profile(ids: dict) -> None:
    with psycopg.connect(_require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN"), autocommit=True) as conn:
        for table in SECTIONS:
            conn.execute(
                f"DELETE FROM health_compass.{table} WHERE profile_id = %s",
                (ids["profile"],),
            )
        conn.execute(
            "DELETE FROM health_compass.profile_permissions WHERE profile_id = %s",
            (ids["profile"],),
        )
        conn.execute(
            "DELETE FROM health_compass.health_profiles WHERE id = %s", (ids["profile"],)
        )
        conn.execute(
            "DELETE FROM health_compass.workspace_members WHERE workspace_id = %s",
            (ids["workspace"],),
        )
        conn.execute(
            "DELETE FROM health_compass.workspaces WHERE id = %s", (ids["workspace"],)
        )
        conn.execute("DELETE FROM health_compass.users WHERE id = %s", (ids["user"],))


def _app_conn(user_id: uuid.UUID) -> psycopg.Connection:
    conn = psycopg.connect(_require_dsn(APP_DSN, "HC_TEST_DATABASE_APP_DSN"))
    conn.execute("SELECT set_config('app.current_user_id', %s, false)", (str(user_id),))
    return conn


def _insert_row(
    conn: psycopg.Connection,
    table: str,
    ids: dict,
    *,
    code_system: str | None,
    code: str | None,
) -> uuid.UUID:
    spec = SECTIONS[table]
    row_id = uuid.uuid4()
    extra = spec.get("extra_columns", {})
    columns = [
        "id", "profile_id", spec["name_column"], "code_system", "code",
        spec["status_column"], "source_type", "confirmation_status",
        "created_by_user_id", *extra.keys(),
    ]
    values = [
        row_id, ids["profile"], "Integrity test entry", code_system, code,
        "active", "manual", "confirmed", ids["user"], *extra.values(),
    ]
    placeholders = ", ".join(["%s"] * len(values))
    conn.execute(
        f"INSERT INTO health_compass.{table} ({', '.join(columns)}) VALUES ({placeholders})",
        values,
    )
    return row_id


def _canonical(conn: psycopg.Connection, table: str, row_id: uuid.UUID) -> str | None:
    row = conn.execute(
        f"SELECT canonical_concept_id FROM health_compass.{table} WHERE id = %s",
        (row_id,),
    ).fetchone()
    assert row is not None
    return str(row[0]) if row[0] else None


@pytest.mark.parametrize("table", sorted(SECTIONS))
def test_matching_domain_concept_is_accepted_and_derived(table: str) -> None:
    ids = _seed_profile()
    spec = SECTIONS[table]
    try:
        with _app_conn(ids["user"]) as conn:
            row_id = _insert_row(
                conn, table, ids, code_system="health_compass", code=spec["own_concept"]
            )
            assert _canonical(conn, table, row_id) == spec["own_concept"]
            conn.commit()
    finally:
        _cleanup_profile(ids)


@pytest.mark.parametrize("table", sorted(SECTIONS))
def test_wrong_domain_concept_is_rejected(table: str) -> None:
    ids = _seed_profile()
    spec = SECTIONS[table]
    try:
        with _app_conn(ids["user"]) as conn:
            with pytest.raises(errors.Error) as excinfo:
                _insert_row(
                    conn, table, ids,
                    code_system="health_compass", code=spec["wrong_concept"],
                )
            assert excinfo.value.sqlstate == "HC409"
    finally:
        _cleanup_profile(ids)


@pytest.mark.parametrize("table", sorted(SECTIONS))
def test_unknown_concept_is_rejected(table: str) -> None:
    ids = _seed_profile()
    try:
        with _app_conn(ids["user"]) as conn:
            with pytest.raises(errors.Error) as excinfo:
                _insert_row(
                    conn, table, ids,
                    code_system="health_compass", code=str(uuid.uuid4()),
                )
            assert excinfo.value.sqlstate == "HC404"
    finally:
        _cleanup_profile(ids)


@pytest.mark.parametrize("table", sorted(SECTIONS))
def test_invalid_uuid_code_is_rejected_with_controlled_state(table: str) -> None:
    ids = _seed_profile()
    try:
        with _app_conn(ids["user"]) as conn:
            with pytest.raises(errors.Error) as excinfo:
                _insert_row(
                    conn, table, ids,
                    code_system="health_compass", code="not-a-uuid-not-a-uuid-not-a-uuid",
                )
            assert excinfo.value.sqlstate == "HC422"
    finally:
        _cleanup_profile(ids)


@pytest.mark.parametrize("table", sorted(SECTIONS))
def test_clearing_code_clears_canonical_mapping(table: str) -> None:
    ids = _seed_profile()
    spec = SECTIONS[table]
    try:
        with _app_conn(ids["user"]) as conn:
            row_id = _insert_row(
                conn, table, ids, code_system="health_compass", code=spec["own_concept"]
            )
            conn.execute(
                f"UPDATE health_compass.{table} SET code = NULL WHERE id = %s",
                (row_id,),
            )
            assert _canonical(conn, table, row_id) is None
    finally:
        _cleanup_profile(ids)


@pytest.mark.parametrize("table", sorted(SECTIONS))
def test_changing_code_system_clears_derived_mapping(table: str) -> None:
    ids = _seed_profile()
    spec = SECTIONS[table]
    try:
        with _app_conn(ids["user"]) as conn:
            row_id = _insert_row(
                conn, table, ids, code_system="health_compass", code=spec["own_concept"]
            )
            conn.execute(
                f"UPDATE health_compass.{table} SET code_system = 'icd-10', code = 'A00' "
                "WHERE id = %s",
                (row_id,),
            )
            assert _canonical(conn, table, row_id) is None
    finally:
        _cleanup_profile(ids)


def test_changing_code_atomically_remaps_canonical() -> None:
    ids = _seed_profile()
    try:
        with _app_conn(ids["user"]) as conn:
            row_id = _insert_row(
                conn, "profile_conditions", ids,
                code_system="health_compass", code=CONDITION_CONCEPT,
            )
            other_condition = "11111111-1111-4111-8111-111111111102"
            conn.execute(
                "UPDATE health_compass.profile_conditions SET code = %s WHERE id = %s",
                (other_condition, row_id),
            )
            assert _canonical(conn, "profile_conditions", row_id) == other_condition
    finally:
        _cleanup_profile(ids)


@pytest.mark.parametrize("table", sorted(SECTIONS))
def test_app_role_cannot_update_canonical_column_directly(table: str) -> None:
    """CR-19/D4: canonical_concept_id is system-managed, no direct UPDATE grant."""
    ids = _seed_profile()
    spec = SECTIONS[table]
    try:
        with _app_conn(ids["user"]) as conn:
            row_id = _insert_row(conn, table, ids, code_system=None, code=None)
            conn.commit()
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(
                    f"UPDATE health_compass.{table} SET canonical_concept_id = %s "
                    "WHERE id = %s",
                    (spec["own_concept"], row_id),
                )
    finally:
        _cleanup_profile(ids)


def test_client_cannot_store_contradictory_combination() -> None:
    """A direct canonical write that contradicts the coding is re-derived."""
    ids = _seed_profile()
    admin_dsn = _require_dsn(ADMIN_DSN, "HC_TEST_DATABASE_ADMIN_DSN")
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            row_id = _insert_row(
                conn, "profile_conditions", ids,
                code_system="health_compass", code=CONDITION_CONCEPT,
            )
            # Even a privileged direct write of the derived column is
            # overridden by the trigger re-derivation from the source coding.
            conn.execute(
                "UPDATE health_compass.profile_conditions "
                "SET canonical_concept_id = %s WHERE id = %s",
                (MEDICATION_CONCEPT, row_id),
            )
            assert _canonical(conn, "profile_conditions", row_id) == CONDITION_CONCEPT
    finally:
        _cleanup_profile(ids)
