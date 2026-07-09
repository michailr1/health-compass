"""Add purpose-specific link_email tokens and transactional completion.

Revision ID: 0025
Revises: 0024
"""

from __future__ import annotations

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {S}.account_link_email_tokens (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          intent_id uuid NOT NULL REFERENCES {S}.account_link_intents(id) ON DELETE CASCADE,
          purpose varchar(32) NOT NULL DEFAULT 'link_email',
          token_hash varchar(64) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          expires_at timestamptz NOT NULL,
          used_at timestamptz NULL,
          requested_ip varchar(45) NULL,
          user_agent text NULL,
          CONSTRAINT uq_account_link_email_tokens_hash UNIQUE (token_hash),
          CONSTRAINT ck_account_link_email_tokens_purpose CHECK (purpose = 'link_email'),
          CONSTRAINT ck_account_link_email_tokens_expiry CHECK (expires_at > created_at)
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_account_link_email_tokens_intent_created "
        f"ON {S}.account_link_email_tokens (intent_id, created_at DESC)"
    )
    op.execute(f"ALTER TABLE {S}.account_link_email_tokens ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.account_link_email_tokens FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY account_link_email_tokens_fail_closed "
        f"ON {S}.account_link_email_tokens AS RESTRICTIVE FOR ALL "
        f"USING (false) WITH CHECK (false)"
    )
    op.execute(f"REVOKE ALL ON {S}.account_link_email_tokens FROM PUBLIC")
    op.execute(f"REVOKE ALL ON {S}.account_link_email_tokens FROM {APP}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.account_link_email_tokens TO {R}")
    op.execute(f"GRANT SELECT, UPDATE ON {S}.account_link_intents TO {R}")
    op.execute(f"GRANT SELECT, INSERT ON {S}.user_identities TO {R}")

    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_issue_link_email_token(
          target_intent_id uuid,
          expected_browser_binding_hash text,
          link_token_hash text,
          link_expires_at timestamptz,
          link_ip text,
          link_user_agent text
        ) RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          target_email text;
        BEGIN
          SELECT ali.normalized_email
          INTO target_email
          FROM {S}.account_link_intents ali
          WHERE ali.id = target_intent_id
            AND ali.status = 'pending_confirmation'
            AND ali.required_provider = 'email'
            AND ali.expires_at > now()
            AND ali.browser_binding_hash = expected_browser_binding_hash;

          IF target_email IS NULL THEN
            RETURN NULL;
          END IF;

          IF (
            SELECT count(*)
            FROM {S}.account_link_email_tokens t
            WHERE t.intent_id = target_intent_id
              AND t.created_at > now() - interval '15 minutes'
          ) >= 5 THEN
            RETURN NULL;
          END IF;

          INSERT INTO {S}.account_link_email_tokens (
            intent_id, purpose, token_hash, expires_at, requested_ip, user_agent
          ) VALUES (
            target_intent_id, 'link_email', link_token_hash, link_expires_at, link_ip, link_user_agent
          );

          RETURN target_email;
        END
        $$
        """
    )

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
          locked_intent {S}.account_link_intents%ROWTYPE;
          consumed_token_id uuid;
          google_subject text;
          google_email text;
        BEGIN
          SELECT t.id, ali.*
          INTO consumed_token_id, locked_intent
          FROM {S}.account_link_email_tokens t
          JOIN {S}.account_link_intents ali ON ali.id = t.intent_id
          WHERE t.token_hash = link_token_hash
            AND t.purpose = 'link_email'
            AND t.used_at IS NULL
            AND t.expires_at > now()
          FOR UPDATE OF t, ali;

          IF consumed_token_id IS NULL THEN
            RETURN NULL;
          END IF;

          IF locked_intent.status <> 'pending_confirmation'
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

          IF EXISTS (
            SELECT 1 FROM {S}.user_identities ui
            WHERE ui.provider = 'google'
              AND ui.subject = google_subject
              AND ui.user_id <> locked_intent.candidate_user_id
          ) THEN
            RETURN NULL;
          END IF;

          INSERT INTO {S}.user_identities (
            id, user_id, provider, subject, issuer, claims, created_at, last_seen_at
          ) VALUES (
            gen_random_uuid(),
            locked_intent.candidate_user_id,
            'google',
            google_subject,
            google_issuer,
            locked_intent.initiating_claims,
            now(),
            now()
          )
          ON CONFLICT (provider, subject) DO UPDATE
          SET last_seen_at = EXCLUDED.last_seen_at,
              claims = EXCLUDED.claims
          WHERE {S}.user_identities.user_id = locked_intent.candidate_user_id;

          UPDATE {S}.account_link_email_tokens
          SET used_at = now()
          WHERE id = consumed_token_id;

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

    issue_sig = (
        f"{S}.app_issue_link_email_token(uuid, text, text, timestamptz, text, text)"
    )
    consume_sig = f"{S}.app_consume_link_email_token(text, text, text)"
    for signature in (issue_sig, consume_sig):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {R}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    consume_sig = f"{S}.app_consume_link_email_token(text, text, text)"
    issue_sig = (
        f"{S}.app_issue_link_email_token(uuid, text, text, timestamptz, text, text)"
    )
    for signature in (consume_sig, issue_sig):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
    op.execute(f"REVOKE ALL ON {S}.account_link_email_tokens FROM {R}")
    op.execute(f"DROP TABLE {S}.account_link_email_tokens")
