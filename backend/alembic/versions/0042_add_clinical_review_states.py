"""Add first-class Clinical Context review states.

Revision ID: 0042
Revises: 0041
"""

from __future__ import annotations

from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {S}.profile_clinical_reviews "
        "ADD COLUMN review_state varchar(32)"
    )
    op.execute(
        f"UPDATE {S}.profile_clinical_reviews "
        "SET review_state = CASE WHEN confirmed_empty THEN 'confirmed_none' ELSE 'unknown' END"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_clinical_reviews "
        "ALTER COLUMN review_state SET DEFAULT 'unknown'"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_clinical_reviews "
        "ALTER COLUMN review_state SET NOT NULL"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_clinical_reviews "
        "ADD CONSTRAINT ck_profile_clinical_reviews_state "
        "CHECK (review_state IN ('unknown', 'deferred', 'confirmed_none'))"
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.sync_clinical_review_legacy_flag()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_OP = 'INSERT' THEN
            IF NEW.confirmed_empty THEN
              NEW.review_state := 'confirmed_none';
            ELSE
              NEW.confirmed_empty := (NEW.review_state = 'confirmed_none');
            END IF;
          ELSIF NEW.review_state IS DISTINCT FROM OLD.review_state THEN
            NEW.confirmed_empty := (NEW.review_state = 'confirmed_none');
          ELSIF NEW.confirmed_empty IS DISTINCT FROM OLD.confirmed_empty THEN
            NEW.review_state := CASE WHEN NEW.confirmed_empty THEN 'confirmed_none' ELSE 'unknown' END;
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_sync_clinical_review_legacy_flag
        BEFORE INSERT OR UPDATE OF review_state, confirmed_empty
        ON {S}.profile_clinical_reviews
        FOR EACH ROW
        EXECUTE FUNCTION {S}.sync_clinical_review_legacy_flag()
        """
    )
    op.execute(
        f"GRANT UPDATE (review_state) ON {S}.profile_clinical_reviews TO {APP}"
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
            'clinical_context.reviewed',
            'clinical_section.review_deferred',
            'clinical_section.review_unknown',
            'clinical_section.confirmed_none',
            'clinical_section.confirmed_none_cleared'
          )
        )
        """
    )

    op.execute(f"ALTER TABLE {S}.profile_clinical_reviews ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.profile_clinical_reviews FORCE ROW LEVEL SECURITY")
    op.execute(f"REVOKE DELETE ON {S}.profile_clinical_reviews FROM {APP}")


def downgrade() -> None:
    op.execute(
        f"DROP TRIGGER IF EXISTS trg_sync_clinical_review_legacy_flag "
        f"ON {S}.profile_clinical_reviews"
    )
    op.execute(
        f"DROP FUNCTION IF EXISTS {S}.sync_clinical_review_legacy_flag()"
    )
    op.execute(
        f"UPDATE {S}.profile_clinical_reviews "
        "SET confirmed_empty = (review_state = 'confirmed_none')"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_clinical_reviews "
        "DROP CONSTRAINT ck_profile_clinical_reviews_state"
    )
    op.execute(
        f"REVOKE UPDATE (review_state) ON {S}.profile_clinical_reviews FROM {APP}"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_clinical_reviews DROP COLUMN review_state"
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
