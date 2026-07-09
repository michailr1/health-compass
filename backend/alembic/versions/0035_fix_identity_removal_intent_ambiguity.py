"""Qualify identity-removal columns to avoid PL/pgSQL name ambiguity.

Revision ID: 0035
Revises: 0034
"""

from __future__ import annotations

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"
SIG = f"{S}.app_create_identity_removal_intent(uuid, uuid, text, timestamptz)"


def _create_function() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_create_identity_removal_intent(
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
          PERFORM 1
          FROM {S}.user_identities ui
          WHERE ui.user_id = actor_user_id
          ORDER BY ui.id
          FOR UPDATE;

          SELECT count(*) INTO identity_count
          FROM {S}.user_identities ui
          WHERE ui.user_id = actor_user_id;

          IF identity_count <= 1 THEN RETURN NULL; END IF;

          SELECT ui.* INTO target_identity
          FROM {S}.user_identities ui
          WHERE ui.id = target_identity_id
            AND ui.user_id = actor_user_id;

          IF target_identity.id IS NULL
             OR target_identity.provider NOT IN ('google', 'email') THEN
            RETURN NULL;
          END IF;

          SELECT ui.provider INTO remaining_provider
          FROM {S}.user_identities ui
          WHERE ui.user_id = actor_user_id
            AND ui.id <> target_identity.id
            AND ui.provider IN ('google', 'email')
            AND ui.claims ->> 'email_verified' = 'true'
          ORDER BY CASE ui.provider WHEN 'google' THEN 1 ELSE 2 END
          LIMIT 1;

          IF remaining_provider IS NULL OR remaining_provider = target_identity.provider THEN
            RETURN NULL;
          END IF;

          UPDATE {S}.identity_removal_intents AS iri
          SET status = 'cancelled', version = iri.version + 1
          WHERE iri.user_id = actor_user_id
            AND iri.target_identity_id = target_identity.id
            AND iri.status = 'pending_confirmation';

          INSERT INTO {S}.identity_removal_intents (
            user_id, target_identity_id, target_provider, required_provider,
            browser_binding_hash, expires_at
          ) VALUES (
            actor_user_id, target_identity.id, target_identity.provider, remaining_provider,
            new_browser_binding_hash, new_expires_at
          ) RETURNING identity_removal_intents.id INTO new_intent_id;

          RETURN jsonb_build_object(
            'intent_id', new_intent_id,
            'target_provider', target_identity.provider,
            'required_provider', remaining_provider
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
    _create_function()


def downgrade() -> None:
    # The qualified implementation is signature- and behavior-compatible with
    # revision 0029, so keep the safe definition across a one-step downgrade.
    _create_function()
