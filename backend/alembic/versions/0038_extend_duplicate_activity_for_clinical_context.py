"""Include Clinical Context history in HC-026 duplicate-user assessment.

Revision ID: 0038
Revises: 0037
"""

from __future__ import annotations

from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"
SIG = f"{S}.app_duplicate_user_activity(uuid)"


def _create_function(*, include_clinical: bool) -> None:
    clinical_declarations = """
          condition_count integer;
          allergy_count integer;
          medication_count integer;
          supplement_count integer;
          clinical_safety_flag_count integer;
    """ if include_clinical else ""

    clinical_queries = f"""
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
    """ if include_clinical else ""

    clinical_sum = """
            + condition_count
            + allergy_count
            + medication_count
            + supplement_count
            + clinical_safety_flag_count
    """ if include_clinical else ""

    clinical_json = """
            'profile_conditions', condition_count,
            'profile_allergies', allergy_count,
            'profile_medications', medication_count,
            'profile_supplements', supplement_count,
            'profile_clinical_safety_flags', clinical_safety_flag_count,
    """ if include_clinical else ""

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
          {clinical_declarations}
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

          {clinical_queries}

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
            {clinical_sum};

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
            {clinical_json}
            'user_consents', consent_count
          );
        END
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {SIG} OWNER TO {R}")
    op.execute(f"REVOKE ALL ON FUNCTION {SIG} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {SIG} FROM {APP}")


def upgrade() -> None:
    for table in (
        "profile_conditions",
        "profile_allergies",
        "profile_medications",
        "profile_supplements",
        "profile_clinical_safety_flags",
    ):
        op.execute(f"GRANT SELECT ON {S}.{table} TO {R}")
    _create_function(include_clinical=True)


def downgrade() -> None:
    _create_function(include_clinical=False)
    for table in (
        "profile_conditions",
        "profile_allergies",
        "profile_medications",
        "profile_supplements",
        "profile_clinical_safety_flags",
    ):
        op.execute(f"REVOKE SELECT ON {S}.{table} FROM {R}")
