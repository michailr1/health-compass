from __future__ import annotations

from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def read_migration(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def test_link_intent_tables_force_rls_and_revoke_app_direct_access() -> None:
    intent_sql = read_migration("0023_add_account_linking_intents.py")
    token_sql = read_migration("0025_add_link_email_tokens_and_completion.py")
    assert "ENABLE ROW LEVEL SECURITY" in intent_sql
    assert "FORCE ROW LEVEL SECURITY" in intent_sql
    assert "REVOKE ALL ON {S}.account_link_intents FROM {APP}" in intent_sql
    assert "ENABLE ROW LEVEL SECURITY" in token_sql
    assert "FORCE ROW LEVEL SECURITY" in token_sql
    assert "REVOKE ALL ON {S}.account_link_email_tokens FROM {APP}" in token_sql


def test_link_email_has_fixed_purpose_and_separate_consume_function() -> None:
    token_sql = read_migration("0025_add_link_email_tokens_and_completion.py")
    assert "purpose varchar(32) NOT NULL DEFAULT 'link_email'" in token_sql
    assert "CHECK (purpose = 'link_email')" in token_sql
    assert "app_issue_link_email_token" in token_sql
    assert "app_consume_link_email_token" in token_sql


def test_result_completion_supports_login_and_settings_flows() -> None:
    completion_sql = read_migration("0028_return_link_completion_context.py")
    assert "settings_add_email" in completion_sql
    assert "settings_add_google" in completion_sql
    assert "google_first_email_existing" in completion_sql
    assert "email_first_google_existing" in completion_sql
    assert "FOR UPDATE" in completion_sql
    assert "replayed" in completion_sql


def test_result_completion_migration_has_real_downgrade() -> None:
    completion_sql = read_migration("0028_return_link_completion_context.py")
    downgrade = completion_sql.split("def downgrade() -> None:", 1)[1]
    assert "DROP FUNCTION IF EXISTS" in downgrade
    assert "pass" not in downgrade
    assert "RuntimeError" not in downgrade


def test_identity_removal_uses_separate_tables_purpose_and_force_rls() -> None:
    removal_sql = read_migration("0029_add_identity_removal_step_up.py")
    assert "identity_removal_intents" in removal_sql
    assert "identity_removal_email_tokens" in removal_sql
    assert "purpose varchar(32) NOT NULL DEFAULT 'remove_identity_email'" in removal_sql
    assert "purpose = 'remove_identity_email'" in removal_sql
    assert removal_sql.count("FORCE ROW LEVEL SECURITY") >= 1
    assert "REVOKE ALL ON {S}.{table} FROM {APP}" in removal_sql


def test_identity_removal_preserves_intent_for_idempotent_replay() -> None:
    removal_sql = read_migration("0029_add_identity_removal_step_up.py")
    assert "ON DELETE SET NULL" in removal_sql
    assert "IF i.status = 'completed'" in removal_sql
    assert "'replayed', true" in removal_sql


def test_identity_removal_locks_rows_before_counting() -> None:
    removal_sql = read_migration("0029_add_identity_removal_step_up.py")
    assert "ORDER BY ui.id\n          FOR UPDATE" in removal_sql
    assert "SELECT count(*) INTO identity_count" in removal_sql
    assert "WHERE ui.user_id = i.user_id\n          FOR UPDATE" not in removal_sql


def test_identity_removal_has_hard_last_identity_guard() -> None:
    removal_sql = read_migration("0029_add_identity_removal_step_up.py")
    assert removal_sql.count("IF identity_count <= 1 THEN") >= 3
    assert "target_provider <> required_provider" in removal_sql


def test_duplicate_assessment_is_conservative() -> None:
    duplicate_sql = read_migration("0030_add_duplicate_user_assessment.py")
    for signal in (
        "dashboard_snapshots",
        "body_measurements",
        "profile_audit_events",
        "user_consents",
        "customized_profiles",
        "shared_workspace_members",
        "shared_profile_permissions",
    ):
        assert signal in duplicate_sql
    assert "both_users_have_meaningful_data" in duplicate_sql
    assert "both_empty_oldest_wins" in duplicate_sql


def test_duplicate_assessment_is_bound_to_current_user_context() -> None:
    duplicate_sql = read_migration("0030_add_duplicate_user_assessment.py")
    assert "current_setting('app.current_user_id', true)" in duplicate_sql
    assert "current_user_id NOT IN (first_user_id, second_user_id)" in duplicate_sql
    assert "for signature in (helper_signature, public_signature)" in duplicate_sql
    assert "REVOKE ALL ON FUNCTION {signature} FROM {APP}" in duplicate_sql
    assert "GRANT EXECUTE ON FUNCTION {public_signature} TO {APP}" in duplicate_sql
    assert "'shared_verified_email', true" in duplicate_sql
    assert "'shared_verified_email', shared_verified_email" not in duplicate_sql


def test_duplicate_resolution_has_separate_purpose_and_force_rls() -> None:
    resolution_sql = read_migration("0031_add_duplicate_resolution_intents.py")
    assert "duplicate_resolution_intents" in resolution_sql
    assert "duplicate_resolution_email_tokens" in resolution_sql
    assert "purpose varchar(32) NOT NULL DEFAULT 'resolve_duplicate_email'" in resolution_sql
    assert "purpose = 'resolve_duplicate_email'" in resolution_sql
    assert resolution_sql.count("FORCE ROW LEVEL SECURITY") >= 1
    assert "REVOKE ALL ON {S}.{table} FROM {APP}" in resolution_sql


def test_duplicate_absorption_reassesses_and_revokes_sessions() -> None:
    resolution_sql = read_migration("0031_add_duplicate_resolution_intents.py")
    assert "assessment := {S}.app_assess_duplicate_user_pair" in resolution_sql
    assert "SET status = 'blocked'" in resolution_sql
    assert "UPDATE {S}.auth_sessions" in resolution_sql
    assert "SET revoked_at = coalesce(revoked_at, now())" in resolution_sql
    assert "UPDATE {S}.user_identities" in resolution_sql
    assert "SET user_id = canonical_id" in resolution_sql


def test_duplicate_absorption_has_no_general_medical_data_merge() -> None:
    resolution_sql = read_migration("0031_add_duplicate_resolution_intents.py")
    assert "DELETE FROM {S}.health_profiles" in resolution_sql
    assert "DELETE FROM {S}.workspaces" in resolution_sql
    assert "UPDATE {S}.body_measurements" not in resolution_sql
    assert "UPDATE {S}.dashboard_snapshots" not in resolution_sql
    assert "UPDATE {S}.profile_audit_events" not in resolution_sql
    assert "both_users_have_meaningful_data" in read_migration("0030_add_duplicate_user_assessment.py")


def test_duplicate_absorption_helper_is_not_app_executable() -> None:
    resolution_sql = read_migration("0031_add_duplicate_resolution_intents.py")
    assert "app_apply_duplicate_absorption(uuid)" in resolution_sql
    assert "REVOKE ALL ON FUNCTION {signature} FROM {APP}" in resolution_sql
    assert "for signature in public_signatures" in resolution_sql


def test_duplicate_intent_survives_when_initiator_is_absorbed() -> None:
    preservation_sql = read_migration("0032_preserve_duplicate_resolution_intents.py")
    assert "ALTER COLUMN initiating_user_id DROP NOT NULL" in preservation_sql
    assert "ON DELETE SET NULL" in preservation_sql


def test_duplicate_absorption_restores_protected_initiator_context() -> None:
    context_sql = read_migration("0033_fix_duplicate_absorption_context.py")
    assert "set_config('app.current_user_id', i.initiating_user_id::text, true)" in context_sql
    assert "REVOKE ALL ON FUNCTION {SIG} FROM {APP}" in context_sql


def test_duplicate_candidate_lookup_avoids_uuid_min_and_temp_tables() -> None:
    lookup_sql = read_migration("0034_fix_duplicate_candidate_lookup.py")
    assert "array_agg(c.user_id ORDER BY c.user_id)" in lookup_sql
    assert "cardinality(candidate_user_ids)" in lookup_sql
    assert "min(user_id)" not in lookup_sql
    assert "CREATE TEMP TABLE" not in lookup_sql


def test_security_definer_functions_revoke_public_execute() -> None:
    for filename in (
        "0023_add_account_linking_intents.py",
        "0024_add_account_link_intent_functions.py",
        "0025_add_link_email_tokens_and_completion.py",
        "0026_add_google_link_confirmation.py",
        "0027_add_link_decline_and_separate_account.py",
        "0028_return_link_completion_context.py",
        "0029_add_identity_removal_step_up.py",
        "0030_add_duplicate_user_assessment.py",
        "0031_add_duplicate_resolution_intents.py",
        "0033_fix_duplicate_absorption_context.py",
        "0034_fix_duplicate_candidate_lookup.py",
    ):
        migration = read_migration(filename)
        assert "SECURITY DEFINER" in migration
        assert "REVOKE ALL ON FUNCTION" in migration
