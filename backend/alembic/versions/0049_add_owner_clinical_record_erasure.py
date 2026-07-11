"""Add owner-only permanent erasure for Clinical Context records.

Revision ID: 0049
Revises: 0048

Direct DELETE remains unavailable to the runtime role. Erasure is exposed only
through a narrowly scoped SECURITY DEFINER function that verifies profile
ownership, applies optimistic concurrency, removes content-bearing audit rows,
and leaves a generic non-medical tombstone event.
"""

from __future__ import annotations

from alembic import op

revision = "0049"
down_revision = "0048"
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

CURRENT_AUDIT_ACTIONS = """
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
"""

FUNCTION_SIGNATURE = (
    f"{S}.app_erase_clinical_record("
    "uuid, text, uuid, timestamp with time zone, uuid, text)"
)


def _replace_audit_constraint(*, include_erasure: bool) -> None:
    actions = CURRENT_AUDIT_ACTIONS
    if include_erasure:
        actions = f"{actions.rstrip()},\n            'clinical_record.erased'\n"
    op.execute(
        f"ALTER TABLE {S}.profile_audit_events "
        "DROP CONSTRAINT ck_profile_audit_action"
    )
    op.execute(
        f"""
        ALTER TABLE {S}.profile_audit_events
        ADD CONSTRAINT ck_profile_audit_action CHECK (
          action IN (
{actions}
          )
        )
        """
    )


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

    _replace_audit_constraint(include_erasure=True)

    # Preserve the no-direct-delete invariant. The definer function below is
    # the only supported runtime erasure path.
    for table in CLINICAL_TABLES:
        op.execute(f"REVOKE DELETE ON {S}.{table} FROM {APP}")
        op.execute(f"GRANT SELECT, DELETE ON {S}.{table} TO {R}")
    op.execute(f"REVOKE DELETE ON {S}.profile_audit_events FROM {APP}")
    op.execute(f"GRANT SELECT ON {S}.health_profiles TO {R}")
    op.execute(f"GRANT SELECT, INSERT, DELETE ON {S}.profile_audit_events TO {R}")

    # PostgreSQL requires the prospective function owner to hold CREATE on the
    # containing schema during ALTER FUNCTION ... OWNER TO. Grant it only for
    # the ownership transfer and revoke it immediately afterwards.
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_erase_clinical_record(
          target_profile_id uuid,
          target_section text,
          target_record_id uuid,
          expected_updated_at timestamptz,
          erasure_event_id uuid,
          erasure_request_id text
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          actor_id uuid;
          owner_id uuid;
          target_table text;
          source_entity_type text;
          actual_updated_at timestamptz;
        BEGIN
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL THEN
            RAISE EXCEPTION 'Clinical record not found' USING ERRCODE = 'HC404';
          END IF;

          SELECT hp.owner_user_id
          INTO owner_id
          FROM {S}.health_profiles hp
          WHERE hp.id = target_profile_id;

          -- Return the same not-found shape for a missing profile and a caller
          -- who is not the profile owner, avoiding profile enumeration.
          IF owner_id IS NULL OR owner_id <> actor_id THEN
            RAISE EXCEPTION 'Clinical record not found' USING ERRCODE = 'HC404';
          END IF;

          IF expected_updated_at IS NULL THEN
            RAISE EXCEPTION 'expected_updated_at is required' USING ERRCODE = 'HC428';
          END IF;

          CASE target_section
            WHEN 'conditions' THEN
              target_table := 'profile_conditions';
              source_entity_type := 'condition';
            WHEN 'allergies' THEN
              target_table := 'profile_allergies';
              source_entity_type := 'allergy';
            WHEN 'medications' THEN
              target_table := 'profile_medications';
              source_entity_type := 'medication';
            WHEN 'supplements' THEN
              target_table := 'profile_supplements';
              source_entity_type := 'supplement';
            WHEN 'clinical-safety-flags' THEN
              target_table := 'profile_clinical_safety_flags';
              source_entity_type := 'clinical_safety_flag';
            ELSE
              RAISE EXCEPTION 'Unknown clinical section' USING ERRCODE = 'HC422';
          END CASE;

          -- Serialize erasure against first-record creation and section review
          -- transitions for the four user-facing Clinical Context sections.
          IF target_section <> 'clinical-safety-flags' THEN
            PERFORM pg_catalog.pg_advisory_xact_lock(
              pg_catalog.hashtextextended(
                'clinical-review:' || target_profile_id::text || ':' || target_section,
                8615
              )
            );
          END IF;

          EXECUTE pg_catalog.format(
            'SELECT updated_at FROM %I.%I '
            'WHERE id = $1 AND profile_id = $2 FOR UPDATE',
            '{S}', target_table
          )
          INTO actual_updated_at
          USING target_record_id, target_profile_id;

          IF NOT FOUND THEN
            RAISE EXCEPTION 'Clinical record not found' USING ERRCODE = 'HC404';
          END IF;

          IF actual_updated_at IS DISTINCT FROM expected_updated_at THEN
            RAISE EXCEPTION 'Clinical record was updated elsewhere' USING ERRCODE = 'HC409';
          END IF;

          -- Earlier audit events can contain names, doses, reactions and other
          -- health values. Remove those values as part of the same transaction.
          DELETE FROM {S}.profile_audit_events
          WHERE profile_id = target_profile_id
            AND entity_type = source_entity_type
            AND entity_id = target_record_id;

          EXECUTE pg_catalog.format(
            'DELETE FROM %I.%I WHERE id = $1 AND profile_id = $2',
            '{S}', target_table
          )
          USING target_record_id, target_profile_id;

          -- Keep only a content-free security tombstone. It intentionally does
          -- not retain the section, record label, clinical values or reason.
          INSERT INTO {S}.profile_audit_events (
            id,
            profile_id,
            actor_user_id,
            entity_type,
            entity_id,
            action,
            changed_fields,
            request_id
          ) VALUES (
            erasure_event_id,
            target_profile_id,
            actor_id,
            'clinical_record',
            target_record_id,
            'clinical_record.erased',
            '{{}}'::jsonb,
            erasure_request_id
          );

          RETURN true;
        END;
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {FUNCTION_SIGNATURE} OWNER TO {R}")
    op.execute(f"ALTER FUNCTION {FUNCTION_SIGNATURE} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION_SIGNATURE} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {FUNCTION_SIGNATURE} FROM {APP}")
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION_SIGNATURE}")

    for table in CLINICAL_TABLES:
        op.execute(f"REVOKE DELETE ON {S}.{table} FROM {R}")
        op.execute(f"REVOKE DELETE ON {S}.{table} FROM {APP}")
    op.execute(f"REVOKE INSERT, DELETE ON {S}.profile_audit_events FROM {R}")
    op.execute(f"REVOKE DELETE ON {S}.profile_audit_events FROM {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")

    _replace_audit_constraint(include_erasure=False)
