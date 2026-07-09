"""Add HC-026 duplicate resolution intents and transactional absorption.

Revision ID: 0031
Revises: 0030
"""

from __future__ import annotations

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {S}.duplicate_resolution_intents (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          initiating_user_id uuid NOT NULL REFERENCES {S}.users(id) ON DELETE CASCADE,
          canonical_user_id uuid NOT NULL REFERENCES {S}.users(id) ON DELETE CASCADE,
          absorbed_user_id uuid REFERENCES {S}.users(id) ON DELETE SET NULL,
          required_provider varchar(64) NOT NULL,
          expected_subject varchar(255) NOT NULL,
          normalized_email varchar(320) NOT NULL,
          status varchar(32) NOT NULL DEFAULT 'pending_confirmation',
          browser_binding_hash varchar(64) NOT NULL,
          state_hash varchar(64),
          nonce_hash varchar(64),
          pkce_verifier_hash varchar(64),
          expires_at timestamptz NOT NULL,
          completed_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          version integer NOT NULL DEFAULT 1,
          CONSTRAINT ck_duplicate_resolution_provider CHECK (
            required_provider IN ('google', 'email')
          ),
          CONSTRAINT ck_duplicate_resolution_status CHECK (
            status IN ('pending_confirmation', 'completed', 'cancelled', 'expired', 'blocked')
          )
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE {S}.duplicate_resolution_email_tokens (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          intent_id uuid NOT NULL REFERENCES {S}.duplicate_resolution_intents(id) ON DELETE CASCADE,
          purpose varchar(32) NOT NULL DEFAULT 'resolve_duplicate_email',
          token_hash varchar(64) NOT NULL UNIQUE,
          expires_at timestamptz NOT NULL,
          used_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_duplicate_resolution_email_purpose CHECK (
            purpose = 'resolve_duplicate_email'
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_duplicate_resolution_initiator_status ON {S}.duplicate_resolution_intents(initiating_user_id, status)"
    )

    for table in ("duplicate_resolution_intents", "duplicate_resolution_email_tokens"):
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {S}.{table} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON {S}.{table} FROM {APP}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.{table} TO {R}")

    for table in (
        "users",
        "user_identities",
        "auth_sessions",
        "workspaces",
        "workspace_members",
        "health_profiles",
        "profile_permissions",
        "user_consents",
    ):
        op.execute(f"GRANT SELECT, UPDATE, DELETE ON {S}.{table} TO {R}")
    op.execute(f"GRANT INSERT ON {S}.audit_events TO {R}")
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_create_duplicate_resolution_intent(
          actor_user_id uuid,
          new_browser_binding_hash text,
          new_expires_at timestamptz
        ) RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          context_user_id uuid;
          candidate_user_id uuid;
          candidate_count integer;
          assessment jsonb;
          canonical_user_id uuid;
          absorbed_user_id uuid;
          required_provider text;
          expected_subject text;
          normalized_email text;
          new_intent_id uuid;
        BEGIN
          context_user_id := nullif(current_setting('app.current_user_id', true), '')::uuid;
          IF context_user_id IS NULL OR context_user_id <> actor_user_id THEN
            RETURN NULL;
          END IF;

          WITH actor_emails AS (
            SELECT lower(btrim(ui.subject)) AS email
            FROM {S}.user_identities ui
            WHERE ui.user_id = actor_user_id
              AND ui.provider = 'email'
              AND ui.claims ->> 'email_verified' = 'true'
            UNION
            SELECT lower(btrim(ui.claims ->> 'email')) AS email
            FROM {S}.user_identities ui
            WHERE ui.user_id = actor_user_id
              AND ui.provider = 'google'
              AND ui.claims ->> 'email_verified' = 'true'
          ),
          candidates AS (
            SELECT DISTINCT ui.user_id
            FROM {S}.user_identities ui
            JOIN actor_emails ae ON ae.email = CASE
              WHEN ui.provider = 'email' THEN lower(btrim(ui.subject))
              WHEN ui.provider = 'google' THEN lower(btrim(ui.claims ->> 'email'))
              ELSE NULL
            END
            WHERE ui.user_id <> actor_user_id
              AND ui.provider IN ('google', 'email')
              AND ui.claims ->> 'email_verified' = 'true'
          )
          SELECT count(*), min(user_id)
          INTO candidate_count, candidate_user_id
          FROM candidates;

          IF candidate_count <> 1 OR candidate_user_id IS NULL THEN
            RETURN jsonb_build_object(
              'available', false,
              'reason', CASE
                WHEN candidate_count = 0 THEN 'no_duplicate_candidate'
                ELSE 'multiple_duplicate_candidates'
              END
            );
          END IF;

          assessment := {S}.app_assess_duplicate_user_pair(actor_user_id, candidate_user_id);
          IF assessment IS NULL OR (assessment ->> 'eligible')::boolean IS NOT TRUE THEN
            RETURN jsonb_build_object(
              'available', false,
              'reason', coalesce(assessment ->> 'reason', 'assessment_failed')
            );
          END IF;

          canonical_user_id := (assessment ->> 'canonical_user_id')::uuid;
          absorbed_user_id := (assessment ->> 'absorbed_user_id')::uuid;

          SELECT
            ui.provider,
            ui.subject,
            CASE
              WHEN ui.provider = 'email' THEN lower(btrim(ui.subject))
              ELSE lower(btrim(ui.claims ->> 'email'))
            END
          INTO required_provider, expected_subject, normalized_email
          FROM {S}.user_identities ui
          WHERE ui.user_id = candidate_user_id
            AND ui.provider IN ('google', 'email')
            AND ui.claims ->> 'email_verified' = 'true'
            AND NOT EXISTS (
              SELECT 1
              FROM {S}.user_identities actor_identity
              WHERE actor_identity.user_id = actor_user_id
                AND actor_identity.provider = ui.provider
            )
          ORDER BY CASE ui.provider WHEN 'google' THEN 1 ELSE 2 END
          LIMIT 1;

          IF required_provider IS NULL THEN
            RETURN jsonb_build_object(
              'available', false,
              'reason', 'no_distinct_second_identity'
            );
          END IF;

          UPDATE {S}.duplicate_resolution_intents
          SET status = 'cancelled', version = version + 1
          WHERE initiating_user_id = actor_user_id
            AND status = 'pending_confirmation';

          INSERT INTO {S}.duplicate_resolution_intents (
            initiating_user_id, canonical_user_id, absorbed_user_id,
            required_provider, expected_subject, normalized_email,
            browser_binding_hash, expires_at
          ) VALUES (
            actor_user_id, canonical_user_id, absorbed_user_id,
            required_provider, expected_subject, normalized_email,
            new_browser_binding_hash, new_expires_at
          ) RETURNING id INTO new_intent_id;

          RETURN jsonb_build_object(
            'available', true,
            'intent_id', new_intent_id,
            'required_provider', required_provider,
            'canonical_is_current', canonical_user_id = actor_user_id
          );
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_issue_duplicate_resolution_email_token(
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
          i {S}.duplicate_resolution_intents%ROWTYPE;
        BEGIN
          SELECT dri.* INTO i
          FROM {S}.duplicate_resolution_intents dri
          WHERE dri.id = target_intent_id
          FOR UPDATE;

          IF i.id IS NULL
             OR i.status <> 'pending_confirmation'
             OR i.required_provider <> 'email'
             OR i.expires_at <= now()
             OR i.browser_binding_hash <> expected_browser_binding_hash THEN
            RETURN NULL;
          END IF;

          IF NOT EXISTS (
            SELECT 1 FROM {S}.user_identities ui
            WHERE ui.user_id IN (i.canonical_user_id, i.absorbed_user_id)
              AND ui.provider = 'email'
              AND ui.subject = i.expected_subject
              AND lower(btrim(ui.subject)) = i.normalized_email
              AND ui.claims ->> 'email_verified' = 'true'
          ) THEN
            RETURN NULL;
          END IF;

          DELETE FROM {S}.duplicate_resolution_email_tokens
          WHERE intent_id = i.id AND used_at IS NULL;

          INSERT INTO {S}.duplicate_resolution_email_tokens (
            intent_id, token_hash, expires_at
          ) VALUES (
            i.id, new_token_hash, least(new_expires_at, i.expires_at)
          );

          RETURN i.normalized_email;
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_prepare_duplicate_resolution_google(
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
          UPDATE {S}.duplicate_resolution_intents
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
        CREATE FUNCTION {S}.app_apply_duplicate_absorption(
          target_intent_id uuid
        ) RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          i {S}.duplicate_resolution_intents%ROWTYPE;
          assessment jsonb;
          canonical_id uuid;
          absorbed_id uuid;
        BEGIN
          SELECT dri.* INTO i
          FROM {S}.duplicate_resolution_intents dri
          WHERE dri.id = target_intent_id
          FOR UPDATE;

          IF i.id IS NULL OR i.absorbed_user_id IS NULL THEN RETURN NULL; END IF;
          IF i.status = 'completed' THEN
            RETURN jsonb_build_object(
              'intent_id', i.id,
              'canonical_user_id', i.canonical_user_id,
              'replayed', true
            );
          END IF;
          IF i.status <> 'pending_confirmation' OR i.expires_at <= now() THEN RETURN NULL; END IF;

          canonical_id := i.canonical_user_id;
          absorbed_id := i.absorbed_user_id;

          assessment := {S}.app_assess_duplicate_user_pair(canonical_id, absorbed_id);
          IF assessment IS NULL
             OR (assessment ->> 'eligible')::boolean IS NOT TRUE
             OR (assessment ->> 'canonical_user_id')::uuid <> canonical_id
             OR (assessment ->> 'absorbed_user_id')::uuid <> absorbed_id THEN
            UPDATE {S}.duplicate_resolution_intents
            SET status = 'blocked', version = version + 1
            WHERE id = i.id;
            RETURN NULL;
          END IF;

          PERFORM 1 FROM {S}.user_identities ui
          WHERE ui.user_id IN (canonical_id, absorbed_id)
          ORDER BY ui.id FOR UPDATE;

          IF EXISTS (
            SELECT 1
            FROM {S}.user_identities absorbed_identity
            JOIN {S}.user_identities canonical_identity
              ON canonical_identity.user_id = canonical_id
             AND canonical_identity.provider = absorbed_identity.provider
             AND canonical_identity.subject = absorbed_identity.subject
            WHERE absorbed_identity.user_id = absorbed_id
          ) THEN
            RETURN NULL;
          END IF;

          UPDATE {S}.auth_sessions
          SET revoked_at = coalesce(revoked_at, now()),
              user_id = canonical_id
          WHERE user_id = absorbed_id;

          UPDATE {S}.user_identities
          SET user_id = canonical_id
          WHERE user_id = absorbed_id;

          DELETE FROM {S}.profile_permissions pp
          USING {S}.health_profiles hp
          WHERE pp.profile_id = hp.id
            AND hp.owner_user_id = absorbed_id;

          DELETE FROM {S}.health_profiles
          WHERE owner_user_id = absorbed_id;

          DELETE FROM {S}.workspace_members wm
          USING {S}.workspaces w
          WHERE wm.workspace_id = w.id
            AND w.created_by_user_id = absorbed_id;

          DELETE FROM {S}.workspaces
          WHERE created_by_user_id = absorbed_id;

          DELETE FROM {S}.user_consents
          WHERE user_id = absorbed_id;

          UPDATE {S}.duplicate_resolution_intents
          SET status = 'completed', completed_at = now(), version = version + 1
          WHERE id = i.id AND status = 'pending_confirmation';

          DELETE FROM {S}.users
          WHERE id = absorbed_id;

          RETURN jsonb_build_object(
            'intent_id', i.id,
            'canonical_user_id', canonical_id,
            'absorbed_user_id', absorbed_id,
            'replayed', false
          );
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_complete_duplicate_resolution_email(
          resolution_token_hash text,
          expected_browser_binding_hash text
        ) RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          token_row {S}.duplicate_resolution_email_tokens%ROWTYPE;
          i {S}.duplicate_resolution_intents%ROWTYPE;
          result jsonb;
        BEGIN
          SELECT t.* INTO token_row
          FROM {S}.duplicate_resolution_email_tokens t
          WHERE t.token_hash = resolution_token_hash
            AND t.purpose = 'resolve_duplicate_email'
            AND t.expires_at > now()
          FOR UPDATE;
          IF token_row.id IS NULL THEN RETURN NULL; END IF;

          SELECT dri.* INTO i
          FROM {S}.duplicate_resolution_intents dri
          WHERE dri.id = token_row.intent_id
          FOR UPDATE;

          IF i.id IS NULL
             OR i.browser_binding_hash <> expected_browser_binding_hash
             OR i.required_provider <> 'email' THEN RETURN NULL; END IF;
          IF i.status = 'completed' THEN
            RETURN jsonb_build_object(
              'intent_id', i.id,
              'canonical_user_id', i.canonical_user_id,
              'replayed', true
            );
          END IF;
          IF i.status <> 'pending_confirmation'
             OR token_row.used_at IS NOT NULL
             OR i.expires_at <= now() THEN RETURN NULL; END IF;

          IF NOT EXISTS (
            SELECT 1 FROM {S}.user_identities ui
            WHERE ui.user_id IN (i.canonical_user_id, i.absorbed_user_id)
              AND ui.provider = 'email'
              AND ui.subject = i.expected_subject
              AND lower(btrim(ui.subject)) = i.normalized_email
              AND ui.claims ->> 'email_verified' = 'true'
          ) THEN RETURN NULL; END IF;

          UPDATE {S}.duplicate_resolution_email_tokens
          SET used_at = now()
          WHERE id = token_row.id;

          result := {S}.app_apply_duplicate_absorption(i.id);
          RETURN result;
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_complete_duplicate_resolution_google(
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
          i {S}.duplicate_resolution_intents%ROWTYPE;
        BEGIN
          SELECT dri.* INTO i
          FROM {S}.duplicate_resolution_intents dri
          WHERE dri.id = target_intent_id
          FOR UPDATE;

          IF i.id IS NULL
             OR i.browser_binding_hash <> expected_browser_binding_hash
             OR i.state_hash <> confirmed_state_hash
             OR i.nonce_hash <> confirmed_nonce_hash
             OR i.pkce_verifier_hash <> confirmed_pkce_verifier_hash
             OR i.required_provider <> 'google' THEN RETURN NULL; END IF;
          IF i.status = 'completed' THEN
            RETURN jsonb_build_object(
              'intent_id', i.id,
              'canonical_user_id', i.canonical_user_id,
              'replayed', true
            );
          END IF;
          IF i.status <> 'pending_confirmation' OR i.expires_at <= now() THEN RETURN NULL; END IF;

          IF confirmed_google_subject <> i.expected_subject
             OR lower(btrim(confirmed_google_email)) <> i.normalized_email
             OR NOT EXISTS (
               SELECT 1 FROM {S}.user_identities ui
               WHERE ui.user_id IN (i.canonical_user_id, i.absorbed_user_id)
                 AND ui.provider = 'google'
                 AND ui.subject = confirmed_google_subject
                 AND lower(btrim(ui.claims ->> 'email')) = i.normalized_email
                 AND ui.claims ->> 'email_verified' = 'true'
             ) THEN RETURN NULL; END IF;

          RETURN {S}.app_apply_duplicate_absorption(i.id);
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_record_duplicate_resolution_audit(
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
            'duplicate_resolution_intent', audit_intent_id::text,
            audit_ip, audit_user_agent, audit_metadata, now()
          )
        $$
        """
    )

    helper_signatures = (
        f"{S}.app_apply_duplicate_absorption(uuid)",
    )
    public_signatures = (
        f"{S}.app_create_duplicate_resolution_intent(uuid, text, timestamptz)",
        f"{S}.app_issue_duplicate_resolution_email_token(uuid, text, text, timestamptz)",
        f"{S}.app_prepare_duplicate_resolution_google(uuid, text, text, text, text)",
        f"{S}.app_complete_duplicate_resolution_email(text, text)",
        f"{S}.app_complete_duplicate_resolution_google(uuid, text, text, text, text, text, text)",
        f"{S}.app_record_duplicate_resolution_audit(text, text, uuid, text, text, text, jsonb)",
    )
    for signature in helper_signatures + public_signatures:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {R}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {APP}")
    for signature in public_signatures:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    signatures = (
        f"{S}.app_record_duplicate_resolution_audit(text, text, uuid, text, text, text, jsonb)",
        f"{S}.app_complete_duplicate_resolution_google(uuid, text, text, text, text, text, text)",
        f"{S}.app_complete_duplicate_resolution_email(text, text)",
        f"{S}.app_apply_duplicate_absorption(uuid)",
        f"{S}.app_prepare_duplicate_resolution_google(uuid, text, text, text, text)",
        f"{S}.app_issue_duplicate_resolution_email_token(uuid, text, text, timestamptz)",
        f"{S}.app_create_duplicate_resolution_intent(uuid, text, timestamptz)",
    )
    for signature in signatures:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
    op.execute(f"DROP TABLE IF EXISTS {S}.duplicate_resolution_email_tokens")
    op.execute(f"DROP TABLE IF EXISTS {S}.duplicate_resolution_intents")
