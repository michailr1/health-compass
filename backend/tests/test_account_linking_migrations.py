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


def test_security_definer_functions_revoke_public_execute() -> None:
    for filename in (
        "0023_add_account_linking_intents.py",
        "0024_add_account_link_intent_functions.py",
        "0025_add_link_email_tokens_and_completion.py",
        "0026_add_google_link_confirmation.py",
        "0027_add_link_decline_and_separate_account.py",
        "0028_return_link_completion_context.py",
    ):
        migration = read_migration(filename)
        assert "SECURITY DEFINER" in migration
        assert "REVOKE ALL ON FUNCTION" in migration
