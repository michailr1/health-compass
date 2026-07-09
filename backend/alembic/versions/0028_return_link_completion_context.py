"""Add result-returning completion functions without replacing 0025/0026 functions.

Revision ID: 0028
Revises: 0027
"""

from __future__ import annotations

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_consume_link_email_token_result(
          link_token_hash text,
          expected_browser_binding_hash text,
          google_issuer text
        ) RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          consumed_token_id uuid;
          target_intent_id uuid;
          locked_intent {S}.account_link_intents%ROWTYPE;
          google_subject text;
          google_email text;
          existing_identity_user_id uuid;
        BEGIN
          SELECT t.id, t.intent_id
          INTO consumed_token_id, target_intent_id
          FROM {S}.account_link_email_tokens t
          WHERE t.token_hash = link_token_hash
            AND t.purpose = 'link_email'
            AND t.expires_at > now()
          FOR UPDATE;

          IF consumed_token_id IS NULL THEN
            RETURN NULL;
          END IF;

          SELECT ali.*
          INTO locked_intent
          FROM {S}.account_link_intents ali
          WHERE ali.id = target_intent_id
          FOR UPDATE;

          IF locked_intent.id IS NULL
             OR locked_intent.required_provider <> 'email'
             OR locked_intent.browser_binding_hash <> expected_browser_binding_hash THEN
            RETURN NULL;
          END IF;

          IF locked_intent.status = 'completed' THEN
            RETURN jsonb_build_object(
              'intent_id', locked_intent.id,
              'user_id', locked_intent.candidate_user_id,
              'replayed', true
            );
          END IF;

          IF locked_intent.status <> 'pending_confirmation'
             OR locked_intent.expires_at <= now()
             OR EXISTS (
               SELECT 1 FROM {S}.account_link_email_tokens used
               WHERE used.id = consumed_token_id AND used.used_at IS NOT NULL
             ) THEN
            RETURN NULL;
          END IF;

          google_subject := locked_intent.initiating_subject;
          google_email := lower(btrim(locked_intent.initiating_claims ->> 'email'));

          IF locked_intent.initiating_provider <> 'google'
             OR google_subject IS NULL
             OR google_email IS NULL
             OR google_email <> locked_intent.normalized_email
             OR locked_intent.initiating_claims ->> 'email_verified' <> 'true' THEN
            RETURN NULL;
          END IF;

          SELECT ui.user_id
          INTO existing_identity_user_id
          FROM {S}.user_identities ui
          WHERE ui.provider = 'google'
            AND ui.subject = google_subject
          FOR UPDATE;

          IF existing_identity_user_id IS NOT NULL
             AND existing_identity_user_id <> locked_intent.candidate_user_id THEN
            RETURN NULL;
          END IF;

          IF existing_identity_user_id IS NULL THEN
            INSERT INTO {S}.user_identities (
              id, user_id, provider, subject, issuer, claims, created_at, last_seen_at
            ) VALUES (
              gen_random_uuid(), locked_intent.candidate_user_id, 'google',
              google_subject, google_issuer, locked_intent.initiating_claims,
              now(), now()
            );
          ELSE
            UPDATE {S}.user_identities
            SET claims = locked_intent.initiating_claims,
                last_seen_at = now()
            WHERE provider = 'google'
              AND subject = google_subject
              AND user_id = locked_intent.candidate_user_id;
          END IF;

          UPDATE {S}.account_link_email_tokens
          SET used_at = now()
          WHERE id = consumed_token_id;

          UPDATE {S}.account_link_intents
          SET status = 'completed', completed_at = now(), version = version + 1
          WHERE id = locked_intent.id AND status = 'pending_confirmation';

          RETURN jsonb_build_object(
            'intent_id', locked_intent.id,
            'user_id', locked_intent.candidate_user_id,
            'replayed', false
          );
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_complete_google_link_result(
          target_intent_id uuid,
          expected_browser_binding_hash text,
          confirmed_state_hash text,
          confirmed_nonce_hash text,
          confirmed_pkce_verifier_hash text,
          confirmed_google_subject text,
          confirmed_google_email text
        ) RETURNS jsonb
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

          IF locked_intent.id IS NULL
             OR locked_intent.browser_binding_hash <> expected_browser_binding_hash
             OR locked_intent.state_hash <> confirmed_state_hash
             OR locked_intent.nonce_hash <> confirmed_nonce_hash
             OR locked_intent.pkce_verifier_hash <> confirmed_pkce_verifier_hash THEN
            RETURN NULL;
          END IF;

          IF locked_intent.status = 'completed' THEN
            RETURN jsonb_build_object(
              'intent_id', locked_intent.id,
              'user_id', locked_intent.candidate_user_id,
              'replayed', true
            );
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
              gen_random_uuid(), locked_intent.candidate_user_id, 'email',
              locked_intent.initiating_subject, 'health-compass-email',
              jsonb_build_object('email', locked_intent.initiating_subject, 'email_verified', true),
              now(), now()
            );
          ELSE
            UPDATE {S}.user_identities
            SET last_seen_at = now()
            WHERE provider = 'email'
              AND subject = locked_intent.initiating_subject
              AND user_id = locked_intent.candidate_user_id;
          END IF;

          UPDATE {S}.account_link_intents
          SET status = 'completed', completed_at = now(), version = version + 1
          WHERE id = locked_intent.id AND status = 'pending_confirmation';

          RETURN jsonb_build_object(
            'intent_id', locked_intent.id,
            'user_id', locked_intent.candidate_user_id,
            'replayed', false
          );
        END
        $$
        """
    )

    email_sig = f"{S}.app_consume_link_email_token_result(text, text, text)"
    google_sig = f"{S}.app_complete_google_link_result(uuid, text, text, text, text, text, text)"
    for signature in (email_sig, google_sig):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {R}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    email_sig = f"{S}.app_consume_link_email_token_result(text, text, text)"
    google_sig = f"{S}.app_complete_google_link_result(uuid, text, text, text, text, text, text)"
    for signature in (google_sig, email_sig):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
