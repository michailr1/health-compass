"""Count review/intake rows as meaningful duplicate-user activity.

HC-015 Slice B (CR-02/FBL-02): ``app_duplicate_user_activity`` predates the
``profile_clinical_reviews`` (0039) and ``profile_intake_decisions`` (0045)
tables, so an account holding only such rows was classified as empty and
absorption then failed on the RESTRICT foreign keys to ``health_profiles``.

This revision:

1. grants the definer role SELECT on both tables;
2. recreates ``app_duplicate_user_activity`` with per-table counts for both;
3. recreates ``app_apply_duplicate_absorption`` with a foreign-key safety net
   so that any future schema drift marks the intent ``blocked`` and returns a
   controlled NULL instead of surfacing an unhandled FK violation.

Revision ID: 0046
Revises: 0045
"""

from __future__ import annotations

from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"
ACTIVITY_SIG = f"{S}.app_duplicate_user_activity(uuid)"
ABSORPTION_SIG = f"{S}.app_apply_duplicate_absorption(uuid)"

NEW_TABLES = ("profile_clinical_reviews", "profile_intake_decisions")


def _create_activity_function(*, include_reviews_and_intake: bool) -> None:
    review_declarations = """
          clinical_review_count integer;
          intake_decision_count integer;
    """ if include_reviews_and_intake else ""

    review_queries = f"""
          SELECT count(*) INTO clinical_review_count
          FROM {S}.profile_clinical_reviews pcr
          LEFT JOIN {S}.health_profiles hp ON hp.id = pcr.profile_id
          WHERE hp.owner_user_id = target_user_id
             OR pcr.reviewed_by_user_id = target_user_id;

          SELECT count(*) INTO intake_decision_count
          FROM {S}.profile_intake_decisions pid
          LEFT JOIN {S}.health_profiles hp ON hp.id = pid.profile_id
          WHERE hp.owner_user_id = target_user_id
             OR pid.decided_by_user_id = target_user_id;
    """ if include_reviews_and_intake else ""

    review_sum = """
            + clinical_review_count
            + intake_decision_count
    """ if include_reviews_and_intake else ""

    review_json = """
            'profile_clinical_reviews', clinical_review_count,
            'profile_intake_decisions', intake_decision_count,
    """ if include_reviews_and_intake else ""

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_duplicate_user_activity(target_user_id uuid)
        RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          workspace_count integer;
          owned_profile_count integer;
          foreign_workspace_memberships integer;
          shared_workspace_members integer;
          foreign_profile_permissions integer;
          shared_profile_permissions integer;
          customized_profiles integer;
          dashboard_count integer;
          measurement_count integer;
          profile_audit_count integer;
          consent_count integer;
          condition_count integer;
          allergy_count integer;
          medication_count integer;
          supplement_count integer;
          clinical_safety_flag_count integer;
          {review_declarations}
          meaningful_count integer;
          is_empty boolean;
        BEGIN
          SELECT count(*) INTO workspace_count
          FROM {S}.workspaces w
          WHERE w.created_by_user_id = target_user_id;

          SELECT count(*) INTO owned_profile_count
          FROM {S}.health_profiles hp
          WHERE hp.owner_user_id = target_user_id;

          SELECT count(*) INTO foreign_workspace_memberships
          FROM {S}.workspace_members wm
          JOIN {S}.workspaces w ON w.id = wm.workspace_id
          WHERE wm.user_id = target_user_id
            AND w.created_by_user_id <> target_user_id;

          SELECT count(*) INTO shared_workspace_members
          FROM {S}.workspace_members wm
          JOIN {S}.workspaces w ON w.id = wm.workspace_id
          WHERE w.created_by_user_id = target_user_id
            AND wm.user_id <> target_user_id;

          SELECT count(*) INTO foreign_profile_permissions
          FROM {S}.profile_permissions pp
          JOIN {S}.health_profiles hp ON hp.id = pp.profile_id
          WHERE pp.user_id = target_user_id
            AND hp.owner_user_id <> target_user_id;

          SELECT count(*) INTO shared_profile_permissions
          FROM {S}.profile_permissions pp
          JOIN {S}.health_profiles hp ON hp.id = pp.profile_id
          WHERE hp.owner_user_id = target_user_id
            AND pp.user_id <> target_user_id;

          SELECT count(*) INTO customized_profiles
          FROM {S}.health_profiles hp
          WHERE hp.owner_user_id = target_user_id
            AND (
              hp.date_of_birth IS NOT NULL
              OR hp.sex IS NOT NULL
              OR hp.height_cm IS NOT NULL
              OR hp.timezone IS NOT NULL
            );

          SELECT count(*) INTO dashboard_count
          FROM {S}.dashboard_snapshots ds
          JOIN {S}.health_profiles hp ON hp.id = ds.profile_id
          WHERE hp.owner_user_id = target_user_id;

          SELECT count(*) INTO measurement_count
          FROM {S}.body_measurements bm
          LEFT JOIN {S}.health_profiles hp ON hp.id = bm.profile_id
          WHERE hp.owner_user_id = target_user_id
             OR bm.created_by_user_id = target_user_id
             OR bm.voided_by_user_id = target_user_id;

          SELECT count(*) INTO profile_audit_count
          FROM {S}.profile_audit_events pae
          LEFT JOIN {S}.health_profiles hp ON hp.id = pae.profile_id
          WHERE hp.owner_user_id = target_user_id
             OR pae.actor_user_id = target_user_id;

          SELECT count(*) INTO consent_count
          FROM {S}.user_consents uc
          WHERE uc.user_id = target_user_id;

          SELECT count(*) INTO condition_count
          FROM {S}.profile_conditions pc
          LEFT JOIN {S}.health_profiles hp ON hp.id = pc.profile_id
          WHERE hp.owner_user_id = target_user_id
             OR pc.created_by_user_id = target_user_id
             OR pc.voided_by_user_id = target_user_id;

          SELECT count(*) INTO allergy_count
          FROM {S}.profile_allergies pa
          LEFT JOIN {S}.health_profiles hp ON hp.id = pa.profile_id
          WHERE hp.owner_user_id = target_user_id
             OR pa.created_by_user_id = target_user_id
             OR pa.voided_by_user_id = target_user_id;

          SELECT count(*) INTO medication_count
          FROM {S}.profile_medications pm
          LEFT JOIN {S}.health_profiles hp ON hp.id = pm.profile_id
          WHERE hp.owner_user_id = target_user_id
             OR pm.created_by_user_id = target_user_id
             OR pm.voided_by_user_id = target_user_id;

          SELECT count(*) INTO supplement_count
          FROM {S}.profile_supplements ps
          LEFT JOIN {S}.health_profiles hp ON hp.id = ps.profile_id
          WHERE hp.owner_user_id = target_user_id
             OR ps.created_by_user_id = target_user_id
             OR ps.voided_by_user_id = target_user_id;

          SELECT count(*) INTO clinical_safety_flag_count
          FROM {S}.profile_clinical_safety_flags pf
          LEFT JOIN {S}.health_profiles hp ON hp.id = pf.profile_id
          WHERE hp.owner_user_id = target_user_id
             OR pf.created_by_user_id = target_user_id
             OR pf.voided_by_user_id = target_user_id;

          {review_queries}

          meaningful_count :=
            foreign_workspace_memberships
            + shared_workspace_members
            + foreign_profile_permissions
            + shared_profile_permissions
            + customized_profiles
            + dashboard_count
            + measurement_count
            + profile_audit_count
            + consent_count
            + condition_count
            + allergy_count
            + medication_count
            + supplement_count
            + clinical_safety_flag_count
            {review_sum};

          is_empty := (
            workspace_count = 1
            AND owned_profile_count = 1
            AND meaningful_count = 0
            AND EXISTS (
              SELECT 1
              FROM {S}.workspace_members wm
              JOIN {S}.workspaces w ON w.id = wm.workspace_id
              WHERE wm.user_id = target_user_id
                AND w.created_by_user_id = target_user_id
                AND wm.role = 'owner'
            )
            AND EXISTS (
              SELECT 1
              FROM {S}.profile_permissions pp
              JOIN {S}.health_profiles hp ON hp.id = pp.profile_id
              WHERE pp.user_id = target_user_id
                AND hp.owner_user_id = target_user_id
                AND pp.permission = 'owner'
            )
          );

          RETURN jsonb_build_object(
            'user_id', target_user_id,
            'is_empty', is_empty,
            'workspace_count', workspace_count,
            'owned_profile_count', owned_profile_count,
            'meaningful_count', meaningful_count,
            'foreign_workspace_memberships', foreign_workspace_memberships,
            'shared_workspace_members', shared_workspace_members,
            'foreign_profile_permissions', foreign_profile_permissions,
            'shared_profile_permissions', shared_profile_permissions,
            'customized_profiles', customized_profiles,
            'dashboard_snapshots', dashboard_count,
            'body_measurements', measurement_count,
            'profile_audit_events', profile_audit_count,
            'profile_conditions', condition_count,
            'profile_allergies', allergy_count,
            'profile_medications', medication_count,
            'profile_supplements', supplement_count,
            'profile_clinical_safety_flags', clinical_safety_flag_count,
            {review_json}
            'user_consents', consent_count
          );
        END
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {ACTIVITY_SIG} OWNER TO {R}")
    op.execute(f"REVOKE ALL ON FUNCTION {ACTIVITY_SIG} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {ACTIVITY_SIG} FROM {APP}")


def _create_absorption_function(*, with_fk_safety_net: bool) -> None:
    body = f"""
          canonical_id := i.canonical_user_id;
          absorbed_id := i.absorbed_user_id;
          PERFORM set_config('app.current_user_id', i.initiating_user_id::text, true);

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
    """

    if with_fk_safety_net:
        body = f"""
          BEGIN
            {body}
          EXCEPTION WHEN foreign_key_violation THEN
            -- Meaningful rows still reference the absorbed account. The
            -- activity assessment should have blocked this earlier; treat it
            -- as a controlled conflict, never delete the referencing data.
            UPDATE {S}.duplicate_resolution_intents
            SET status = 'blocked', version = version + 1
            WHERE id = i.id;
            RETURN NULL;
          END;
    """

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

          {body}
        END
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {ABSORPTION_SIG} OWNER TO {R}")
    op.execute(f"REVOKE ALL ON FUNCTION {ABSORPTION_SIG} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {ABSORPTION_SIG} FROM {APP}")


def upgrade() -> None:
    for table in NEW_TABLES:
        op.execute(f"GRANT SELECT ON {S}.{table} TO {R}")
    _create_activity_function(include_reviews_and_intake=True)
    _create_absorption_function(with_fk_safety_net=True)


def downgrade() -> None:
    _create_absorption_function(with_fk_safety_net=False)
    _create_activity_function(include_reviews_and_intake=False)
    for table in NEW_TABLES:
        op.execute(f"REVOKE SELECT ON {S}.{table} FROM {R}")
