"""Add step-up protected identity removal.

Revision ID: 0029
Revises: 0028
"""

from __future__ import annotations

from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {S}.identity_removal_intents (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id uuid NOT NULL REFERENCES {S}.users(id) ON DELETE CASCADE,
          target_identity_id uuid NOT NULL REFERENCES {S}.user_identities(id) ON DELETE CASCADE,
          target_provider varchar(64) NOT NULL,
          required_provider varchar(64) NOT NULL,
          status varchar(32) NOT NULL DEFAULT 'pending_confirmation',
          browser_binding_hash varchar(64) NOT NULL,
          state_hash varchar(64),
          nonce_hash varchar(64),
          pkce_verifier_hash varchar(64),
          expires_at timestamptz NOT NULL,
          completed_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          version integer NOT NULL DEFAULT 1,
          CONSTRAINT ck_identity_removal_status CHECK (
            status IN ('pending_confirmation', 'completed', 'cancelled', 'expired')
          ),
          CONSTRAINT ck_identity_removal_provider CHECK (
            target_provider IN ('google', 'email')
            AND required_provider IN ('google', 'email')
            AND target_provider <> required_provider
          )
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE {S}.identity_removal_email_tokens (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          intent_id uuid NOT NULL REFERENCES {S}.identity_removal_intents(id) ON DELETE CASCADE,
          purpose varchar(32) NOT NULL DEFAULT 'remove_identity_email',
          token_hash varchar(64) NOT NULL UNIQUE,
          expires_at timestamptz NOT NULL,
          used_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_identity_removal_email_purpose CHECK (
            purpose = 'remove_identity_email'
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_identity_removal_user_status ON {S}.identity_removal_intents(user_id, status)"
    )
    op.execute(
        f"CREATE INDEX ix_identity_removal_email_intent ON {S}.identity_removal_email_tokens(intent_id)"
    )

    for table in ("identity_removal_intents", "identity_removal_email_tokens"):
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {S}.{table} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON {S}.{table} FROM {APP}")

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.identity_removal_intents TO {R}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.identity_removal_email_tokens TO {R}")
    op.execute(f"GRANT SELECT, DELETE ON {S}.user_identities TO {R}")
    op.execute(f"GRANT INSERT ON {S}.audit_events TO {R}")
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_create_identity_removal_intent(
          actor_user_id uuid,
          target_identity_id uuid,
          new_browser_binding_hash text,
          new_expires_at timestamptz
        ) RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          target_identity {S}.user_identities%ROWTYPE;
          remaining_provider text;
          identity_count integer;
          new_intent_id uuid;
        BEGIN
          SELECT count(*) INTO identity_count
          FROM {S}.user_identities ui
          WHERE ui.user_id = actor_user_id;

          IF identity_count <= 1 THEN
            RETURN NULL;
          END IF;

          SELECT ui.* INTO target_identity
          FROM {S}.user_identities ui
          WHERE ui.id = target_identity_id
            AND ui.user_id = actor_user_id
          FOR UPDATE;

          IF target_identity.id IS NULL
             OR target_identity.provider NOT IN ('google', 'email') THEN
            RETURN NULL;
          END IF;

          SELECT ui.provider INTO remaining_provider
          FROM {S}.user_identities ui
          WHERE ui.user_id = actor_user_id
            AND ui.id <> target_identity.id
            AND ui.provider IN ('google', 'email')
            AND (
              (ui.provider = 'email' AND ui.claims ->> 'email_verified' = 'true')
              OR
              (ui.provider = 'google' AND ui.claims ->> 'email_verified' = 'true')
            )
          ORDER BY CASE ui.provider WHEN 'google' THEN 1 ELSE 2 END
          LIMIT 1
          FOR UPDATE;

          IF remaining_provider IS NULL OR remaining_provider = target_identity.provider THEN
            RETURN NULL;
          END IF;

          UPDATE {S}.identity_removal_intents
          SET status = 'cancelled', version = version + 1
          WHERE user_id = actor_user_id
            AND target_identity_id = target_identity.id
            AND status = 'pending_confirmation';

          INSERT INTO {S}.identity_removal_intents (
            user_id, target_identity_id, target_provider, required_provider,
            browser_binding_hash, expires_at
          ) VALUES (
            actor_user_id, target_identity.id, target_identity.provider, remaining_provider,
            new_browser_binding_hash, new_expires_at
          ) RETURNING id INTO new_intent_id;

          RETURN jsonb_build_object(
            'intent_id', new_intent_id,
            'target_provider', target_identity.provider,
            'required_provider', remaining_provider
          );
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_prepare_identity_removal_google(
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
          UPDATE {S}.identity_removal_intents
          SET state_hash = new_state_hash,
              nonce_hash = new_nonce_hash,
              pkce_verifier_hash = new_pkce_verifier_hash,
              version = version + 1
          WHERE id = target_intent_id
            AND status = 'pending_confirmation'
            AND required_provider = 'google'
            AND expires_at > now()
            AND browser_binding_hash = expected_browser_binding_hash;
          RETURN FOUND;
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_complete_identity_removal_google(
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
          i {S}.identity_removal_intents%ROWTYPE;
          confirmed_user_id uuid;
          identity_count integer;
        BEGIN
          SELECT iri.* INTO i
          FROM {S}.identity_removal_intents iri
          WHERE iri.id = target_intent_id
          FOR UPDATE;

          IF i.id IS NULL
             OR i.browser_binding_hash <> expected_browser_binding_hash
             OR i.state_hash <> confirmed_state_hash
             OR i.nonce_hash <> confirmed_nonce_hash
             OR i.pkce_verifier_hash <> confirmed_pkce_verifier_hash THEN
            RETURN NULL;
          END IF;

          IF i.status = 'completed' THEN
            RETURN jsonb_build_object(
              'intent_id', i.id,
              'user_id', i.user_id,
              'removed_provider', i.target_provider,
              'replayed', true
            );
          END IF;

          IF i.status <> 'pending_confirmation'
             OR i.required_provider <> 'google'
             OR i.expires_at <= now() THEN
            RETURN NULL;
          END IF;

          SELECT ui.user_id INTO confirmed_user_id
          FROM {S}.user_identities ui
          WHERE ui.provider = 'google'
            AND ui.subject = confirmed_google_subject
            AND lower(btrim(ui.claims ->> 'email')) = lower(btrim(confirmed_google_email))
            AND ui.claims ->> 'email_verified' = 'true'
            AND ui.id <> i.target_identity_id
          FOR UPDATE;

          IF confirmed_user_id IS NULL OR confirmed_user_id <> i.user_id THEN
            RETURN NULL;
          END IF;

          SELECT count(*) INTO identity_count
          FROM {S}.user_identities ui
          WHERE ui.user_id = i.user_id
          FOR UPDATE;

          IF identity_count <= 1 THEN
            RETURN NULL;
          END IF;

          DELETE FROM {S}.user_identities ui
          WHERE ui.id = i.target_identity_id
            AND ui.user_id = i.user_id;

          IF NOT FOUND THEN RETURN NULL; END IF;

          UPDATE {S}.identity_removal_intents
          SET status = 'completed', completed_at = now(), version = version + 1
          WHERE id = i.id AND status = 'pending_confirmation';

          RETURN jsonb_build_object(
            'intent_id', i.id,
            'user_id', i.user_id,
            'removed_provider', i.target_provider,
            'replayed', false
          );
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_issue_identity_removal_email_token(
          target_intent_id uuid,
          expected_browser_binding_hash text,
          new_token_hash text,
          new_expires_at timestamptz
        ) RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          i {S}.identity_removal_intents%ROWTYPE;
          recipient text;
        BEGIN
          SELECT iri.* INTO i
          FROM {S}.identity_removal_intents iri
          WHERE iri.id = target_intent_id
          FOR UPDATE;

          IF i.id IS NULL
             OR i.status <> 'pending_confirmation'
             OR i.required_provider <> 'email'
             OR i.expires_at <= now()
             OR i.browser_binding_hash <> expected_browser_binding_hash THEN
            RETURN NULL;
          END IF;

          SELECT ui.subject INTO recipient
          FROM {S}.user_identities ui
          WHERE ui.user_id = i.user_id
            AND ui.provider = 'email'
            AND ui.id <> i.target_identity_id
            AND ui.claims ->> 'email_verified' = 'true'
          LIMIT 1
          FOR UPDATE;

          IF recipient IS NULL THEN RETURN NULL; END IF;

          DELETE FROM {S}.identity_removal_email_tokens
          WHERE intent_id = i.id AND used_at IS NULL;

          INSERT INTO {S}.identity_removal_email_tokens (
            intent_id, token_hash, expires_at
          ) VALUES (
            i.id, new_token_hash, least(new_expires_at, i.expires_at)
          );

          RETURN recipient;
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_consume_identity_removal_email_token(
          removal_token_hash text,
          expected_browser_binding_hash text
        ) RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          token_row {S}.identity_removal_email_tokens%ROWTYPE;
          i {S}.identity_removal_intents%ROWTYPE;
          confirmed_email_user_id uuid;
          identity_count integer;
        BEGIN
          SELECT t.* INTO token_row
          FROM {S}.identity_removal_email_tokens t
          WHERE t.token_hash = removal_token_hash
            AND t.purpose = 'remove_identity_email'
            AND t.expires_at > now()
          FOR UPDATE;

          IF token_row.id IS NULL THEN RETURN NULL; END IF;

          SELECT iri.* INTO i
          FROM {S}.identity_removal_intents iri
          WHERE iri.id = token_row.intent_id
          FOR UPDATE;

          IF i.id IS NULL
             OR i.browser_binding_hash <> expected_browser_binding_hash
             OR i.required_provider <> 'email' THEN
            RETURN NULL;
          END IF;

          IF i.status = 'completed' THEN
            RETURN jsonb_build_object(
              'intent_id', i.id,
              'user_id', i.user_id,
              'removed_provider', i.target_provider,
              'replayed', true
            );
          END IF;

          IF i.status <> 'pending_confirmation'
             OR i.expires_at <= now()
             OR token_row.used_at IS NOT NULL THEN
            RETURN NULL;
          END IF;

          SELECT ui.user_id INTO confirmed_email_user_id
          FROM {S}.user_identities ui
          WHERE ui.user_id = i.user_id
            AND ui.provider = 'email'
            AND ui.id <> i.target_identity_id
            AND ui.claims ->> 'email_verified' = 'true'
          LIMIT 1
          FOR UPDATE;

          IF confirmed_email_user_id IS NULL THEN RETURN NULL; END IF;

          SELECT count(*) INTO identity_count
          FROM {S}.user_identities ui
          WHERE ui.user_id = i.user_id
          FOR UPDATE;

          IF identity_count <= 1 THEN RETURN NULL; END IF;

          DELETE FROM {S}.user_identities ui
          WHERE ui.id = i.target_identity_id
            AND ui.user_id = i.user_id;

          IF NOT FOUND THEN RETURN NULL; END IF;

          UPDATE {S}.identity_removal_email_tokens
          SET used_at = now()
          WHERE id = token_row.id;

          UPDATE {S}.identity_removal_intents
          SET status = 'completed', completed_at = now(), version = version + 1
          WHERE id = i.id AND status = 'pending_confirmation';

          RETURN jsonb_build_object(
            'intent_id', i.id,
            'user_id', i.user_id,
            'removed_provider', i.target_provider,
            'replayed', false
          );
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_record_identity_removal_audit(
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
            'identity_removal_intent', audit_intent_id::text,
            audit_ip, audit_user_agent, audit_metadata, now()
          )
        $$
        """
    )

    signatures = (
        f"{S}.app_create_identity_removal_intent(uuid, uuid, text, timestamptz)",
        f"{S}.app_prepare_identity_removal_google(uuid, text, text, text, text)",
        f"{S}.app_complete_identity_removal_google(uuid, text, text, text, text, text, text)",
        f"{S}.app_issue_identity_removal_email_token(uuid, text, text, timestamptz)",
        f"{S}.app_consume_identity_removal_email_token(text, text)",
        f"{S}.app_record_identity_removal_audit(text, text, uuid, text, text, text, jsonb)",
    )
    for signature in signatures:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {R}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    signatures = (
        f"{S}.app_record_identity_removal_audit(text, text, uuid, text, text, text, jsonb)",
        f"{S}.app_consume_identity_removal_email_token(text, text)",
        f"{S}.app_issue_identity_removal_email_token(uuid, text, text, timestamptz)",
        f"{S}.app_complete_identity_removal_google(uuid, text, text, text, text, text, text)",
        f"{S}.app_prepare_identity_removal_google(uuid, text, text, text, text)",
        f"{S}.app_create_identity_removal_intent(uuid, uuid, text, timestamptz)",
    )
    for signature in signatures:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")

    op.execute(f"DROP TABLE IF EXISTS {S}.identity_removal_email_tokens")
    op.execute(f"DROP TABLE IF EXISTS {S}.identity_removal_intents")
