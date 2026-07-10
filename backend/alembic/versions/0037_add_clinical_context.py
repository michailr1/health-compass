"""Add Clinical Context Slice 2 schema and RLS foundation.

Revision ID: 0037
Revises: 0036
"""

from __future__ import annotations

from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"

CLINICAL_TABLES = (
    "profile_conditions",
    "profile_allergies",
    "profile_medications",
    "profile_supplements",
    "profile_clinical_safety_flags",
)


def _enable_rls_and_grant(table: str, update_columns: str) -> None:
    op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_select ON {S}.{table} "
        f"FOR SELECT USING ({S}.app_can_view_profile(profile_id))"
    )
    op.execute(
        f"CREATE POLICY {table}_insert ON {S}.{table} "
        f"FOR INSERT WITH CHECK ("
        f"created_by_user_id = {S}.app_current_user_id() "
        f"AND {S}.app_can_edit_profile(profile_id))"
    )
    op.execute(
        f"CREATE POLICY {table}_update ON {S}.{table} "
        f"FOR UPDATE USING ({S}.app_can_edit_profile(profile_id)) "
        f"WITH CHECK ({S}.app_can_edit_profile(profile_id))"
    )
    op.execute(f"GRANT SELECT, INSERT ON {S}.{table} TO {APP}")
    op.execute(f"GRANT UPDATE ({update_columns}) ON {S}.{table} TO {APP}")


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_roles
            WHERE rolname = '{R}' AND rolbypassrls AND NOT rolcanlogin
          ) THEN
            RAISE EXCEPTION
              'Provision first: CREATE ROLE {R} NOLOGIN BYPASSRLS; '
              'GRANT {R} TO health_compass_migrator';
          END IF;
        END $$;
        """
    )

    op.execute(
        f"""
        CREATE TABLE {S}.profile_conditions (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          display_name varchar(255) NOT NULL,
          code_system varchar(64) NULL,
          code varchar(128) NULL,
          clinical_status varchar(32) NOT NULL,
          onset_date date NULL,
          resolved_date date NULL,
          notes varchar(2000) NULL,
          source_type varchar(32) NOT NULL,
          confirmation_status varchar(32) NOT NULL,
          created_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          voided_at timestamptz NULL,
          voided_by_user_id uuid NULL REFERENCES {S}.users(id),
          void_reason varchar(500) NULL,
          CONSTRAINT ck_profile_conditions_name CHECK (btrim(display_name) <> ''),
          CONSTRAINT ck_profile_conditions_status CHECK (
            clinical_status IN ('active', 'resolved', 'inactive', 'unknown')
          ),
          CONSTRAINT ck_profile_conditions_dates CHECK (
            resolved_date IS NULL OR onset_date IS NULL OR resolved_date >= onset_date
          ),
          CONSTRAINT ck_profile_conditions_source CHECK (
            source_type IN ('manual', 'document')
          ),
          CONSTRAINT ck_profile_conditions_confirmation CHECK (
            confirmation_status IN ('confirmed', 'needs_review')
          ),
          CONSTRAINT ck_profile_conditions_source_confirmation CHECK (
            source_type <> 'manual' OR confirmation_status = 'confirmed'
          ),
          CONSTRAINT ck_profile_conditions_void CHECK (
            (voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL)
            OR
            (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL
             AND void_reason IS NOT NULL AND btrim(void_reason) <> '')
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_profile_conditions_profile_status "
        f"ON {S}.profile_conditions (profile_id, clinical_status, updated_at DESC)"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.profile_allergies (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          substance_name varchar(255) NOT NULL,
          code_system varchar(64) NULL,
          code varchar(128) NULL,
          allergy_type varchar(32) NOT NULL,
          reaction varchar(500) NULL,
          severity varchar(32) NULL,
          clinical_status varchar(32) NOT NULL,
          source_type varchar(32) NOT NULL,
          confirmation_status varchar(32) NOT NULL,
          created_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          voided_at timestamptz NULL,
          voided_by_user_id uuid NULL REFERENCES {S}.users(id),
          void_reason varchar(500) NULL,
          CONSTRAINT ck_profile_allergies_name CHECK (btrim(substance_name) <> ''),
          CONSTRAINT ck_profile_allergies_type CHECK (
            allergy_type IN ('allergy', 'intolerance', 'unknown')
          ),
          CONSTRAINT ck_profile_allergies_severity CHECK (
            severity IS NULL OR severity IN ('mild', 'moderate', 'severe', 'unknown')
          ),
          CONSTRAINT ck_profile_allergies_status CHECK (
            clinical_status IN ('active', 'inactive', 'resolved', 'unknown')
          ),
          CONSTRAINT ck_profile_allergies_source CHECK (
            source_type IN ('manual', 'document')
          ),
          CONSTRAINT ck_profile_allergies_confirmation CHECK (
            confirmation_status IN ('confirmed', 'needs_review')
          ),
          CONSTRAINT ck_profile_allergies_source_confirmation CHECK (
            source_type <> 'manual' OR confirmation_status = 'confirmed'
          ),
          CONSTRAINT ck_profile_allergies_void CHECK (
            (voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL)
            OR
            (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL
             AND void_reason IS NOT NULL AND btrim(void_reason) <> '')
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_profile_allergies_profile_status "
        f"ON {S}.profile_allergies (profile_id, clinical_status, updated_at DESC)"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.profile_medications (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          display_name varchar(255) NOT NULL,
          code_system varchar(64) NULL,
          code varchar(128) NULL,
          status varchar(32) NOT NULL,
          dose_value numeric(12,4) NULL,
          dose_unit varchar(32) NULL,
          frequency_text varchar(255) NULL,
          route varchar(64) NULL,
          start_date date NULL,
          end_date date NULL,
          reason_text varchar(500) NULL,
          source_type varchar(32) NOT NULL,
          confirmation_status varchar(32) NOT NULL,
          created_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          voided_at timestamptz NULL,
          voided_by_user_id uuid NULL REFERENCES {S}.users(id),
          void_reason varchar(500) NULL,
          CONSTRAINT ck_profile_medications_name CHECK (btrim(display_name) <> ''),
          CONSTRAINT ck_profile_medications_status CHECK (
            status IN ('active', 'completed', 'paused', 'stopped', 'unknown')
          ),
          CONSTRAINT ck_profile_medications_dose CHECK (
            (dose_value IS NULL AND dose_unit IS NULL)
            OR
            (dose_value > 0 AND dose_unit IS NOT NULL AND btrim(dose_unit) <> '')
          ),
          CONSTRAINT ck_profile_medications_dates CHECK (
            end_date IS NULL OR start_date IS NULL OR end_date >= start_date
          ),
          CONSTRAINT ck_profile_medications_source CHECK (
            source_type IN ('manual', 'document')
          ),
          CONSTRAINT ck_profile_medications_confirmation CHECK (
            confirmation_status IN ('confirmed', 'needs_review')
          ),
          CONSTRAINT ck_profile_medications_source_confirmation CHECK (
            source_type <> 'manual' OR confirmation_status = 'confirmed'
          ),
          CONSTRAINT ck_profile_medications_void CHECK (
            (voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL)
            OR
            (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL
             AND void_reason IS NOT NULL AND btrim(void_reason) <> '')
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_profile_medications_profile_status "
        f"ON {S}.profile_medications (profile_id, status, updated_at DESC)"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.profile_supplements (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          display_name varchar(255) NOT NULL,
          supplement_type varchar(32) NOT NULL,
          code_system varchar(64) NULL,
          code varchar(128) NULL,
          status varchar(32) NOT NULL,
          dose_value numeric(12,4) NULL,
          dose_unit varchar(32) NULL,
          frequency_text varchar(255) NULL,
          start_date date NULL,
          end_date date NULL,
          source_type varchar(32) NOT NULL,
          confirmation_status varchar(32) NOT NULL,
          created_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          voided_at timestamptz NULL,
          voided_by_user_id uuid NULL REFERENCES {S}.users(id),
          void_reason varchar(500) NULL,
          CONSTRAINT ck_profile_supplements_name CHECK (btrim(display_name) <> ''),
          CONSTRAINT ck_profile_supplements_type CHECK (
            supplement_type IN ('vitamin', 'mineral', 'herbal', 'sports', 'other', 'unknown')
          ),
          CONSTRAINT ck_profile_supplements_status CHECK (
            status IN ('active', 'completed', 'paused', 'stopped', 'unknown')
          ),
          CONSTRAINT ck_profile_supplements_dose CHECK (
            (dose_value IS NULL AND dose_unit IS NULL)
            OR
            (dose_value > 0 AND dose_unit IS NOT NULL AND btrim(dose_unit) <> '')
          ),
          CONSTRAINT ck_profile_supplements_dates CHECK (
            end_date IS NULL OR start_date IS NULL OR end_date >= start_date
          ),
          CONSTRAINT ck_profile_supplements_source CHECK (
            source_type IN ('manual', 'document')
          ),
          CONSTRAINT ck_profile_supplements_confirmation CHECK (
            confirmation_status IN ('confirmed', 'needs_review')
          ),
          CONSTRAINT ck_profile_supplements_source_confirmation CHECK (
            source_type <> 'manual' OR confirmation_status = 'confirmed'
          ),
          CONSTRAINT ck_profile_supplements_void CHECK (
            (voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL)
            OR
            (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL
             AND void_reason IS NOT NULL AND btrim(void_reason) <> '')
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_profile_supplements_profile_status "
        f"ON {S}.profile_supplements (profile_id, status, updated_at DESC)"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.profile_clinical_safety_flags (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          flag_type varchar(64) NOT NULL,
          status varchar(32) NOT NULL,
          source_entity_type varchar(64) NULL,
          source_entity_id uuid NULL,
          source_type varchar(32) NOT NULL,
          confirmation_status varchar(32) NOT NULL,
          created_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          voided_at timestamptz NULL,
          voided_by_user_id uuid NULL REFERENCES {S}.users(id),
          void_reason varchar(500) NULL,
          CONSTRAINT ck_profile_clinical_safety_flags_type CHECK (
            flag_type = 'nutrition_calorie_feedback_suppressed'
          ),
          CONSTRAINT ck_profile_clinical_safety_flags_status CHECK (
            status IN ('active', 'inactive')
          ),
          CONSTRAINT ck_profile_clinical_safety_flags_source CHECK (
            source_type IN ('manual', 'document')
          ),
          CONSTRAINT ck_profile_clinical_safety_flags_confirmation CHECK (
            confirmation_status IN ('confirmed', 'needs_review')
          ),
          CONSTRAINT ck_profile_clinical_safety_flags_source_confirmation CHECK (
            source_type <> 'manual' OR confirmation_status = 'confirmed'
          ),
          CONSTRAINT ck_profile_clinical_safety_flags_void CHECK (
            (voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL)
            OR
            (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL
             AND void_reason IS NOT NULL AND btrim(void_reason) <> '')
          )
        )
        """
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_profile_clinical_safety_flags_active "
        f"ON {S}.profile_clinical_safety_flags (profile_id, flag_type) "
        f"WHERE voided_at IS NULL AND status = 'active'"
    )

    _enable_rls_and_grant(
        "profile_conditions",
        "display_name, code_system, code, clinical_status, onset_date, resolved_date, "
        "notes, updated_at, voided_at, voided_by_user_id, void_reason",
    )
    _enable_rls_and_grant(
        "profile_allergies",
        "substance_name, code_system, code, allergy_type, reaction, severity, "
        "clinical_status, updated_at, voided_at, voided_by_user_id, void_reason",
    )
    _enable_rls_and_grant(
        "profile_medications",
        "display_name, code_system, code, status, dose_value, dose_unit, frequency_text, "
        "route, start_date, end_date, reason_text, updated_at, voided_at, "
        "voided_by_user_id, void_reason",
    )
    _enable_rls_and_grant(
        "profile_supplements",
        "display_name, supplement_type, code_system, code, status, dose_value, dose_unit, "
        "frequency_text, start_date, end_date, updated_at, voided_at, "
        "voided_by_user_id, void_reason",
    )
    _enable_rls_and_grant(
        "profile_clinical_safety_flags",
        "status, source_entity_type, source_entity_id, updated_at, voided_at, "
        "voided_by_user_id, void_reason",
    )

    op.execute(
        f"ALTER TABLE {S}.profile_audit_events "
        f"DROP CONSTRAINT ck_profile_audit_action"
    )
    op.execute(
        f"""
        ALTER TABLE {S}.profile_audit_events
        ADD CONSTRAINT ck_profile_audit_action CHECK (
          action IN (
            'profile.updated',
            'body_measurement.created',
            'body_measurement.voided',
            'condition.created', 'condition.updated', 'condition.voided',
            'allergy.created', 'allergy.updated', 'allergy.voided',
            'medication.created', 'medication.updated', 'medication.voided',
            'supplement.created', 'supplement.updated', 'supplement.voided',
            'clinical_safety_flag.created',
            'clinical_safety_flag.updated',
            'clinical_safety_flag.voided'
          )
        )
        """
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {S}.profile_audit_events "
        f"DROP CONSTRAINT ck_profile_audit_action"
    )
    op.execute(
        f"""
        ALTER TABLE {S}.profile_audit_events
        ADD CONSTRAINT ck_profile_audit_action CHECK (
          action IN (
            'profile.updated',
            'body_measurement.created',
            'body_measurement.voided'
          )
        )
        """
    )

    for table in reversed(CLINICAL_TABLES):
        op.execute(f"REVOKE ALL ON {S}.{table} FROM {APP}")
        op.execute(f"DROP POLICY IF EXISTS {table}_update ON {S}.{table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_insert ON {S}.{table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_select ON {S}.{table}")
        op.execute(f"DROP TABLE {S}.{table}")
