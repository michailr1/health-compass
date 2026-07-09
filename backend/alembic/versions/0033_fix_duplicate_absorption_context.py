"""Restore the protected initiator context during HC-026 absorption.

Revision ID: 0033
Revises: 0032
"""

from __future__ import annotations

from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"
SIG = f"{S}.app_apply_duplicate_absorption(uuid)"


def _create_function(with_context_restore: bool) -> None:
    context_sql = (
        "PERFORM set_config('app.current_user_id', i.initiating_user_id::text, true);"
        if with_context_restore
        else ""
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_apply_duplicate_absorption(
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
          IF i.status <> 'pending_confirmation'
             OR i.expires_at <= now()
             OR i.initiating_user_id IS NULL THEN
            RETURN NULL;
          END IF;

          canonical_id := i.canonical_user_id;
          absorbed_id := i.absorbed_user_id;
          {context_sql}

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
    op.execute(f"ALTER FUNCTION {SIG} OWNER TO {R}")
    op.execute(f"REVOKE ALL ON FUNCTION {SIG} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {SIG} FROM {APP}")


def upgrade() -> None:
    _create_function(with_context_restore=True)


def downgrade() -> None:
    _create_function(with_context_restore=False)
