"""Avoid non-portable UUID aggregation in HC-026 candidate lookup.

Revision ID: 0034
Revises: 0033
"""

from __future__ import annotations

from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"
SIG = f"{S}.app_create_duplicate_resolution_intent(uuid, text, timestamptz)"


def _create_function(use_uuid_aggregate: bool) -> None:
    candidate_sql = (
        "SELECT count(*), min(user_id) INTO candidate_count, candidate_user_id FROM candidates;"
        if use_uuid_aggregate
        else """
          SELECT count(*) INTO candidate_count FROM candidates;
          SELECT c.user_id INTO candidate_user_id
          FROM candidates c
          ORDER BY c.user_id
          LIMIT 1;
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_create_duplicate_resolution_intent(
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

          CREATE TEMP TABLE IF NOT EXISTS pg_temp.hc_duplicate_candidates (
            user_id uuid PRIMARY KEY
          ) ON COMMIT DROP;
          TRUNCATE pg_temp.hc_duplicate_candidates;

          INSERT INTO pg_temp.hc_duplicate_candidates (user_id)
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
          )
          SELECT DISTINCT ui.user_id
          FROM {S}.user_identities ui
          JOIN actor_emails ae ON ae.email = CASE
            WHEN ui.provider = 'email' THEN lower(btrim(ui.subject))
            WHEN ui.provider = 'google' THEN lower(btrim(ui.claims ->> 'email'))
            ELSE NULL
          END
          WHERE ui.user_id <> actor_user_id
            AND ui.provider IN ('google', 'email')
            AND ui.claims ->> 'email_verified' = 'true';

          WITH candidates AS (
            SELECT user_id FROM pg_temp.hc_duplicate_candidates
          )
          {candidate_sql}

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
    op.execute(f"ALTER FUNCTION {SIG} OWNER TO {R}")
    op.execute(f"REVOKE ALL ON FUNCTION {SIG} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {SIG} FROM {APP}")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIG} TO {APP}")


def upgrade() -> None:
    _create_function(use_uuid_aggregate=False)


def downgrade() -> None:
    _create_function(use_uuid_aggregate=True)
