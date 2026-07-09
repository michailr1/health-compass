"""Fix declined-to-cancelled transition for explicit separate accounts.

Revision ID: 0036
Revises: 0035
"""

from __future__ import annotations

from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"
SIG = f"{S}.app_claim_declined_link_for_separate_account(uuid, text)"


def _create_function(*, clear_declined_at: bool) -> None:
    declined_assignment = "declined_at = NULL," if clear_declined_at else ""
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_claim_declined_link_for_separate_account(
          target_intent_id uuid,
          expected_browser_binding_hash text
        ) RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          locked_intent {S}.account_link_intents%ROWTYPE;
          result_payload jsonb;
        BEGIN
          SELECT ali.*
          INTO locked_intent
          FROM {S}.account_link_intents ali
          WHERE ali.id = target_intent_id
          FOR UPDATE;

          IF locked_intent.id IS NULL
             OR locked_intent.status <> 'declined'
             OR locked_intent.expires_at <= now()
             OR locked_intent.browser_binding_hash <> expected_browser_binding_hash THEN
            RETURN NULL;
          END IF;

          result_payload := jsonb_build_object(
            'normalized_email', locked_intent.normalized_email,
            'provider', locked_intent.initiating_provider,
            'subject', locked_intent.initiating_subject,
            'claims', coalesce(locked_intent.initiating_claims, '{{}}'::jsonb)
          );

          UPDATE {S}.account_link_intents AS ali
          SET status = 'cancelled',
              {declined_assignment}
              version = ali.version + 1
          WHERE ali.id = locked_intent.id
            AND ali.status = 'declined';

          RETURN result_payload;
        END
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {SIG} OWNER TO {R}")
    op.execute(f"REVOKE ALL ON FUNCTION {SIG} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {SIG} FROM {APP}")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIG} TO {APP}")


def upgrade() -> None:
    _create_function(clear_declined_at=True)


def downgrade() -> None:
    _create_function(clear_declined_at=False)
