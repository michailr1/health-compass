"""Add explicit reviewed/confirmed-empty state for Clinical Context sections.

Revision ID: 0039
Revises: 0038
"""

from __future__ import annotations

from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {S}.profile_clinical_reviews (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          section varchar(32) NOT NULL,
          confirmed_empty boolean NOT NULL DEFAULT false,
          reviewed_at timestamptz NOT NULL DEFAULT now(),
          reviewed_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_profile_clinical_reviews_section CHECK (
            section IN ('conditions', 'allergies', 'medications', 'supplements')
          ),
          CONSTRAINT ux_profile_clinical_reviews_profile_section UNIQUE (profile_id, section)
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_profile_clinical_reviews_profile "
        f"ON {S}.profile_clinical_reviews (profile_id, section)"
    )
    op.execute(f"ALTER TABLE {S}.profile_clinical_reviews ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.profile_clinical_reviews FORCE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON {S}.profile_clinical_reviews FROM PUBLIC")
    op.execute(f"REVOKE ALL ON {S}.profile_clinical_reviews FROM {APP}")
    op.execute(f"GRANT SELECT, INSERT ON {S}.profile_clinical_reviews TO {APP}")
    op.execute(
        f"GRANT UPDATE (confirmed_empty, reviewed_at, reviewed_by_user_id, updated_at) "
        f"ON {S}.profile_clinical_reviews TO {APP}"
    )
    op.execute(
        f"""
        CREATE POLICY profile_clinical_reviews_select
        ON {S}.profile_clinical_reviews
        FOR SELECT
        USING ({S}.app_can_view_profile(profile_id))
        """
    )
    op.execute(
        f"""
        CREATE POLICY profile_clinical_reviews_insert
        ON {S}.profile_clinical_reviews
        FOR INSERT
        WITH CHECK (
          reviewed_by_user_id = {S}.app_current_user_id()
          AND {S}.app_can_edit_profile(profile_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY profile_clinical_reviews_update
        ON {S}.profile_clinical_reviews
        FOR UPDATE
        USING ({S}.app_can_edit_profile(profile_id))
        WITH CHECK (
          reviewed_by_user_id = {S}.app_current_user_id()
          AND {S}.app_can_edit_profile(profile_id)
        )
        """
    )

    op.execute(
        f"ALTER TABLE {S}.profile_audit_events DROP CONSTRAINT ck_profile_audit_action"
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
            'clinical_safety_flag.voided',
            'clinical_context.reviewed'
          )
        )
        """
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE {S}.profile_audit_events DROP CONSTRAINT ck_profile_audit_action"
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
    op.execute(f"REVOKE ALL ON {S}.profile_clinical_reviews FROM {APP}")
    op.execute(
        f"DROP POLICY IF EXISTS profile_clinical_reviews_update "
        f"ON {S}.profile_clinical_reviews"
    )
    op.execute(
        f"DROP POLICY IF EXISTS profile_clinical_reviews_insert "
        f"ON {S}.profile_clinical_reviews"
    )
    op.execute(
        f"DROP POLICY IF EXISTS profile_clinical_reviews_select "
        f"ON {S}.profile_clinical_reviews"
    )
    op.execute(f"DROP TABLE {S}.profile_clinical_reviews")
