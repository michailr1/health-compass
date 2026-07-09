from __future__ import annotations

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0037_add_clinical_context.py"
)


def test_clinical_context_migration_security_invariants() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "profile_allergies" in sql
    assert "profile_medications" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "app_profile_has_active_health_consent" in sql
    assert "SECURITY DEFINER" in sql
    assert "SET search_path = ''" in sql
    assert "SET row_security = off" in sql
    assert "REVOKE ALL ON FUNCTION {CONSENT_SIG} FROM PUBLIC" in sql
    assert "app_can_view_profile(profile_id)" in sql
    assert "app_can_edit_profile(profile_id)" in sql
    assert "app_profile_has_active_health_consent(profile_id)" in sql


def test_empty_lists_require_explicit_review_timestamps() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "ADD COLUMN allergies_reviewed_at timestamptz" in sql
    assert "ADD COLUMN medications_reviewed_at timestamptz" in sql
