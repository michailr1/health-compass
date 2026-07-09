"""Add result-returning completion functions for login and settings linking.

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
EMAIL_SIG = f"{S}.app_consume_link_email_token_result(text, text, text)"
GOOGLE_SIG = f"{S}.app_complete_google_link_result(uuid, text, text, text, text, text, text)"


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
          token_id uuid;
          target_intent_id uuid;
          i {S}.account_link_intents%ROWTYPE;
          existing_user_id uuid;
          google_subject text;
        BEGIN
          SELECT t.id, t.intent_id INTO token_id, target_intent_id
          FROM {S}.account_link_email_tokens t
          WHERE t.token_hash = link_token_hash
            AND t.purpose = 'link_email'
            AND t.expires_at > now()
          FOR UPDATE;
          IF token_id IS NULL THEN RETURN NULL; END IF;

          SELECT ali.* INTO i
          FROM {S}.account_link_intents ali
          WHERE ali.id = target_intent_id
          FOR UPDATE;

          IF i.id IS NULL
             OR i.required_provider <> 'email'
             OR i.browser_binding_hash <> expected_browser_binding_hash THEN RETURN NULL; END IF;
          IF i.status = 'completed' THEN
            RETURN jsonb_build_object('intent_id', i.id, 'user_id', i.candidate_user_id, 'replayed', true);
          END IF;
          IF i.status <> 'pending_confirmation' OR i.expires_at <= now() THEN RETURN NULL; END IF;
          IF EXISTS (
            SELECT 1 FROM {S}.account_link_email_tokens t
            WHERE t.id = token_id AND t.used_at IS NOT NULL
          ) THEN RETURN NULL; END IF;

          IF i.flow_type = 'settings_add_email' THEN
            SELECT ui.user_id INTO existing_user_id
            FROM {S}.user_identities ui
            WHERE ui.provider = 'email' AND ui.subject = i.normalized_email
            FOR UPDATE;
            IF existing_user_id IS NOT NULL AND existing_user_id <> i.candidate_user_id THEN RETURN NULL; END IF;
            IF existing_user_id IS NULL THEN
              INSERT INTO {S}.user_identities (
                id, user_id, provider, subject, issuer, claims, created_at, last_seen_at
              ) VALUES (
                gen_random_uuid(), i.candidate_user_id, 'email', i.normalized_email,
                'health-compass-email',
                jsonb_build_object('email', i.normalized_email, 'email_verified', true), now(), now()
              );
            END IF;
          ELSIF i.flow_type = 'google_first_email_existing' THEN
            google_subject := i.initiating_subject;
            IF i.initiating_provider <> 'google'
               OR lower(btrim(i.initiating_claims ->> 'email')) <> i.normalized_email
               OR i.initiating_claims ->> 'email_verified' <> 'true' THEN RETURN NULL; END IF;
            SELECT ui.user_id INTO existing_user_id
            FROM {S}.user_identities ui
            WHERE ui.provider = 'google' AND ui.subject = google_subject
            FOR UPDATE;
            IF existing_user_id IS NOT NULL AND existing_user_id <> i.candidate_user_id THEN RETURN NULL; END IF;
            IF existing_user_id IS NULL THEN
              INSERT INTO {S}.user_identities (
                id, user_id, provider, subject, issuer, claims, created_at, last_seen_at
              ) VALUES (
                gen_random_uuid(), i.candidate_user_id, 'google', google_subject,
                google_issuer, i.initiating_claims, now(), now()
              );
            ELSE
              UPDATE {S}.user_identities
              SET claims = i.initiating_claims, last_seen_at = now()
              WHERE provider = 'google' AND subject = google_subject AND user_id = i.candidate_user_id;
            END IF;
          ELSE
            RETURN NULL;
          END IF;

          UPDATE {S}.account_link_email_tokens SET used_at = now() WHERE id = token_id;
          UPDATE {S}.account_link_intents
          SET status = 'completed', completed_at = now(), version = version + 1
          WHERE id = i.id AND status = 'pending_confirmation';
          RETURN jsonb_build_object('intent_id', i.id, 'user_id', i.candidate_user_id, 'replayed', false);
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
          i {S}.account_link_intents%ROWTYPE;
          google_user_id uuid;
          email_user_id uuid;
          normalized_email text;
        BEGIN
          SELECT ali.* INTO i
          FROM {S}.account_link_intents ali
          WHERE ali.id = target_intent_id
          FOR UPDATE;

          IF i.id IS NULL
             OR i.browser_binding_hash <> expected_browser_binding_hash
             OR i.state_hash <> confirmed_state_hash
             OR i.nonce_hash <> confirmed_nonce_hash
             OR i.pkce_verifier_hash <> confirmed_pkce_verifier_hash THEN RETURN NULL; END IF;
          IF i.status = 'completed' THEN
            RETURN jsonb_build_object('intent_id', i.id, 'user_id', i.candidate_user_id, 'replayed', true);
          END IF;
          IF i.status <> 'pending_confirmation'
             OR i.required_provider <> 'google'
             OR i.expires_at <= now() THEN RETURN NULL; END IF;

          normalized_email := lower(btrim(confirmed_google_email));
          IF normalized_email <> i.normalized_email THEN RETURN NULL; END IF;

          SELECT ui.user_id INTO google_user_id
          FROM {S}.user_identities ui
          WHERE ui.provider = 'google' AND ui.subject = confirmed_google_subject
          FOR UPDATE;

          IF i.flow_type = 'settings_add_google' THEN
            IF google_user_id IS NOT NULL AND google_user_id <> i.candidate_user_id THEN RETURN NULL; END IF;
            IF google_user_id IS NULL THEN
              INSERT INTO {S}.user_identities (
                id, user_id, provider, subject, issuer, claims, created_at, last_seen_at
              ) VALUES (
                gen_random_uuid(), i.candidate_user_id, 'google', confirmed_google_subject,
                'https://accounts.google.com',
                jsonb_build_object(
                  'sub', confirmed_google_subject,
                  'email', normalized_email,
                  'email_verified', true
                ),
                now(), now()
              );
            ELSE
              UPDATE {S}.user_identities
              SET last_seen_at = now()
              WHERE provider = 'google' AND subject = confirmed_google_subject AND user_id = i.candidate_user_id;
            END IF;
          ELSIF i.flow_type = 'email_first_google_existing' THEN
            IF google_user_id IS NULL OR google_user_id <> i.candidate_user_id THEN RETURN NULL; END IF;
            SELECT ui.user_id INTO email_user_id
            FROM {S}.user_identities ui
            WHERE ui.provider = 'email' AND ui.subject = i.initiating_subject
            FOR UPDATE;
            IF email_user_id IS NOT NULL AND email_user_id <> i.candidate_user_id THEN RETURN NULL; END IF;
            IF email_user_id IS NULL THEN
              INSERT INTO {S}.user_identities (
                id, user_id, provider, subject, issuer, claims, created_at, last_seen_at
              ) VALUES (
                gen_random_uuid(), i.candidate_user_id, 'email', i.initiating_subject,
                'health-compass-email',
                jsonb_build_object('email', i.initiating_subject, 'email_verified', true), now(), now()
              );
            END IF;
          ELSE
            RETURN NULL;
          END IF;

          UPDATE {S}.account_link_intents
          SET status = 'completed', completed_at = now(), version = version + 1
          WHERE id = i.id AND status = 'pending_confirmation';
          RETURN jsonb_build_object('intent_id', i.id, 'user_id', i.candidate_user_id, 'replayed', false);
        END
        $$
        """
    )

    for signature in (EMAIL_SIG, GOOGLE_SIG):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {R}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    for signature in (GOOGLE_SIG, EMAIL_SIG):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
