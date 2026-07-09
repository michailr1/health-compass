"""Add narrow SECURITY DEFINER functions for account-link intents.

Revision ID: 0024
Revises: 0023
"""

from __future__ import annotations

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(f"GRANT SELECT ON {S}.users TO {R}")
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_create_account_link_intent(
          intent_flow_type text,
          intent_normalized_email text,
          intent_candidate_user_id uuid,
          intent_initiating_provider text,
          intent_initiating_subject text,
          intent_required_provider text,
          intent_browser_binding_hash text,
          intent_expires_at timestamptz,
          intent_initiating_claims jsonb,
          intent_created_ip text,
          intent_user_agent text
        ) RETURNS uuid
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          created_intent_id uuid;
        BEGIN
          IF intent_expires_at <= now() THEN
            RAISE EXCEPTION 'account-link intent expiry must be in the future';
          END IF;

          IF intent_initiating_provider = intent_required_provider THEN
            RAISE EXCEPTION 'account-link providers must be distinct';
          END IF;

          IF NOT EXISTS (
            SELECT 1
            FROM {S}.users u
            WHERE u.id = intent_candidate_user_id
              AND u.status = 'active'
          ) THEN
            RAISE EXCEPTION 'account-link candidate is unavailable';
          END IF;

          INSERT INTO {S}.account_link_intents (
            flow_type,
            status,
            normalized_email,
            candidate_user_id,
            initiating_provider,
            initiating_subject,
            required_provider,
            initiating_claims,
            browser_binding_hash,
            created_ip,
            user_agent,
            expires_at
          ) VALUES (
            intent_flow_type,
            'pending_confirmation',
            lower(btrim(intent_normalized_email)),
            intent_candidate_user_id,
            intent_initiating_provider,
            intent_initiating_subject,
            intent_required_provider,
            intent_initiating_claims,
            intent_browser_binding_hash,
            intent_created_ip,
            intent_user_agent,
            intent_expires_at
          )
          RETURNING id INTO created_intent_id;

          RETURN created_intent_id;
        END
        $$
        """
    )
    op.execute(
        f"ALTER FUNCTION {S}.app_create_account_link_intent("
        "text, text, uuid, text, text, text, text, timestamptz, jsonb, text, text) "
        f"OWNER TO {R}"
    )
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")
    op.execute(
        f"REVOKE ALL ON FUNCTION {S}.app_create_account_link_intent("
        "text, text, uuid, text, text, text, text, timestamptz, jsonb, text, text) "
        "FROM PUBLIC"
    )
    op.execute(
        f"GRANT EXECUTE ON FUNCTION {S}.app_create_account_link_intent("
        "text, text, uuid, text, text, text, text, timestamptz, jsonb, text, text) "
        f"TO {APP}"
    )


def downgrade() -> None:
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION {S}.app_create_account_link_intent("
        "text, text, uuid, text, text, text, text, timestamptz, jsonb, text, text) "
        f"FROM {APP}"
    )
    op.execute(
        f"DROP FUNCTION IF EXISTS {S}.app_create_account_link_intent("
        "text, text, uuid, text, text, text, text, timestamptz, jsonb, text, text)"
    )
    op.execute(f"REVOKE SELECT ON {S}.users FROM {R}")
