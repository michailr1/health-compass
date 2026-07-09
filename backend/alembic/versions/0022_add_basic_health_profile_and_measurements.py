"""Add Basic Health Profile fields, measurements, audit, and consent gate.

Revision ID: 0022
Revises: 0021
"""

from __future__ import annotations

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_roles
            WHERE rolname = '{R}' AND rolbypassrls AND NOT rolcanlogin
          ) THEN
            RAISE EXCEPTION
              'Provision first: CREATE ROLE {R} NOLOGIN BYPASSRLS; '
              'GRANT {R} TO health_compass_migrator';
          END IF;

          IF EXISTS (
            SELECT 1 FROM {S}.health_profiles
            WHERE sex IS NOT NULL
              AND sex NOT IN ('male', 'female', 'not_specified')
          ) THEN
            RAISE EXCEPTION
              'Cannot add health_profiles sex constraint: unsupported values exist';
          END IF;
        END $$;
        """
    )

    op.execute(f"ALTER TABLE {S}.health_profiles ADD COLUMN height_cm numeric(5,2)")
    op.execute(f"ALTER TABLE {S}.health_profiles ADD COLUMN timezone varchar(64)")
    op.execute(
        f"ALTER TABLE {S}.health_profiles "
        "ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now()"
    )
    op.execute(
        f"ALTER TABLE {S}.health_profiles ADD CONSTRAINT ck_health_profiles_sex "
        "CHECK (sex IS NULL OR sex IN ('male', 'female', 'not_specified'))"
    )
    op.execute(
        f"ALTER TABLE {S}.health_profiles ADD CONSTRAINT ck_health_profiles_height_cm "
        "CHECK (height_cm IS NULL OR height_cm > 0)"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.body_measurements (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          measurement_type varchar(32) NOT NULL,
          value numeric(12,4) NOT NULL,
          unit varchar(16) NOT NULL,
          measured_at timestamptz NOT NULL,
          source_type varchar(32) NOT NULL,
          confirmation_status varchar(32) NOT NULL,
          created_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          voided_at timestamptz NULL,
          voided_by_user_id uuid NULL REFERENCES {S}.users(id),
          void_reason varchar(500) NULL,
          CONSTRAINT ck_body_measurements_type CHECK (measurement_type = 'weight'),
          CONSTRAINT ck_body_measurements_unit CHECK (unit = 'kg'),
          CONSTRAINT ck_body_measurements_value CHECK (value > 0),
          CONSTRAINT ck_body_measurements_source CHECK (source_type = 'manual'),
          CONSTRAINT ck_body_measurements_confirmation CHECK (confirmation_status = 'confirmed'),
          CONSTRAINT ck_body_measurements_void_fields CHECK (
            (voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL)
            OR
            (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL AND void_reason IS NOT NULL)
          )
        )
        """
    )
    op.execute(
        f"""
        CREATE INDEX ix_body_measurements_active_profile_type_time
        ON {S}.body_measurements
          (profile_id, measurement_type, measured_at DESC)
        WHERE voided_at IS NULL
        """
    )

    op.execute(
        f"""
        CREATE TABLE {S}.profile_audit_events (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          actor_user_id uuid NOT NULL REFERENCES {S}.users(id),
          entity_type varchar(64) NOT NULL,
          entity_id uuid NOT NULL,
          action varchar(64) NOT NULL,
          changed_fields jsonb NOT NULL,
          request_id varchar(128) NULL,
          occurred_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_profile_audit_action CHECK (
            action IN (
              'profile.updated',
              'body_measurement.created',
              'body_measurement.voided'
            )
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_profile_audit_events_profile_time "
        f"ON {S}.profile_audit_events (profile_id, occurred_at DESC)"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.user_consents (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL REFERENCES {S}.users(id),
          consent_type varchar(64) NOT NULL,
          document_version varchar(32) NOT NULL,
          accepted_at timestamptz NOT NULL,
          revoked_at timestamptz NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_user_consents_type CHECK (
            consent_type = 'health_data_processing'
          )
        )
        """
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX ux_user_consents_active
        ON {S}.user_consents (user_id, consent_type)
        WHERE revoked_at IS NULL
        """
    )
    op.execute(
        f"CREATE INDEX ix_user_consents_user_time "
        f"ON {S}.user_consents (user_id, accepted_at DESC)"
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_can_edit_profile(target_profile_id uuid)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
          SELECT EXISTS (
            SELECT 1
            FROM {S}.health_profiles hp
            WHERE hp.id = target_profile_id
              AND hp.owner_user_id = {S}.app_current_user_id()
          ) OR EXISTS (
            SELECT 1
            FROM {S}.profile_permissions pp
            WHERE pp.profile_id = target_profile_id
              AND pp.user_id = {S}.app_current_user_id()
              AND pp.permission IN ('owner', 'edit')
          )
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {S}.app_can_edit_profile(uuid) OWNER TO {R}")
    op.execute(f"REVOKE ALL ON FUNCTION {S}.app_can_edit_profile(uuid) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {S}.app_can_edit_profile(uuid) TO {APP}")

    op.execute(
        f"CREATE POLICY profiles_edit_update ON {S}.health_profiles "
        f"FOR UPDATE USING ({S}.app_can_edit_profile(id)) "
        f"WITH CHECK ({S}.app_can_edit_profile(id))"
    )

    for table in ["body_measurements", "profile_audit_events", "user_consents"]:
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")

    op.execute(
        f"CREATE POLICY body_measurements_select ON {S}.body_measurements "
        f"FOR SELECT USING ({S}.app_can_view_profile(profile_id))"
    )
    op.execute(
        f"CREATE POLICY body_measurements_insert ON {S}.body_measurements "
        f"FOR INSERT WITH CHECK ("
        f"created_by_user_id = {S}.app_current_user_id() "
        f"AND {S}.app_can_edit_profile(profile_id))"
    )
    op.execute(
        f"CREATE POLICY body_measurements_void_update ON {S}.body_measurements "
        f"FOR UPDATE USING ({S}.app_can_edit_profile(profile_id)) "
        f"WITH CHECK ("
        f"{S}.app_can_edit_profile(profile_id) "
        f"AND voided_at IS NOT NULL "
        f"AND voided_by_user_id = {S}.app_current_user_id() "
        f"AND void_reason IS NOT NULL)"
    )

    op.execute(
        f"CREATE POLICY profile_audit_events_select ON {S}.profile_audit_events "
        f"FOR SELECT USING ({S}.app_can_view_profile(profile_id))"
    )
    op.execute(
        f"CREATE POLICY profile_audit_events_insert ON {S}.profile_audit_events "
        f"FOR INSERT WITH CHECK ("
        f"actor_user_id = {S}.app_current_user_id() "
        f"AND {S}.app_can_edit_profile(profile_id))"
    )

    op.execute(
        f"CREATE POLICY user_consents_select ON {S}.user_consents "
        f"FOR SELECT USING (user_id = {S}.app_current_user_id())"
    )
    op.execute(
        f"CREATE POLICY user_consents_insert ON {S}.user_consents "
        f"FOR INSERT WITH CHECK (user_id = {S}.app_current_user_id())"
    )
    op.execute(
        f"CREATE POLICY user_consents_update ON {S}.user_consents "
        f"FOR UPDATE USING (user_id = {S}.app_current_user_id()) "
        f"WITH CHECK (user_id = {S}.app_current_user_id())"
    )

    op.execute(f"REVOKE UPDATE ON {S}.health_profiles FROM {APP}")
    op.execute(
        f"GRANT UPDATE (display_name, date_of_birth, sex, height_cm, timezone, updated_at) "
        f"ON {S}.health_profiles TO {APP}"
    )

    op.execute(f"GRANT SELECT, INSERT ON {S}.body_measurements TO {APP}")
    op.execute(
        f"GRANT UPDATE (voided_at, voided_by_user_id, void_reason) "
        f"ON {S}.body_measurements TO {APP}"
    )
    op.execute(f"GRANT SELECT, INSERT ON {S}.profile_audit_events TO {APP}")
    op.execute(f"GRANT SELECT, INSERT ON {S}.user_consents TO {APP}")
    op.execute(f"GRANT UPDATE (revoked_at) ON {S}.user_consents TO {APP}")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE (revoked_at) ON {S}.user_consents FROM {APP}")
    op.execute(f"REVOKE SELECT, INSERT ON {S}.user_consents FROM {APP}")
    op.execute(f"REVOKE SELECT, INSERT ON {S}.profile_audit_events FROM {APP}")
    op.execute(
        f"REVOKE UPDATE (voided_at, voided_by_user_id, void_reason) "
        f"ON {S}.body_measurements FROM {APP}"
    )
    op.execute(f"REVOKE SELECT, INSERT ON {S}.body_measurements FROM {APP}")

    op.execute(f"DROP POLICY IF EXISTS user_consents_update ON {S}.user_consents")
    op.execute(f"DROP POLICY IF EXISTS user_consents_insert ON {S}.user_consents")
    op.execute(f"DROP POLICY IF EXISTS user_consents_select ON {S}.user_consents")
    op.execute(
        f"DROP POLICY IF EXISTS profile_audit_events_insert ON {S}.profile_audit_events"
    )
    op.execute(
        f"DROP POLICY IF EXISTS profile_audit_events_select ON {S}.profile_audit_events"
    )
    op.execute(
        f"DROP POLICY IF EXISTS body_measurements_void_update ON {S}.body_measurements"
    )
    op.execute(f"DROP POLICY IF EXISTS body_measurements_insert ON {S}.body_measurements")
    op.execute(f"DROP POLICY IF EXISTS body_measurements_select ON {S}.body_measurements")
    op.execute(f"DROP POLICY IF EXISTS profiles_edit_update ON {S}.health_profiles")

    op.execute(f"REVOKE EXECUTE ON FUNCTION {S}.app_can_edit_profile(uuid) FROM {APP}")
    op.execute(f"DROP FUNCTION IF EXISTS {S}.app_can_edit_profile(uuid)")

    op.execute(f"DROP TABLE {S}.user_consents")
    op.execute(f"DROP TABLE {S}.profile_audit_events")
    op.execute(f"DROP TABLE {S}.body_measurements")

    op.execute(
        f"ALTER TABLE {S}.health_profiles DROP CONSTRAINT ck_health_profiles_height_cm"
    )
    op.execute(f"ALTER TABLE {S}.health_profiles DROP CONSTRAINT ck_health_profiles_sex")
    op.execute(f"ALTER TABLE {S}.health_profiles DROP COLUMN updated_at")
    op.execute(f"ALTER TABLE {S}.health_profiles DROP COLUMN timezone")
    op.execute(f"ALTER TABLE {S}.health_profiles DROP COLUMN height_cm")
