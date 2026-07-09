"""Add Google confirmation preparation and transactional completion.

Revision ID: 0026
Revises: 0025
"""

from __future__ import annotations

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(f"GRANT SELECT, UPDATE ON {S}.account_link_intents TO {R}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.user_identities TO {R}")
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_prepare_google_link(
          target_intent_id uuid,
          expected_browser_binding_hash text,
          new_state_hash text,
          new_nonce_hash text,
          new_pkce_verifier_hash text
        ) RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        BEGIN
          UPDATE {S}.account_link_intents
          SET state_hash = new_state_hash,
              nonce_hash = new_nonce_hash,
              pkce_verifier_hash = new_pkce_verifier_hash,
              version = version + 1
          WHERE id = target_intent_id
            AND status = 'pending_confirmation'
            AND required_provider = 'google'
            AND initiating_provider = 'email'
            AND expires_at > now()
            AND browser_binding_hash = expected_browser_binding_hash;

          RETURN FOUND;
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_complete_google_link(
          target_intent_id uuid,
          expected_browser_binding_hash text,
          confirmed_state_hash text,
          confirmed_nonce_hash text,
          confirmed_pkce_verifier_hash text,
          confirmed_google_subject text,
          confirmed_google_email text
        ) RETURNS uuid
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          locked_intent {S}.account_link_intents%ROWTYPE;
          google_identity_user_id uuid;
          existing_email_identity_user_id uuid;
          normalized_confirmed_email text;
        BEGIN
          SELECT ali.*
          INTO locked_intent
          FROM {S}.account_link_intents ali
          WHERE ali.id = target_intent_id
          FOR UPDATE;

          IF locked_intent.id IS NULL THEN
            RETURN NULL;
          END IF;

          IF locked_intent.browser_binding_hash <> expected_browser_binding_hash
             OR locked_intent.state_hash <> confirmed_state_hash
             OR locked_intent.nonce_hash <> confirmed_nonce_hash
             OR locked_intent.pkce_verifier_hash <> confirmed_pkce_verifier_hash THEN
            RETURN NULL;
          END IF;

          IF locked_intent.status = 'completed' THEN
            RETURN locked_intent.candidate_user_id;
          END IF;

          IF locked_intent.status <> 'pending_confirmation'
             OR locked_intent.required_provider <> 'google'
             OR locked_intent.initiating_provider <> 'email'
             OR locked_intent.expires_at <= now() THEN
            RETURN NULL;
          END IF;

          normalized_confirmed_email := lower(btrim(confirmed_google_email));
          IF normalized_confirmed_email <> locked_intent.normalized_email THEN
            RETURN NULL;
          END IF;

          SELECT ui.user_id
          INTO google_identity_user_id
          FROM {S}.user_identities ui
          WHERE ui.provider = 'google'
            AND ui.subject = confirmed_google_subject
            AND lower(btrim(ui.claims ->> 'email')) = normalized_confirmed_email
            AND ui.claims ->> 'email_verified' = 'true'
          FOR UPDATE;

          IF google_identity_user_id IS NULL
             OR google_identity_user_id <> locked_intent.candidate_user_id THEN
            RETURN NULL;
          END IF;

          SELECT ui.user_id
          INTO existing_email_identity_user_id
          FROM {S}.user_identities ui
          WHERE ui.provider = 'email'
            AND ui.subject = locked_intent.initiating_subject
          FOR UPDATE;

          IF existing_email_identity_user_id IS NOT NULL
             AND existing_email_identity_user_id <> locked_intent.candidate_user_id THEN
            RETURN NULL;
          END IF;

          IF existing_email_identity_user_id IS NULL THEN
            INSERT INTO {S}.user_identities (
              id, user_id, provider, subject, issuer, claims, created_at, last_seen_at
            ) VALUES (
              gen_random_uuid(),
              locked_intent.candidate_user_id,
              'email',
              locked_intent.initiating_subject,
              'health-compass-email',
              jsonb_build_object(
                'email', locked_intent.initiating_subject,
                'email_verified', true
              ),
              now(),
              now()
            );
          ELSE
            UPDATE {S}.user_identities
            SET last_seen_at = now()
            WHERE provider = 'email'
              AND subject = locked_intent.initiating_subject
              AND user_id = locked_intent.candidate_user_id;
          END IF;

          UPDATE {S}.account_link_intents
          SET status = 'completed',
              completed_at = now(),
              version = version + 1
          WHERE id = locked_intent.id
            AND status = 'pending_confirmation';

          RETURN locked_intent.candidate_user_id;
        END
        $$
        """
    )

    prepare_sig = f"{S}.app_prepare_google_link(uuid, text, text, text, text)"
    complete_sig = f"{S}.app_complete_google_link(uuid, text, text, text, text, text, text)"
    for signature in (prepare_sig, complete_sig):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {R}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    complete_sig = f"{S}.app_complete_google_link(uuid, text, text, text, text, text, text)"
    prepare_sig = f"{S}.app_prepare_google_link(uuid, text, text, text, text)"
    for signature in (complete_sig, prepare_sig):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
