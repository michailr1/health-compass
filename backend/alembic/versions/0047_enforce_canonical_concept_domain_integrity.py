"""Enforce canonical concept domain integrity on the DB boundary.

HC-015 Slice D (CR-04/CR-05/CR-19 dictionary part):

1. repairs stale derived mappings: ``canonical_concept_id`` is cleared where
   the source coding no longer says ``health_compass`` + code, and re-aligned
   where a valid matching concept exists;
2. stops with a clear error if any existing row carries a non-UUID code, an
   unknown concept or a wrong-domain concept — those need human review, they
   are never repaired silently;
3. replaces the sync trigger with a per-section validating version: clearing
   or changing ``code``/``code_system`` atomically clears or re-derives the
   mapping, invalid UUIDs raise SQLSTATE ``HC422``, unknown concepts
   ``HC404`` and wrong-domain concepts ``HC409`` so the API can translate
   them into controlled validation errors;
4. revokes the direct ``UPDATE (canonical_concept_id)`` grant from the
   runtime role — the column is system-managed and only ever derived.

Downgrade restores the 0043 trigger behavior and the column grant. The data
repairs are not reversed: the cleared values were already invalid under the
derivation contract that existed since 0043.

Revision ID: 0047
Revises: 0046
"""

from __future__ import annotations

from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"

DOMAIN_BY_TABLE = {
    "profile_conditions": "condition_or_symptom",
    "profile_allergies": "allergy_or_intolerance",
    "profile_medications": "medication",
    "profile_supplements": "supplement",
}

UUID_REGEX = (
    "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    "[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _repair_and_verify_existing_rows() -> None:
    for table, domain in DOMAIN_BY_TABLE.items():
        # Safe repair 1: the derivation contract says "no health_compass
        # coding, no canonical mapping". Clearing a derived value that should
        # not exist loses no source data.
        op.execute(
            f"""
            UPDATE {S}.{table}
            SET canonical_concept_id = NULL
            WHERE canonical_concept_id IS NOT NULL
              AND (code_system IS DISTINCT FROM 'health_compass' OR code IS NULL)
            """
        )

        # Stop: a health_compass code that is not a UUID cannot be derived.
        op.execute(
            f"""
            DO $$
            DECLARE bad integer;
            BEGIN
              SELECT count(*) INTO bad
              FROM {S}.{table}
              WHERE code_system = 'health_compass'
                AND code IS NOT NULL
                AND code !~ '{UUID_REGEX}';
              IF bad > 0 THEN
                RAISE EXCEPTION
                  '0047: % rows in {S}.{table} have a non-UUID health_compass code; review them before enforcing domain integrity',
                  bad;
              END IF;
            END
            $$
            """
        )

        # Safe repair 2: re-align a drifted derived value when the coded
        # concept exists and belongs to the correct domain.
        op.execute(
            f"""
            UPDATE {S}.{table} t
            SET canonical_concept_id = t.code::uuid
            FROM {S}.clinical_dictionary_concepts c
            WHERE t.code_system = 'health_compass'
              AND t.code IS NOT NULL
              AND c.id = t.code::uuid
              AND c.domain = '{domain}'
              AND t.canonical_concept_id IS DISTINCT FROM t.code::uuid
            """
        )

        # Stop: unknown concept or wrong-domain concept needs human review.
        op.execute(
            f"""
            DO $$
            DECLARE bad integer;
            BEGIN
              SELECT count(*) INTO bad
              FROM {S}.{table} t
              LEFT JOIN {S}.clinical_dictionary_concepts c ON c.id = t.code::uuid
              WHERE t.code_system = 'health_compass'
                AND t.code IS NOT NULL
                AND (c.id IS NULL OR c.domain <> '{domain}');
              IF bad > 0 THEN
                RAISE EXCEPTION
                  '0047: % rows in {S}.{table} reference an unknown or wrong-domain health_compass concept; repair them manually before this migration',
                  bad;
              END IF;
            END
            $$
            """
        )


def _create_validating_trigger_function() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.sync_clinical_dictionary_concept()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          expected_domain text := TG_ARGV[0];
          concept_domain text;
        BEGIN
          IF NEW.code_system = 'health_compass' AND NEW.code IS NOT NULL THEN
            BEGIN
              NEW.canonical_concept_id := NEW.code::uuid;
            EXCEPTION WHEN invalid_text_representation THEN
              RAISE EXCEPTION 'invalid health_compass concept id'
                USING ERRCODE = 'HC422';
            END;
          ELSE
            -- Clearing the code or leaving the health_compass code system
            -- always clears the derived mapping (CR-05).
            NEW.canonical_concept_id := NULL;
          END IF;

          IF NEW.canonical_concept_id IS NOT NULL THEN
            SELECT domain INTO concept_domain
            FROM {S}.clinical_dictionary_concepts
            WHERE id = NEW.canonical_concept_id;
            IF concept_domain IS NULL THEN
              RAISE EXCEPTION 'unknown health_compass concept'
                USING ERRCODE = 'HC404';
            END IF;
            IF concept_domain <> expected_domain THEN
              RAISE EXCEPTION
                'clinical concept domain % does not match section domain %',
                concept_domain, expected_domain
                USING ERRCODE = 'HC409';
            END IF;
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def _create_legacy_trigger_function() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.sync_clinical_dictionary_concept()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.code_system = 'health_compass' AND NEW.code IS NOT NULL THEN
            BEGIN
              NEW.canonical_concept_id := NEW.code::uuid;
            EXCEPTION WHEN invalid_text_representation THEN
              RAISE EXCEPTION 'invalid health_compass concept id';
            END;
          ELSIF NEW.code_system IS DISTINCT FROM 'health_compass' THEN
            NEW.canonical_concept_id := NULL;
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )


def upgrade() -> None:
    # Block concurrent writes while existing rows are repaired/validated and
    # the old permissive triggers are replaced. Without this lock a legacy
    # application process could insert a wrong-domain code after validation
    # but before the validating trigger is installed.
    op.execute(
        f"""
        LOCK TABLE
          {S}.profile_conditions,
          {S}.profile_allergies,
          {S}.profile_medications,
          {S}.profile_supplements
        IN ACCESS EXCLUSIVE MODE
        """
    )

    _repair_and_verify_existing_rows()
    for table in DOMAIN_BY_TABLE:
        op.execute(f"DROP TRIGGER IF EXISTS trg_sync_{table}_dictionary_concept ON {S}.{table}")
    _create_validating_trigger_function()
    for table, domain in DOMAIN_BY_TABLE.items():
        op.execute(
            f"""
            CREATE TRIGGER trg_sync_{table}_dictionary_concept
            BEFORE INSERT OR UPDATE OF code_system, code, canonical_concept_id
            ON {S}.{table}
            FOR EACH ROW
            EXECUTE FUNCTION {S}.sync_clinical_dictionary_concept('{domain}')
            """
        )
        # The canonical column is derived and system-managed; the runtime
        # role must not write it directly (defense in depth for CR-04).
        op.execute(f"REVOKE UPDATE (canonical_concept_id) ON {S}.{table} FROM {APP}")


def downgrade() -> None:
    for table in DOMAIN_BY_TABLE:
        op.execute(f"DROP TRIGGER IF EXISTS trg_sync_{table}_dictionary_concept ON {S}.{table}")
    _create_legacy_trigger_function()
    for table in DOMAIN_BY_TABLE:
        op.execute(
            f"""
            CREATE TRIGGER trg_sync_{table}_dictionary_concept
            BEFORE INSERT OR UPDATE OF code_system, code
            ON {S}.{table}
            FOR EACH ROW
            EXECUTE FUNCTION {S}.sync_clinical_dictionary_concept()
            """
        )
        op.execute(f"GRANT UPDATE (canonical_concept_id) ON {S}.{table} TO {APP}")
