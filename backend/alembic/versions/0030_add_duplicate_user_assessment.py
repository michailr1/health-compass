"""Add conservative HC-026 duplicate-user assessment.

Revision ID: 0030
Revises: 0029
"""

from __future__ import annotations

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"


def upgrade() -> None:
    for table in (
        "users",
        "user_identities",
        "workspaces",
        "workspace_members",
        "health_profiles",
        "profile_permissions",
        "dashboard_snapshots",
        "body_measurements",
        "profile_audit_events",
        "user_consents",
    ):
        op.execute(f"GRANT SELECT ON {S}.{table} TO {R}")
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_duplicate_user_activity(target_user_id uuid)
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

          meaningful_count :=
            foreign_workspace_memberships
            + shared_workspace_members
            + foreign_profile_permissions
            + shared_profile_permissions
            + customized_profiles
            + dashboard_count
            + measurement_count
            + profile_audit_count
            + consent_count;

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
            'user_consents', consent_count
          );
        END
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_assess_duplicate_user_pair(
          first_user_id uuid,
          second_user_id uuid
        ) RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          first_user {S}.users%ROWTYPE;
          second_user {S}.users%ROWTYPE;
          first_activity jsonb;
          second_activity jsonb;
          shared_verified_email text;
          canonical_user_id uuid;
          absorbed_user_id uuid;
          eligible boolean := false;
          reason text;
        BEGIN
          IF first_user_id = second_user_id THEN
            RETURN NULL;
          END IF;

          PERFORM 1
          FROM {S}.users u
          WHERE u.id IN (first_user_id, second_user_id)
          ORDER BY u.id
          FOR UPDATE;

          SELECT u.* INTO first_user FROM {S}.users u WHERE u.id = first_user_id;
          SELECT u.* INTO second_user FROM {S}.users u WHERE u.id = second_user_id;
          IF first_user.id IS NULL OR second_user.id IS NULL THEN RETURN NULL; END IF;

          WITH first_emails AS (
            SELECT lower(btrim(ui.subject)) AS email
            FROM {S}.user_identities ui
            WHERE ui.user_id = first_user_id
              AND ui.provider = 'email'
              AND ui.claims ->> 'email_verified' = 'true'
            UNION
            SELECT lower(btrim(ui.claims ->> 'email')) AS email
            FROM {S}.user_identities ui
            WHERE ui.user_id = first_user_id
              AND ui.provider = 'google'
              AND ui.claims ->> 'email_verified' = 'true'
          ),
          second_emails AS (
            SELECT lower(btrim(ui.subject)) AS email
            FROM {S}.user_identities ui
            WHERE ui.user_id = second_user_id
              AND ui.provider = 'email'
              AND ui.claims ->> 'email_verified' = 'true'
            UNION
            SELECT lower(btrim(ui.claims ->> 'email')) AS email
            FROM {S}.user_identities ui
            WHERE ui.user_id = second_user_id
              AND ui.provider = 'google'
              AND ui.claims ->> 'email_verified' = 'true'
          )
          SELECT f.email INTO shared_verified_email
          FROM first_emails f
          JOIN second_emails s ON s.email = f.email
          WHERE f.email IS NOT NULL AND f.email <> ''
          LIMIT 1;

          IF shared_verified_email IS NULL THEN
            RETURN jsonb_build_object(
              'eligible', false,
              'reason', 'no_shared_verified_email'
            );
          END IF;

          first_activity := {S}.app_duplicate_user_activity(first_user_id);
          second_activity := {S}.app_duplicate_user_activity(second_user_id);

          IF (first_activity ->> 'is_empty')::boolean
             AND (second_activity ->> 'is_empty')::boolean THEN
            IF first_user.created_at <= second_user.created_at THEN
              canonical_user_id := first_user_id;
              absorbed_user_id := second_user_id;
            ELSE
              canonical_user_id := second_user_id;
              absorbed_user_id := first_user_id;
            END IF;
            eligible := true;
            reason := 'both_empty_oldest_wins';
          ELSIF (first_activity ->> 'is_empty')::boolean THEN
            canonical_user_id := second_user_id;
            absorbed_user_id := first_user_id;
            eligible := true;
            reason := 'first_user_empty';
          ELSIF (second_activity ->> 'is_empty')::boolean THEN
            canonical_user_id := first_user_id;
            absorbed_user_id := second_user_id;
            eligible := true;
            reason := 'second_user_empty';
          ELSE
            reason := 'both_users_have_meaningful_data';
          END IF;

          RETURN jsonb_build_object(
            'eligible', eligible,
            'reason', reason,
            'canonical_user_id', canonical_user_id,
            'absorbed_user_id', absorbed_user_id,
            'shared_verified_email', shared_verified_email,
            'first', first_activity,
            'second', second_activity
          );
        END
        $$
        """
    )

    signatures = (
        f"{S}.app_duplicate_user_activity(uuid)",
        f"{S}.app_assess_duplicate_user_pair(uuid, uuid)",
    )
    for signature in signatures:
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {R}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    signatures = (
        f"{S}.app_assess_duplicate_user_pair(uuid, uuid)",
        f"{S}.app_duplicate_user_activity(uuid)",
    )
    for signature in signatures:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
