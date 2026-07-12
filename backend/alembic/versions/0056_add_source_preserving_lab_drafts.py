"""Add HC-017 E1 source-preserving laboratory drafts.

Revision ID: 0056
Revises: 0055

Drafts are owner/editor-only structured proposals backed by finalized D2 OCR
transcription. They are not confirmed observations and never enter analytics.
"""

from __future__ import annotations

from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"

VALIDATE_PAYLOAD_SIG = f"{S}.app_validate_lab_draft_payload(jsonb)"
CREATE_DRAFT_SIG = (
    f"{S}.app_create_lab_observation_draft("
    "uuid,uuid,timestamp with time zone,timestamp with time zone,"
    "timestamp with time zone,jsonb,uuid,text)"
)
UPDATE_DRAFT_SIG = (
    f"{S}.app_update_lab_observation_draft("
    "uuid,timestamp with time zone,timestamp with time zone,"
    "timestamp with time zone,timestamp with time zone,jsonb,uuid,text)"
)
SET_SOURCES_SIG = (
    f"{S}.app_set_lab_draft_sources("
    "uuid,timestamp with time zone,jsonb,uuid,text)"
)
SET_STATUS_SIG = (
    f"{S}.app_set_lab_observation_draft_status("
    "uuid,text,timestamp with time zone,uuid,text)"
)

AUDIT_ACTIONS_0055 = """
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
            'clinical_section.confirmed_none_cleared',
            'clinical_record.erased',
            'document.uploaded',
            'document.scan_clean',
            'document.scan_rejected',
            'document.render_ready',
            'document.render_failed',
            'document.storage_missing',
            'document.ocr_ready',
            'document.ocr_failed',
            'document.ocr_storage_missing',
            'document.ocr_candidate_reviewed',
            'document.ocr_patient_decision',
            'document.ocr_review_finalized'
"""


def _replace_audit_constraint(*, include_lab_draft_actions: bool) -> None:
    actions = AUDIT_ACTIONS_0055
    if include_lab_draft_actions:
        actions = (
            f"{actions.rstrip()},\n"
            "            'lab.draft_created',\n"
            "            'lab.draft_updated',\n"
            "            'lab.draft_sources_changed',\n"
            "            'lab.draft_status_changed'\n"
        )
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


def _create_functions() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_validate_lab_draft_payload(p_payload jsonb)
        RETURNS boolean
        LANGUAGE plpgsql
        IMMUTABLE
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          value_kind text;
          observed_precision text;
          comparator_value text;
          unit_not_present boolean;
          range_not_present boolean;
          observed_unknown boolean;
          allowed_keys text[] := ARRAY[
            'source_analyte_text','source_value_text','value_kind','comparator',
            'numeric_value','text_value','qualitative_value_text',
            'source_unit_text','unit_not_present',
            'source_reference_range_text','reference_range_not_present',
            'source_observed_at_text','observed_time_unknown','observed_date',
            'observed_at','observed_precision','source_specimen_text',
            'source_flag_text','source_comment'
          ];
        BEGIN
          IF p_payload IS NULL OR jsonb_typeof(p_payload) <> 'object'
             OR p_payload - allowed_keys <> '{{}}'::jsonb THEN
            RAISE EXCEPTION 'Invalid Lab draft payload' USING ERRCODE = 'HC422';
          END IF;

          IF coalesce(length(btrim(p_payload ->> 'source_analyte_text')), 0)
               NOT BETWEEN 1 AND 500
             OR (p_payload ->> 'source_analyte_text') ~ '[[:cntrl:]]'
             OR coalesce(length(btrim(p_payload ->> 'source_value_text')), 0)
               NOT BETWEEN 1 AND 500
             OR (p_payload ->> 'source_value_text') ~ '[[:cntrl:]]' THEN
            RAISE EXCEPTION 'Invalid source Lab text' USING ERRCODE = 'HC422';
          END IF;

          value_kind := p_payload ->> 'value_kind';
          comparator_value := nullif(p_payload ->> 'comparator', '');
          IF value_kind NOT IN ('numeric','text','qualitative')
             OR (comparator_value IS NOT NULL
                 AND comparator_value NOT IN ('<','<=','=','>=','>')) THEN
            RAISE EXCEPTION 'Invalid Lab value kind' USING ERRCODE = 'HC422';
          END IF;

          IF value_kind = 'numeric' THEN
            IF coalesce(p_payload ->> 'numeric_value', '')
                 !~ '^-?[0-9]+([.][0-9]+)?$'
               OR p_payload ? 'text_value'
               OR p_payload ? 'qualitative_value_text' THEN
              RAISE EXCEPTION 'Invalid numeric Lab value' USING ERRCODE = 'HC422';
            END IF;
          ELSIF value_kind = 'text' THEN
            IF comparator_value IS NOT NULL
               OR coalesce(length(btrim(p_payload ->> 'text_value')), 0)
                    NOT BETWEEN 1 AND 500
               OR (p_payload ->> 'text_value') ~ '[[:cntrl:]]'
               OR p_payload ? 'numeric_value'
               OR p_payload ? 'qualitative_value_text' THEN
              RAISE EXCEPTION 'Invalid text Lab value' USING ERRCODE = 'HC422';
            END IF;
          ELSE
            IF comparator_value IS NOT NULL
               OR coalesce(length(btrim(p_payload ->> 'qualitative_value_text')), 0)
                    NOT BETWEEN 1 AND 500
               OR (p_payload ->> 'qualitative_value_text') ~ '[[:cntrl:]]'
               OR p_payload ? 'numeric_value'
               OR p_payload ? 'text_value' THEN
              RAISE EXCEPTION 'Invalid qualitative Lab value' USING ERRCODE = 'HC422';
            END IF;
          END IF;

          IF jsonb_typeof(p_payload -> 'unit_not_present') <> 'boolean'
             OR jsonb_typeof(p_payload -> 'reference_range_not_present') <> 'boolean'
             OR jsonb_typeof(p_payload -> 'observed_time_unknown') <> 'boolean' THEN
            RAISE EXCEPTION 'Explicit absence decisions are required'
              USING ERRCODE = 'HC422';
          END IF;
          unit_not_present := (p_payload ->> 'unit_not_present')::boolean;
          range_not_present :=
            (p_payload ->> 'reference_range_not_present')::boolean;
          observed_unknown := (p_payload ->> 'observed_time_unknown')::boolean;

          IF unit_not_present = (nullif(btrim(p_payload ->> 'source_unit_text'), '')
                                  IS NOT NULL)
             OR range_not_present =
                (nullif(btrim(p_payload ->> 'source_reference_range_text'), '')
                 IS NOT NULL)
             OR observed_unknown =
                (nullif(btrim(p_payload ->> 'source_observed_at_text'), '')
                 IS NOT NULL) THEN
            RAISE EXCEPTION 'Conflicting source absence decision'
              USING ERRCODE = 'HC422';
          END IF;

          observed_precision := p_payload ->> 'observed_precision';
          IF observed_precision NOT IN ('unknown','date','datetime')
             OR (observed_precision = 'unknown'
                 AND (p_payload ? 'observed_date' OR p_payload ? 'observed_at'))
             OR (observed_precision = 'date'
                 AND (NOT p_payload ? 'observed_date' OR p_payload ? 'observed_at'))
             OR (observed_precision = 'datetime'
                 AND (NOT p_payload ? 'observed_at' OR p_payload ? 'observed_date')) THEN
            RAISE EXCEPTION 'Invalid observed time representation'
              USING ERRCODE = 'HC422';
          END IF;
          IF observed_unknown AND observed_precision <> 'unknown' THEN
            RAISE EXCEPTION 'Unknown observed time must use unknown precision'
              USING ERRCODE = 'HC422';
          END IF;

          IF coalesce(length(p_payload ->> 'source_unit_text'), 0) > 200
             OR coalesce(length(p_payload ->> 'source_reference_range_text'), 0) > 500
             OR coalesce(length(p_payload ->> 'source_observed_at_text'), 0) > 500
             OR coalesce(length(p_payload ->> 'source_specimen_text'), 0) > 500
             OR coalesce(length(p_payload ->> 'source_flag_text'), 0) > 200
             OR coalesce(length(p_payload ->> 'source_comment'), 0) > 2000
             OR coalesce(p_payload ->> 'source_unit_text', '') ~ '[[:cntrl:]]'
             OR coalesce(p_payload ->> 'source_reference_range_text', '') ~ '[[:cntrl:]]'
             OR coalesce(p_payload ->> 'source_observed_at_text', '') ~ '[[:cntrl:]]'
             OR coalesce(p_payload ->> 'source_specimen_text', '') ~ '[[:cntrl:]]'
             OR coalesce(p_payload ->> 'source_flag_text', '') ~ '[[:cntrl:]]'
             OR coalesce(p_payload ->> 'source_comment', '') ~ '[[:cntrl:]]' THEN
            RAISE EXCEPTION 'Invalid optional source text' USING ERRCODE = 'HC422';
          END IF;

          RETURN true;
        EXCEPTION
          WHEN invalid_text_representation OR datetime_field_overflow
               OR numeric_value_out_of_range THEN
            RAISE EXCEPTION 'Invalid structured Lab value' USING ERRCODE = 'HC422';
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_create_lab_observation_draft(
          p_draft_id uuid,
          p_document_id uuid,
          p_expected_document_updated_at timestamptz,
          p_expected_review_finalized_at timestamptz,
          p_expected_patient_decision_updated_at timestamptz,
          p_payload jsonb,
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
          target_document {S}.profile_documents%ROWTYPE;
          target_run {S}.document_ocr_runs%ROWTYPE;
          target_decision {S}.document_ocr_patient_decisions%ROWTYPE;
          owner_id uuid;
          now_value timestamptz := pg_catalog.clock_timestamp();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Lab draft operation denied' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL OR p_draft_id IS NULL
             OR p_expected_document_updated_at IS NULL
             OR p_expected_review_finalized_at IS NULL
             OR p_expected_patient_decision_updated_at IS NULL THEN
            RAISE EXCEPTION 'Lab draft precondition is required'
              USING ERRCODE = 'HC428';
          END IF;
          IF p_request_id IS NOT NULL AND length(p_request_id) > 128 THEN
            RAISE EXCEPTION 'Invalid request id' USING ERRCODE = 'HC422';
          END IF;
          PERFORM {S}.app_validate_lab_draft_payload(p_payload);

          SELECT d.* INTO target_document
          FROM {S}.profile_documents d
          WHERE d.id = p_document_id
          FOR UPDATE;
          IF target_document.id IS NULL
             OR NOT {S}.app_can_edit_profile(target_document.profile_id) THEN
            RAISE EXCEPTION 'Document not found' USING ERRCODE = 'HC404';
          END IF;
          SELECT r.* INTO target_run
          FROM {S}.document_ocr_runs r
          WHERE r.id = target_document.current_ocr_run_id
            AND r.document_id = target_document.id
            AND r.profile_id = target_document.profile_id
          FOR UPDATE;
          SELECT pd.* INTO target_decision
          FROM {S}.document_ocr_patient_decisions pd
          WHERE pd.id = target_run.review_patient_decision_id
            AND pd.run_id = target_run.id
          FOR UPDATE;
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp WHERE hp.id = target_document.profile_id;

          IF target_run.id IS NULL OR target_decision.id IS NULL OR owner_id IS NULL
             OR target_document.status <> 'accepted'
             OR target_document.ocr_status <> 'reviewed'
             OR target_document.voided_at IS NOT NULL
             OR target_document.deletion_requested_at IS NOT NULL
             OR target_document.erased_at IS NOT NULL
             OR target_run.status <> 'succeeded'
             OR target_run.review_status <> 'finalized'
             OR target_decision.decision NOT IN ('match','not_present') THEN
            RAISE EXCEPTION 'Lab draft context is not available'
              USING ERRCODE = 'HC409';
          END IF;
          IF target_document.updated_at <> p_expected_document_updated_at
             OR target_run.review_finalized_at <> p_expected_review_finalized_at
             OR target_decision.updated_at <> p_expected_patient_decision_updated_at THEN
            RAISE EXCEPTION 'Lab draft source was updated elsewhere'
              USING ERRCODE = 'HC409';
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM {S}.user_consents uc
            WHERE uc.user_id = owner_id
              AND uc.consent_type = 'health_data_processing'
              AND uc.revoked_at IS NULL
          ) THEN
            RAISE EXCEPTION 'Health data consent is required'
              USING ERRCODE = 'HC409';
          END IF;

          INSERT INTO {S}.lab_observation_drafts (
            id, profile_id, document_id, ocr_run_id, patient_decision_id,
            status, source_analyte_text, source_value_text, value_kind,
            comparator, numeric_value, text_value, qualitative_value_text,
            source_unit_text, unit_not_present,
            source_reference_range_text, reference_range_not_present,
            source_observed_at_text, observed_time_unknown,
            observed_date, observed_at, observed_precision,
            source_specimen_text, source_flag_text, source_comment,
            created_by_user_id, updated_by_user_id, created_at, updated_at
          ) VALUES (
            p_draft_id, target_document.profile_id, target_document.id,
            target_run.id, target_decision.id, 'draft',
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
            actor_id, actor_id, now_value, now_value
          );

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_document.profile_id, actor_id,
            'lab_observation_draft', p_draft_id,
            'lab.draft_created', '{{}}'::jsonb, p_request_id
          );
          RETURN p_draft_id;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_update_lab_observation_draft(
          p_draft_id uuid,
          p_expected_updated_at timestamptz,
          p_expected_document_updated_at timestamptz,
          p_expected_review_finalized_at timestamptz,
          p_expected_patient_decision_updated_at timestamptz,
          p_payload jsonb,
          p_audit_event_id uuid,
          p_request_id text
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          actor_id uuid;
          target_draft {S}.lab_observation_drafts%ROWTYPE;
          target_document {S}.profile_documents%ROWTYPE;
          target_run {S}.document_ocr_runs%ROWTYPE;
          target_decision {S}.document_ocr_patient_decisions%ROWTYPE;
          owner_id uuid;
          now_value timestamptz := pg_catalog.clock_timestamp();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Lab draft operation denied' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL OR p_expected_updated_at IS NULL
             OR p_expected_document_updated_at IS NULL
             OR p_expected_review_finalized_at IS NULL
             OR p_expected_patient_decision_updated_at IS NULL THEN
            RAISE EXCEPTION 'Lab draft precondition is required'
              USING ERRCODE = 'HC428';
          END IF;
          IF p_request_id IS NOT NULL AND length(p_request_id) > 128 THEN
            RAISE EXCEPTION 'Invalid request id' USING ERRCODE = 'HC422';
          END IF;
          PERFORM {S}.app_validate_lab_draft_payload(p_payload);

          SELECT ld.* INTO target_draft
          FROM {S}.lab_observation_drafts ld
          WHERE ld.id = p_draft_id
          FOR UPDATE;
          IF target_draft.id IS NULL
             OR NOT {S}.app_can_edit_profile(target_draft.profile_id) THEN
            RAISE EXCEPTION 'Lab draft not found' USING ERRCODE = 'HC404';
          END IF;
          SELECT d.* INTO target_document
          FROM {S}.profile_documents d
          WHERE d.id = target_draft.document_id
            AND d.profile_id = target_draft.profile_id
          FOR UPDATE;
          SELECT r.* INTO target_run
          FROM {S}.document_ocr_runs r
          WHERE r.id = target_draft.ocr_run_id
          FOR UPDATE;
          SELECT pd.* INTO target_decision
          FROM {S}.document_ocr_patient_decisions pd
          WHERE pd.id = target_draft.patient_decision_id
          FOR UPDATE;
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp WHERE hp.id = target_draft.profile_id;

          IF target_draft.status <> 'draft'
             OR target_document.status <> 'accepted'
             OR target_document.ocr_status <> 'reviewed'
             OR target_document.voided_at IS NOT NULL
             OR target_document.deletion_requested_at IS NOT NULL
             OR target_document.erased_at IS NOT NULL
             OR target_run.status <> 'succeeded'
             OR target_run.review_status <> 'finalized'
             OR target_decision.decision NOT IN ('match','not_present')
             OR target_document.current_ocr_run_id <> target_run.id THEN
            RAISE EXCEPTION 'Lab draft context changed' USING ERRCODE = 'HC409';
          END IF;
          IF target_draft.updated_at <> p_expected_updated_at
             OR target_document.updated_at <> p_expected_document_updated_at
             OR target_run.review_finalized_at <> p_expected_review_finalized_at
             OR target_decision.updated_at <> p_expected_patient_decision_updated_at THEN
            RAISE EXCEPTION 'Lab draft was updated elsewhere'
              USING ERRCODE = 'HC409';
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM {S}.user_consents uc
            WHERE uc.user_id = owner_id
              AND uc.consent_type = 'health_data_processing'
              AND uc.revoked_at IS NULL
          ) THEN
            RAISE EXCEPTION 'Health data consent is required'
              USING ERRCODE = 'HC409';
          END IF;

          UPDATE {S}.lab_observation_drafts
          SET source_analyte_text = btrim(p_payload ->> 'source_analyte_text'),
              source_value_text = btrim(p_payload ->> 'source_value_text'),
              value_kind = p_payload ->> 'value_kind',
              comparator = nullif(p_payload ->> 'comparator',''),
              numeric_value = CASE WHEN p_payload ->> 'value_kind' = 'numeric'
                THEN (p_payload ->> 'numeric_value')::numeric ELSE NULL END,
              text_value = nullif(btrim(p_payload ->> 'text_value'),''),
              qualitative_value_text =
                nullif(btrim(p_payload ->> 'qualitative_value_text'),''),
              source_unit_text = nullif(btrim(p_payload ->> 'source_unit_text'),''),
              unit_not_present = (p_payload ->> 'unit_not_present')::boolean,
              source_reference_range_text =
                nullif(btrim(p_payload ->> 'source_reference_range_text'),''),
              reference_range_not_present =
                (p_payload ->> 'reference_range_not_present')::boolean,
              source_observed_at_text =
                nullif(btrim(p_payload ->> 'source_observed_at_text'),''),
              observed_time_unknown =
                (p_payload ->> 'observed_time_unknown')::boolean,
              observed_date = CASE WHEN p_payload ? 'observed_date'
                THEN (p_payload ->> 'observed_date')::date ELSE NULL END,
              observed_at = CASE WHEN p_payload ? 'observed_at'
                THEN (p_payload ->> 'observed_at')::timestamptz ELSE NULL END,
              observed_precision = p_payload ->> 'observed_precision',
              source_specimen_text =
                nullif(btrim(p_payload ->> 'source_specimen_text'),''),
              source_flag_text = nullif(btrim(p_payload ->> 'source_flag_text'),''),
              source_comment = nullif(btrim(p_payload ->> 'source_comment'),''),
              updated_by_user_id = actor_id,
              updated_at = now_value
          WHERE id = p_draft_id;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_draft.profile_id, actor_id,
            'lab_observation_draft', p_draft_id,
            'lab.draft_updated', '{{}}'::jsonb, p_request_id
          );
          RETURN true;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_set_lab_draft_sources(
          p_draft_id uuid,
          p_expected_updated_at timestamptz,
          p_sources jsonb,
          p_audit_event_id uuid,
          p_request_id text
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          actor_id uuid;
          target_draft {S}.lab_observation_drafts%ROWTYPE;
          source_count integer;
          now_value timestamptz := pg_catalog.clock_timestamp();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Lab source operation denied' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL OR p_expected_updated_at IS NULL THEN
            RAISE EXCEPTION 'Lab source precondition is required'
              USING ERRCODE = 'HC428';
          END IF;
          IF p_request_id IS NOT NULL AND length(p_request_id) > 128 THEN
            RAISE EXCEPTION 'Invalid request id' USING ERRCODE = 'HC422';
          END IF;
          IF p_sources IS NULL OR jsonb_typeof(p_sources) <> 'array'
             OR jsonb_array_length(p_sources) NOT BETWEEN 1 AND 100 THEN
            RAISE EXCEPTION 'Invalid Lab source manifest' USING ERRCODE = 'HC422';
          END IF;

          SELECT ld.* INTO target_draft
          FROM {S}.lab_observation_drafts ld
          WHERE ld.id = p_draft_id
          FOR UPDATE;
          IF target_draft.id IS NULL
             OR NOT {S}.app_can_edit_profile(target_draft.profile_id) THEN
            RAISE EXCEPTION 'Lab draft not found' USING ERRCODE = 'HC404';
          END IF;
          IF target_draft.status <> 'draft'
             OR target_draft.updated_at <> p_expected_updated_at THEN
            RAISE EXCEPTION 'Lab draft was updated elsewhere'
              USING ERRCODE = 'HC409';
          END IF;

          SELECT count(*) INTO source_count
          FROM jsonb_to_recordset(p_sources) AS x(
            candidate_id uuid,
            source_role text,
            expected_updated_at timestamptz
          )
          JOIN {S}.document_ocr_candidates c ON c.id = x.candidate_id
          WHERE c.run_id = target_draft.ocr_run_id
            AND c.document_id = target_draft.document_id
            AND c.profile_id = target_draft.profile_id
            AND c.status IN ('accepted','edited')
            AND c.reviewed_text IS NOT NULL
            AND c.updated_at = x.expected_updated_at
            AND x.source_role IN (
              'analyte','value','unit','reference_range',
              'observed_at','specimen','flag','comment'
            );
          IF source_count <> jsonb_array_length(p_sources)
             OR source_count <> (
               SELECT count(DISTINCT (x.candidate_id::text || ':' || x.source_role))
               FROM jsonb_to_recordset(p_sources) AS x(
                 candidate_id uuid,
                 source_role text,
                 expected_updated_at timestamptz
               )
             ) THEN
            RAISE EXCEPTION 'Lab source manifest changed or is invalid'
              USING ERRCODE = 'HC409';
          END IF;

          DELETE FROM {S}.lab_observation_draft_sources
          WHERE draft_id = p_draft_id;
          INSERT INTO {S}.lab_observation_draft_sources (
            draft_id, candidate_id, source_role, candidate_updated_at,
            profile_id, document_id, ocr_run_id, page_artifact_id, page_number
          )
          SELECT p_draft_id, c.id, x.source_role, c.updated_at,
                 c.profile_id, c.document_id, c.run_id,
                 c.page_artifact_id, c.page_number
          FROM jsonb_to_recordset(p_sources) AS x(
            candidate_id uuid,
            source_role text,
            expected_updated_at timestamptz
          )
          JOIN {S}.document_ocr_candidates c ON c.id = x.candidate_id;

          UPDATE {S}.lab_observation_drafts
          SET updated_by_user_id = actor_id, updated_at = now_value
          WHERE id = p_draft_id;
          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_draft.profile_id, actor_id,
            'lab_observation_draft', p_draft_id,
            'lab.draft_sources_changed', '{{}}'::jsonb, p_request_id
          );
          RETURN true;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_set_lab_observation_draft_status(
          p_draft_id uuid,
          p_status text,
          p_expected_updated_at timestamptz,
          p_audit_event_id uuid,
          p_request_id text
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          actor_id uuid;
          target_draft {S}.lab_observation_drafts%ROWTYPE;
          now_value timestamptz := pg_catalog.clock_timestamp();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Lab draft operation denied' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL OR p_expected_updated_at IS NULL THEN
            RAISE EXCEPTION 'Lab draft precondition is required'
              USING ERRCODE = 'HC428';
          END IF;
          IF p_status NOT IN ('ready','rejected') THEN
            RAISE EXCEPTION 'Invalid Lab draft status' USING ERRCODE = 'HC422';
          END IF;
          IF p_request_id IS NOT NULL AND length(p_request_id) > 128 THEN
            RAISE EXCEPTION 'Invalid request id' USING ERRCODE = 'HC422';
          END IF;

          SELECT ld.* INTO target_draft
          FROM {S}.lab_observation_drafts ld
          WHERE ld.id = p_draft_id
          FOR UPDATE;
          IF target_draft.id IS NULL
             OR NOT {S}.app_can_edit_profile(target_draft.profile_id) THEN
            RAISE EXCEPTION 'Lab draft not found' USING ERRCODE = 'HC404';
          END IF;
          IF target_draft.status <> 'draft'
             OR target_draft.updated_at <> p_expected_updated_at THEN
            RAISE EXCEPTION 'Lab draft was updated elsewhere'
              USING ERRCODE = 'HC409';
          END IF;
          IF p_status = 'ready' AND (
             NOT EXISTS (
               SELECT 1 FROM {S}.lab_observation_draft_sources s
               WHERE s.draft_id = p_draft_id AND s.source_role = 'analyte'
             ) OR NOT EXISTS (
               SELECT 1 FROM {S}.lab_observation_draft_sources s
               WHERE s.draft_id = p_draft_id AND s.source_role = 'value'
             )) THEN
            RAISE EXCEPTION 'Analyte and value provenance are required'
              USING ERRCODE = 'HC409';
          END IF;

          UPDATE {S}.lab_observation_drafts
          SET status = p_status,
              updated_by_user_id = actor_id,
              updated_at = now_value
          WHERE id = p_draft_id;
          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_draft.profile_id, actor_id,
            'lab_observation_draft', p_draft_id,
            'lab.draft_status_changed', '{{}}'::jsonb, p_request_id
          );
          RETURN true;
        END;
        $$
        """
    )

    for signature in (
        VALIDATE_PAYLOAD_SIG,
        CREATE_DRAFT_SIG,
        UPDATE_DRAFT_SIG,
        SET_SOURCES_SIG,
        SET_STATUS_SIG,
    ):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {DEFINER}")
        op.execute(f"ALTER FUNCTION {signature} SET row_security = off")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    for signature in (
        CREATE_DRAFT_SIG,
        UPDATE_DRAFT_SIG,
        SET_SOURCES_SIG,
        SET_STATUS_SIG,
    ):
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {S}.lab_observation_drafts (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          document_id uuid NOT NULL,
          ocr_run_id uuid NOT NULL REFERENCES {S}.document_ocr_runs(id) ON DELETE CASCADE,
          patient_decision_id uuid NOT NULL
            REFERENCES {S}.document_ocr_patient_decisions(id),
          status varchar(32) NOT NULL,
          source_analyte_text varchar(500) NOT NULL,
          source_value_text varchar(500) NOT NULL,
          value_kind varchar(32) NOT NULL,
          comparator varchar(8) NULL,
          numeric_value numeric(38,12) NULL,
          text_value varchar(500) NULL,
          qualitative_value_text varchar(500) NULL,
          source_unit_text varchar(200) NULL,
          unit_not_present boolean NOT NULL,
          source_reference_range_text varchar(500) NULL,
          reference_range_not_present boolean NOT NULL,
          source_observed_at_text varchar(500) NULL,
          observed_time_unknown boolean NOT NULL,
          observed_date date NULL,
          observed_at timestamptz NULL,
          observed_precision varchar(32) NOT NULL,
          source_specimen_text varchar(500) NULL,
          source_flag_text varchar(200) NULL,
          source_comment varchar(2000) NULL,
          created_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          updated_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_lab_observation_drafts_document_profile
            FOREIGN KEY (document_id, profile_id)
            REFERENCES {S}.profile_documents(id, profile_id) ON DELETE CASCADE,
          CONSTRAINT ck_lab_observation_drafts_status CHECK (
            status IN ('draft','ready','rejected')
          ),
          CONSTRAINT ck_lab_observation_drafts_value_kind CHECK (
            (value_kind = 'numeric' AND numeric_value IS NOT NULL
             AND text_value IS NULL AND qualitative_value_text IS NULL)
            OR
            (value_kind = 'text' AND numeric_value IS NULL
             AND text_value IS NOT NULL AND qualitative_value_text IS NULL
             AND comparator IS NULL)
            OR
            (value_kind = 'qualitative' AND numeric_value IS NULL
             AND text_value IS NULL AND qualitative_value_text IS NOT NULL
             AND comparator IS NULL)
          ),
          CONSTRAINT ck_lab_observation_drafts_unit CHECK (
            unit_not_present <> (source_unit_text IS NOT NULL)
          ),
          CONSTRAINT ck_lab_observation_drafts_range CHECK (
            reference_range_not_present <>
              (source_reference_range_text IS NOT NULL)
          ),
          CONSTRAINT ck_lab_observation_drafts_observed_source CHECK (
            observed_time_unknown <> (source_observed_at_text IS NOT NULL)
          ),
          CONSTRAINT ck_lab_observation_drafts_observed_precision CHECK (
            (observed_precision = 'unknown' AND observed_date IS NULL
             AND observed_at IS NULL)
            OR
            (observed_precision = 'date' AND observed_date IS NOT NULL
             AND observed_at IS NULL)
            OR
            (observed_precision = 'datetime' AND observed_date IS NULL
             AND observed_at IS NOT NULL)
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_lab_observation_drafts_document_status "
        f"ON {S}.lab_observation_drafts (document_id, status, created_at)"
    )
    op.execute(
        f"""
        CREATE TABLE {S}.lab_observation_draft_sources (
          draft_id uuid NOT NULL REFERENCES {S}.lab_observation_drafts(id)
            ON DELETE CASCADE,
          candidate_id uuid NOT NULL REFERENCES {S}.document_ocr_candidates(id),
          source_role varchar(32) NOT NULL,
          candidate_updated_at timestamptz NOT NULL,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          document_id uuid NOT NULL,
          ocr_run_id uuid NOT NULL REFERENCES {S}.document_ocr_runs(id),
          page_artifact_id uuid NOT NULL REFERENCES {S}.document_artifacts(id),
          page_number integer NOT NULL,
          PRIMARY KEY (draft_id, candidate_id, source_role),
          CONSTRAINT fk_lab_draft_sources_document_profile
            FOREIGN KEY (document_id, profile_id)
            REFERENCES {S}.profile_documents(id, profile_id) ON DELETE CASCADE,
          CONSTRAINT ck_lab_draft_sources_role CHECK (
            source_role IN (
              'analyte','value','unit','reference_range',
              'observed_at','specimen','flag','comment'
            )
          ),
          CONSTRAINT ck_lab_draft_sources_page CHECK (page_number >= 1)
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_lab_draft_sources_candidate "
        f"ON {S}.lab_observation_draft_sources (candidate_id, draft_id)"
    )

    for table in ("lab_observation_drafts", "lab_observation_draft_sources"):
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY lab_observation_drafts_select "
        f"ON {S}.lab_observation_drafts FOR SELECT "
        f"USING ({S}.app_can_edit_profile(profile_id))"
    )
    op.execute(
        f"CREATE POLICY lab_observation_draft_sources_select "
        f"ON {S}.lab_observation_draft_sources FOR SELECT "
        f"USING ({S}.app_can_edit_profile(profile_id))"
    )
    op.execute(f"GRANT SELECT ON {S}.lab_observation_drafts TO {APP}")
    op.execute(f"GRANT SELECT ON {S}.lab_observation_draft_sources TO {APP}")
    op.execute(
        f"REVOKE INSERT, UPDATE, DELETE ON {S}.lab_observation_drafts FROM {APP}"
    )
    op.execute(
        f"REVOKE INSERT, UPDATE, DELETE ON {S}.lab_observation_draft_sources FROM {APP}"
    )

    _replace_audit_constraint(include_lab_draft_actions=True)

    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
        f"{S}.lab_observation_drafts, {S}.lab_observation_draft_sources TO {DEFINER}"
    )
    op.execute(f"GRANT SELECT ON {S}.document_ocr_candidates TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.document_ocr_runs TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.document_ocr_patient_decisions TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.profile_documents TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.health_profiles TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.user_consents TO {DEFINER}")
    op.execute(f"GRANT INSERT ON {S}.profile_audit_events TO {DEFINER}")

    _create_functions()


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM {S}.lab_observation_drafts)
             OR EXISTS (SELECT 1 FROM {S}.lab_observation_draft_sources) THEN
            RAISE EXCEPTION 'Cannot downgrade 0056 while Lab draft data exists';
          END IF;
        END $$;
        """
    )

    for signature in (
        SET_STATUS_SIG,
        SET_SOURCES_SIG,
        UPDATE_DRAFT_SIG,
        CREATE_DRAFT_SIG,
    ):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
    op.execute(f"DROP FUNCTION IF EXISTS {VALIDATE_PAYLOAD_SIG}")

    _replace_audit_constraint(include_lab_draft_actions=False)

    op.execute(
        f"DROP POLICY IF EXISTS lab_observation_draft_sources_select "
        f"ON {S}.lab_observation_draft_sources"
    )
    op.execute(
        f"DROP POLICY IF EXISTS lab_observation_drafts_select "
        f"ON {S}.lab_observation_drafts"
    )
    op.execute(f"REVOKE SELECT ON {S}.lab_observation_draft_sources FROM {APP}")
    op.execute(f"REVOKE SELECT ON {S}.lab_observation_drafts FROM {APP}")
    op.execute(f"DROP TABLE {S}.lab_observation_draft_sources")
    op.execute(f"DROP TABLE {S}.lab_observation_drafts")
