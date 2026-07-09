"""Add manual allergies and medications clinical context.

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
APP = "health_compass_app"
MIGRATOR = "health_compass_migrator"


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE {S}.health_profiles
          ADD COLUMN allergies_reviewed_at timestamptz,
          ADD COLUMN medications_reviewed_at timestamptz
        """
    )

    op.execute(
        f"""
        CREATE TABLE {S}.profile_allergies (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id) ON DELETE CASCADE,
          allergen varchar(255) NOT NULL,
          reaction text,
          severity varchar(16) NOT NULL DEFAULT 'unknown',
          status varchar(24) NOT NULL DEFAULT 'active',
          onset_date date,
          notes text,
          source_kind varchar(24) NOT NULL DEFAULT 'manual',
          created_by_user_id uuid NOT NULL REFERENCES {S}.users(id) ON DELETE RESTRICT,
          updated_by_user_id uuid NOT NULL REFERENCES {S}.users(id) ON DELETE RESTRICT,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_profile_allergy_allergen_nonempty CHECK (btrim(allergen) <> ''),
          CONSTRAINT ck_profile_allergy_severity CHECK (
            severity IN ('unknown', 'mild', 'moderate', 'severe')
          ),
          CONSTRAINT ck_profile_allergy_status CHECK (
            status IN ('active', 'resolved', 'entered_in_error')
          ),
          CONSTRAINT ck_profile_allergy_source CHECK (source_kind = 'manual')
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_profile_allergies_profile_id ON {S}.profile_allergies(profile_id)"
    )
    op.execute(
        f"CREATE INDEX ix_profile_allergies_profile_status ON {S}.profile_allergies(profile_id, status)"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.profile_medications (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id) ON DELETE CASCADE,
          medication_name varchar(255) NOT NULL,
          dose_text varchar(255),
          schedule_text varchar(255),
          indication text,
          status varchar(24) NOT NULL DEFAULT 'active',
          started_on date,
          ended_on date,
          notes text,
          source_kind varchar(24) NOT NULL DEFAULT 'manual',
          created_by_user_id uuid NOT NULL REFERENCES {S}.users(id) ON DELETE RESTRICT,
          updated_by_user_id uuid NOT NULL REFERENCES {S}.users(id) ON DELETE RESTRICT,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_profile_medication_name_nonempty CHECK (btrim(medication_name) <> ''),
          CONSTRAINT ck_profile_medication_status CHECK (
            status IN ('active', 'paused', 'stopped', 'entered_in_error')
          ),
          CONSTRAINT ck_profile_medication_dates CHECK (
            ended_on IS NULL OR started_on IS NULL OR ended_on >= started_on
          ),
          CONSTRAINT ck_profile_medication_source CHECK (source_kind = 'manual')
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_profile_medications_profile_id ON {S}.profile_medications(profile_id)"
    )
    op.execute(
        f"CREATE INDEX ix_profile_medications_profile_status ON {S}.profile_medications(profile_id, status)"
    )

    for table in ("profile_allergies", "profile_medications"):
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {S}.{table} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON {S}.{table} FROM {APP}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.{table} TO {APP}")

        op.execute(
            f"""
            CREATE POLICY {table}_select_visible
            ON {S}.{table}
            FOR SELECT
            TO {APP}
            USING ({S}.app_can_view_profile(profile_id))
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_insert_editable
            ON {S}.{table}
            FOR INSERT
            TO {APP}
            WITH CHECK (
              {S}.app_can_edit_profile(profile_id)
              AND EXISTS (
                SELECT 1
                FROM {S}.health_profiles hp
                JOIN {S}.user_consents uc ON uc.user_id = hp.owner_user_id
                WHERE hp.id = profile_id
                  AND uc.consent_type = 'health_data_processing'
                  AND uc.revoked_at IS NULL
              )
            )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_update_editable
            ON {S}.{table}
            FOR UPDATE
            TO {APP}
            USING ({S}.app_can_edit_profile(profile_id))
            WITH CHECK (
              {S}.app_can_edit_profile(profile_id)
              AND EXISTS (
                SELECT 1
                FROM {S}.health_profiles hp
                JOIN {S}.user_consents uc ON uc.user_id = hp.owner_user_id
                WHERE hp.id = profile_id
                  AND uc.consent_type = 'health_data_processing'
                  AND uc.revoked_at IS NULL
              )
            )
            """
        )

    op.execute(f"GRANT SELECT ON {S}.user_consents TO {APP}")
    op.execute(f"GRANT SELECT, UPDATE ON {S}.health_profiles TO {APP}")


def downgrade() -> None:
    for table in ("profile_medications", "profile_allergies"):
        op.execute(f"DROP TABLE IF EXISTS {S}.{table}")

    op.execute(
        f"""
        ALTER TABLE {S}.health_profiles
          DROP COLUMN IF EXISTS medications_reviewed_at,
          DROP COLUMN IF EXISTS allergies_reviewed_at
        """
    )
