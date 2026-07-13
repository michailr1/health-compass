"""Harden E3 correction acknowledgement and erasure concurrency.

Revision ID: 0061
Revises: 0060

Correction creates a new medical fact and therefore requires fresh explicit
acknowledgements. Document erasure transitions lock dependent Lab rows with
NOWAIT, and observation-chain erasure stabilizes the complete chain before
irreversible deletion.
"""

from __future__ import annotations

from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"

OLD_CORRECT_SIG = (
    f"{S}.app_correct_lab_observation("
    "uuid,uuid,integer,text,text,jsonb,uuid,text)"
)
NEW_CORRECT_SIG = (
    f"{S}.app_correct_lab_observation("
    "uuid,uuid,integer,text,text,jsonb,"
    "boolean,boolean,boolean,boolean,boolean,boolean,uuid,text)"
)
ERASE_SIG = f"{S}.app_erase_lab_observation(uuid,integer,boolean,uuid,text)"
TRIGGER_SIG = f"{S}.app_guard_document_lab_erasure_transition()"


def _create_correction_function() -> None:
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_correct_lab_observation(
          p_new_observation_id uuid,
          p_observation_id uuid,
          p_expected_lifecycle_version integer,
          p_idempotency_key text,
          p_reason text,
          p_payload jsonb,
          p_ack_source boolean,
          p_ack_unit_range boolean,
          p_ack_observed_at boolean,
          p_ack_profile boolean,
          p_ack_structured_record boolean,
          p_ack_not_present_assignment boolean,
          p_audit_event_id uuid,
          p_request_id text
        )
        RETURNS uuid
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          actor_id uuid;
          owner_id uuid;
          target_observation {S}.lab_observations%ROWTYPE;
          target_document {S}.profile_documents%ROWTYPE;
          existing_observation {S}.lab_observations%ROWTYPE;
          now_value timestamptz := pg_catalog.clock_timestamp();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Lab observation not found' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL OR p_new_observation_id IS NULL
             OR p_expected_lifecycle_version IS NULL THEN
            RAISE EXCEPTION 'Lab lifecycle precondition is required'
              USING ERRCODE = 'HC428';
          END IF;
          IF p_new_observation_id = p_observation_id
             OR coalesce(length(p_idempotency_key), 0) NOT BETWEEN 16 AND 128
             OR p_idempotency_key !~ '^[A-Za-z0-9._:-]+$'
             OR coalesce(length(btrim(p_reason)), 0) NOT BETWEEN 1 AND 1000
             OR p_reason ~ '[[:cntrl:]]'
             OR (p_request_id IS NOT NULL AND length(p_request_id) > 128) THEN
            RAISE EXCEPTION 'Invalid Lab correction request' USING ERRCODE = 'HC422';
          END IF;
          IF p_ack_source IS DISTINCT FROM true
             OR p_ack_unit_range IS DISTINCT FROM true
             OR p_ack_observed_at IS DISTINCT FROM true
             OR p_ack_profile IS DISTINCT FROM true
             OR p_ack_structured_record IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'All correction acknowledgements are required'
              USING ERRCODE = 'HC422';
          END IF;
          PERFORM {S}.app_validate_lab_draft_payload(p_payload);

          SELECT o.* INTO target_observation
          FROM {S}.lab_observations o
          WHERE o.id = p_observation_id
          FOR UPDATE;
          IF target_observation.id IS NULL
             OR NOT {S}.app_can_edit_profile(target_observation.profile_id) THEN
            RAISE EXCEPTION 'Lab observation not found' USING ERRCODE = 'HC404';
          END IF;

          SELECT d.* INTO target_document
          FROM {S}.profile_documents d
          WHERE d.id = target_observation.document_id
            AND d.profile_id = target_observation.profile_id
          FOR UPDATE;
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp
          WHERE hp.id = target_observation.profile_id;

          SELECT o.* INTO existing_observation
          FROM {S}.lab_observations o
          WHERE o.profile_id = target_observation.profile_id
            AND o.confirmation_idempotency_key = p_idempotency_key;
          IF existing_observation.id IS NOT NULL THEN
            IF existing_observation.supersedes_observation_id = p_observation_id THEN
              RETURN existing_observation.id;
            END IF;
            RAISE EXCEPTION 'Lab correction idempotency conflict'
              USING ERRCODE = 'HC409';
          END IF;

          IF target_observation.status <> 'active'
             OR target_document.id IS NULL
             OR target_document.status <> 'accepted'
             OR target_document.voided_at IS NOT NULL
             OR target_document.deletion_requested_at IS NOT NULL
             OR target_document.erased_at IS NOT NULL THEN
            RAISE EXCEPTION 'Lab observation lifecycle changed'
              USING ERRCODE = 'HC409';
          END IF;
          IF target_observation.lifecycle_version <> p_expected_lifecycle_version THEN
            RAISE EXCEPTION 'Lab observation was updated elsewhere'
              USING ERRCODE = 'HC409';
          END IF;
          IF target_observation.patient_decision = 'not_present'
             AND p_ack_not_present_assignment IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Profile assignment acknowledgement is required'
              USING ERRCODE = 'HC422';
          END IF;
          IF owner_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM {S}.user_consents uc
            WHERE uc.user_id = owner_id
              AND uc.consent_type = 'health_data_processing'
              AND uc.revoked_at IS NULL
          ) THEN
            RAISE EXCEPTION 'Health data consent is required'
              USING ERRCODE = 'HC409';
          END IF;

          INSERT INTO {S}.lab_observations (
            id, profile_id, document_id, ocr_run_id, patient_decision_id,
            source_draft_id, status, patient_decision,
            source_analyte_text, source_value_text, value_kind,
            comparator, numeric_value, text_value, qualitative_value_text,
            source_unit_text, unit_not_present,
            source_reference_range_text, reference_range_not_present,
            source_observed_at_text, observed_time_unknown,
            observed_date, observed_at, observed_precision,
            source_specimen_text, source_flag_text, source_comment,
            source_draft_updated_at, source_document_updated_at,
            source_review_finalized_at, source_patient_decision_updated_at,
            confirmation_idempotency_key,
            ack_source, ack_unit_range, ack_observed_at, ack_profile,
            ack_structured_record, ack_not_present_assignment,
            confirmed_by_user_id, confirmed_at, created_at,
            lifecycle_version, lifecycle_updated_at,
            supersedes_observation_id, correction_reason
          ) VALUES (
            p_new_observation_id, target_observation.profile_id,
            target_observation.document_id, target_observation.ocr_run_id,
            target_observation.patient_decision_id, NULL, 'active',
            target_observation.patient_decision,
            btrim(p_payload ->> 'source_analyte_text'),
            btrim(p_payload ->> 'source_value_text'),
            p_payload ->> 'value_kind', nullif(p_payload ->> 'comparator',''),
            CASE WHEN p_payload ->> 'value_kind' = 'numeric'
              THEN (p_payload ->> 'numeric_value')::numeric ELSE NULL END,
            nullif(btrim(p_payload ->> 'text_value'),''),
            nullif(btrim(p_payload ->> 'qualitative_value_text'),''),
            nullif(btrim(p_payload ->> 'source_unit_text'),''),
            (p_payload ->> 'unit_not_present')::boolean,
            nullif(btrim(p_payload ->> 'source_reference_range_text'),''),
            (p_payload ->> 'reference_range_not_present')::boolean,
            nullif(btrim(p_payload ->> 'source_observed_at_text'),''),
            (p_payload ->> 'observed_time_unknown')::boolean,
            CASE WHEN p_payload ? 'observed_date'
              THEN (p_payload ->> 'observed_date')::date ELSE NULL END,
            CASE WHEN p_payload ? 'observed_at'
              THEN (p_payload ->> 'observed_at')::timestamptz ELSE NULL END,
            p_payload ->> 'observed_precision',
            nullif(btrim(p_payload ->> 'source_specimen_text'),''),
            nullif(btrim(p_payload ->> 'source_flag_text'),''),
            nullif(btrim(p_payload ->> 'source_comment'),''),
            target_observation.source_draft_updated_at,
            target_observation.source_document_updated_at,
            target_observation.source_review_finalized_at,
            target_observation.source_patient_decision_updated_at,
            p_idempotency_key,
            p_ack_source,
            p_ack_unit_range,
            p_ack_observed_at,
            p_ack_profile,
            p_ack_structured_record,
            coalesce(p_ack_not_present_assignment, false),
            actor_id, now_value, now_value, 1, now_value,
            target_observation.id, btrim(p_reason)
          );

          INSERT INTO {S}.lab_observation_sources (
            observation_id, candidate_id, source_role, candidate_updated_at,
            profile_id, document_id, ocr_run_id, page_artifact_id, page_number,
            reviewed_text_snapshot
          )
          SELECT p_new_observation_id, s.candidate_id, s.source_role,
                 s.candidate_updated_at, s.profile_id, s.document_id,
                 s.ocr_run_id, s.page_artifact_id, s.page_number,
                 s.reviewed_text_snapshot
          FROM {S}.lab_observation_sources s
          WHERE s.observation_id = target_observation.id;

          UPDATE {S}.lab_observations
          SET status = 'superseded',
              superseded_by_observation_id = p_new_observation_id,
              superseded_at = now_value,
              superseded_by_user_id = actor_id,
              lifecycle_version = lifecycle_version + 1,
              lifecycle_updated_at = now_value
          WHERE id = target_observation.id;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_observation.profile_id, actor_id,
            'lab_observation', p_new_observation_id,
            'lab.observation.corrected', '{{}}'::jsonb, p_request_id
          );
          RETURN p_new_observation_id;
        EXCEPTION
          WHEN invalid_text_representation OR datetime_field_overflow
               OR numeric_value_out_of_range THEN
            RAISE EXCEPTION 'Invalid structured Lab value' USING ERRCODE = 'HC422';
          WHEN unique_violation THEN
            RAISE EXCEPTION 'Lab correction idempotency conflict'
              USING ERRCODE = 'HC409';
        END;
        $$
        """
    )


def _replace_chain_erasure_function() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_erase_lab_observation(
          p_observation_id uuid,
          p_expected_lifecycle_version integer,
          p_confirm_permanent_deletion boolean,
          p_audit_event_id uuid,
          p_request_id text
        )
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          actor_id uuid;
          owner_id uuid;
          target_observation {S}.lab_observations%ROWTYPE;
          root_id uuid;
          previous_id uuid;
          chain_ids uuid[];
          stable_chain_ids uuid[];
          draft_ids uuid[];
          deleted_count integer;
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Lab observation not found' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL OR p_expected_lifecycle_version IS NULL
             OR p_confirm_permanent_deletion IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Permanent erasure confirmation is required'
              USING ERRCODE = 'HC428';
          END IF;
          IF p_request_id IS NOT NULL AND length(p_request_id) > 128 THEN
            RAISE EXCEPTION 'Invalid request id' USING ERRCODE = 'HC422';
          END IF;

          SELECT o.* INTO target_observation
          FROM {S}.lab_observations o
          WHERE o.id = p_observation_id
          FOR UPDATE;
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp
          WHERE hp.id = target_observation.profile_id;
          IF target_observation.id IS NULL OR owner_id IS NULL OR owner_id <> actor_id THEN
            RAISE EXCEPTION 'Lab observation not found' USING ERRCODE = 'HC404';
          END IF;
          IF target_observation.lifecycle_version <> p_expected_lifecycle_version THEN
            RAISE EXCEPTION 'Lab observation was updated elsewhere'
              USING ERRCODE = 'HC409';
          END IF;

          root_id := target_observation.id;
          LOOP
            SELECT o.supersedes_observation_id INTO previous_id
            FROM {S}.lab_observations o WHERE o.id = root_id;
            EXIT WHEN previous_id IS NULL;
            root_id := previous_id;
          END LOOP;

          LOOP
            WITH RECURSIVE chain(id) AS (
              SELECT root_id
              UNION ALL
              SELECT o.id
              FROM {S}.lab_observations o
              JOIN chain c ON o.supersedes_observation_id = c.id
            )
            SELECT array_agg(id ORDER BY id) INTO chain_ids FROM chain;

            BEGIN
              PERFORM o.id
              FROM {S}.lab_observations o
              WHERE o.id = ANY(chain_ids)
              ORDER BY o.id
              FOR UPDATE NOWAIT;
            EXCEPTION WHEN lock_not_available THEN
              RAISE EXCEPTION 'Lab observation lifecycle is busy'
                USING ERRCODE = 'HC409';
            END;

            WITH RECURSIVE stable_chain(id) AS (
              SELECT root_id
              UNION ALL
              SELECT o.id
              FROM {S}.lab_observations o
              JOIN stable_chain c ON o.supersedes_observation_id = c.id
            )
            SELECT array_agg(id ORDER BY id)
            INTO stable_chain_ids
            FROM stable_chain;
            EXIT WHEN stable_chain_ids = chain_ids;
          END LOOP;

          SELECT array_agg(o.source_draft_id)
          INTO draft_ids
          FROM {S}.lab_observations o
          WHERE o.id = ANY(chain_ids) AND o.source_draft_id IS NOT NULL;

          IF draft_ids IS NOT NULL THEN
            UPDATE {S}.lab_observation_drafts
            SET status = 'rejected',
                confirmed_at = NULL,
                confirmed_by_user_id = NULL,
                confirmed_observation_id = NULL,
                updated_by_user_id = actor_id,
                updated_at = pg_catalog.clock_timestamp()
            WHERE id = ANY(draft_ids);
          END IF;

          DELETE FROM {S}.lab_observation_sources
          WHERE observation_id = ANY(chain_ids);
          DELETE FROM {S}.profile_audit_events
          WHERE profile_id = target_observation.profile_id
            AND entity_type = 'lab_observation'
            AND entity_id = ANY(chain_ids);
          DELETE FROM {S}.lab_observations
          WHERE id = ANY(chain_ids);
          GET DIAGNOSTICS deleted_count = ROW_COUNT;

          IF draft_ids IS NOT NULL THEN
            DELETE FROM {S}.profile_audit_events
            WHERE profile_id = target_observation.profile_id
              AND entity_type = 'lab_observation_draft'
              AND entity_id = ANY(draft_ids);
            DELETE FROM {S}.lab_observation_draft_sources
            WHERE draft_id = ANY(draft_ids);
            DELETE FROM {S}.lab_observation_drafts
            WHERE id = ANY(draft_ids);
          END IF;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_observation.profile_id, actor_id,
            'lab_observation', p_observation_id,
            'lab.observation.erased', '{{}}'::jsonb, p_request_id
          );
          RETURN deleted_count;
        END;
        $$
        """
    )


def _create_document_transition_guard() -> None:
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_guard_document_lab_erasure_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        BEGIN
          BEGIN
            PERFORM d.id
            FROM {S}.lab_observation_drafts d
            WHERE d.document_id = NEW.id
            ORDER BY d.id
            FOR UPDATE NOWAIT;

            PERFORM o.id
            FROM {S}.lab_observations o
            WHERE o.document_id = NEW.id
            ORDER BY o.id
            FOR UPDATE NOWAIT;
          EXCEPTION WHEN lock_not_available THEN
            RAISE EXCEPTION 'Document Lab lifecycle is busy'
              USING ERRCODE = 'HC409';
          END;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {TRIGGER_SIG} OWNER TO {DEFINER}")
    op.execute(f"ALTER FUNCTION {TRIGGER_SIG} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {TRIGGER_SIG} FROM PUBLIC")
    op.execute(
        f"""
        CREATE TRIGGER trg_profile_documents_guard_lab_erasure
        BEFORE UPDATE OF status, deletion_requested_at, erased_at
        ON {S}.profile_documents
        FOR EACH ROW
        WHEN (
          (NEW.deletion_requested_at IS NOT NULL
           AND OLD.deletion_requested_at IS NULL)
          OR
          (NEW.erased_at IS NOT NULL AND OLD.erased_at IS NULL)
        )
        EXECUTE FUNCTION {S}.app_guard_document_lab_erasure_transition()
        """
    )


def upgrade() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {OLD_CORRECT_SIG} FROM {APP}")
    _create_correction_function()
    op.execute(f"ALTER FUNCTION {NEW_CORRECT_SIG} OWNER TO {DEFINER}")
    op.execute(f"ALTER FUNCTION {NEW_CORRECT_SIG} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {NEW_CORRECT_SIG} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {NEW_CORRECT_SIG} TO {APP}")

    _replace_chain_erasure_function()
    op.execute(f"ALTER FUNCTION {ERASE_SIG} OWNER TO {DEFINER}")
    op.execute(f"ALTER FUNCTION {ERASE_SIG} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {ERASE_SIG} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {ERASE_SIG} TO {APP}")

    _create_document_transition_guard()
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def downgrade() -> None:
    op.execute(
        f"DROP TRIGGER IF EXISTS trg_profile_documents_guard_lab_erasure "
        f"ON {S}.profile_documents"
    )
    op.execute(f"DROP FUNCTION IF EXISTS {TRIGGER_SIG}")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {NEW_CORRECT_SIG} FROM {APP}")
    op.execute(f"DROP FUNCTION IF EXISTS {NEW_CORRECT_SIG}")
    op.execute(f"GRANT EXECUTE ON FUNCTION {OLD_CORRECT_SIG} TO {APP}")
    # The strengthened same-signature chain erasure function is intentionally
    # retained when stepping back to 0060. Weakening concurrency safety during
    # a partial downgrade would be unsafe; migration 0059 removes the function
    # during a complete downgrade to 0058/base.
