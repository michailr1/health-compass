"""Add account-link decline, separate-account claim and audit helpers.

Revision ID: 0027
Revises: 0026
"""

from __future__ import annotations

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(f"GRANT SELECT, UPDATE ON {S}.account_link_intents TO {R}")
    op.execute(f"GRANT INSERT ON {S}.audit_events TO {R}")
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_decline_account_link(
          target_intent_id uuid,
          expected_browser_binding_hash text
        ) RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        BEGIN
          UPDATE {S}.account_link_intents
          SET status = 'declined',
              declined_at = now(),
              version = version + 1
          WHERE id = target_intent_id
            AND status = 'pending_confirmation'
            AND expires_at > now()
            AND browser_binding_hash = expected_browser_binding_hash;

          RETURN FOUND;
        END
        $$
        """
    )

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

          UPDATE {S}.account_link_intents
          SET status = 'cancelled',
              version = version + 1
          WHERE id = locked_intent.id
            AND status = 'declined';

          RETURN result_payload;
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_record_account_link_audit(
          audit_event_type text,
          audit_result text,
          audit_intent_id uuid,
          audit_actor_user_id text,
          audit_ip text,
          audit_user_agent text,
          audit_metadata jsonb
        ) RETURNS void
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
          INSERT INTO {S}.audit_events (
            id, event_type, result, actor_user_id, entity_type, entity_id,
            ip_address, user_agent, metadata, created_at
          ) VALUES (
            gen_random_uuid(), audit_event_type, audit_result, audit_actor_user_id,
            'account_link_intent', audit_intent_id::text,
            audit_ip, audit_user_agent, audit_metadata, now()
          )
        $$
        """
    )

    signatures = (
        f"{S}.app_decline_account_link(uuid, text)",
        f"{S}.app_claim_declined_link_for_separate_account(uuid, text)",
        f"{S}.app_record_account_link_audit(text, text, uuid, text, text, text, jsonb)",
    )
    for signature in signatures:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {R}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    signatures = (
        f"{S}.app_record_account_link_audit(text, text, uuid, text, text, text, jsonb)",
        f"{S}.app_claim_declined_link_for_separate_account(uuid, text)",
        f"{S}.app_decline_account_link(uuid, text)",
    )
    for signature in signatures:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
