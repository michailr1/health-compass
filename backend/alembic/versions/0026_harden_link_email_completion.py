"""Harden link_email completion locking and identity ownership checks.

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
SIG = f"{S}.app_consume_link_email_token(text, text, text)"


def upgrade() -> None:
    op.execute(f"GRANT UPDATE ON {S}.user_identities TO {R}")
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_consume_link_email_token(
          link_token_hash text,
          expected_browser_binding_hash text,
          google_issuer text
        ) RETURNS uuid
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
            AND t.used_at IS NULL
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
             OR locked_intent.status <> 'pending_confirmation'
             OR locked_intent.required_provider <> 'email'
             OR locked_intent.expires_at <= now()
             OR locked_intent.browser_binding_hash <> expected_browser_binding_hash THEN
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

          RETURN locked_intent.candidate_user_id;
        END
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {SIG} OWNER TO {R}")
    op.execute(f"REVOKE ALL ON FUNCTION {SIG} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIG} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    # Downgrade keeps the safer implementation; schema compatibility is unchanged.
    pass
