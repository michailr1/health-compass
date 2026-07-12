"""Require current document/OCR/patient context for every E1 draft mutation.

Revision ID: 0057
Revises: 0056
"""

from __future__ import annotations

from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"

OLD_SET_SOURCES_SIG = (
    f"{S}.app_set_lab_draft_sources("
    "uuid,timestamp with time zone,jsonb,uuid,text)"
)
OLD_SET_STATUS_SIG = (
    f"{S}.app_set_lab_observation_draft_status("
    "uuid,text,timestamp with time zone,uuid,text)"
)
SET_SOURCES_SIG = (
    f"{S}.app_set_lab_draft_sources("
    "uuid,timestamp with time zone,timestamp with time zone,"
    "timestamp with time zone,timestamp with time zone,jsonb,uuid,text)"
)
SET_STATUS_SIG = (
    f"{S}.app_set_lab_observation_draft_status("
    "uuid,text,timestamp with time zone,timestamp with time zone,"
    "timestamp with time zone,timestamp with time zone,uuid,text)"
)


def _drop_app_function(signature: str) -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
    op.execute(f"DROP FUNCTION IF EXISTS {signature}")


def _create_hardened_functions() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_set_lab_draft_sources(
          p_draft_id uuid,
          p_expected_updated_at timestamptz,
          p_expected_document_updated_at timestamptz,
          p_expected_review_finalized_at timestamptz,
          p_expected_patient_decision_updated_at timestamptz,
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
          target_document {S}.profile_documents%ROWTYPE;
          target_run {S}.document_ocr_runs%ROWTYPE;
          target_decision {S}.document_ocr_patient_decisions%ROWTYPE;
          owner_id uuid;
          source_count integer;
          now_value timestamptz := pg_catalog.clock_timestamp();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Lab source operation denied' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL OR p_expected_updated_at IS NULL
             OR p_expected_document_updated_at IS NULL
             OR p_expected_review_finalized_at IS NULL
             OR p_expected_patient_decision_updated_at IS NULL THEN
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
          IF EXISTS (
            SELECT 1
            FROM jsonb_array_elements(p_sources) item
            WHERE jsonb_typeof(item) <> 'object'
               OR item - ARRAY['candidate_id','source_role','expected_updated_at']
                    <> '{{}}'::jsonb
          ) THEN
            RAISE EXCEPTION 'Invalid Lab source manifest keys'
              USING ERRCODE = 'HC422';
          END IF;

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
            AND r.document_id = target_document.id
            AND r.profile_id = target_document.profile_id
          FOR UPDATE;
          SELECT pd.* INTO target_decision
          FROM {S}.document_ocr_patient_decisions pd
          WHERE pd.id = target_draft.patient_decision_id
            AND pd.run_id = target_run.id
          FOR UPDATE;
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp WHERE hp.id = target_draft.profile_id;

          IF target_draft.status <> 'draft'
             OR target_document.id IS NULL OR target_run.id IS NULL
             OR target_decision.id IS NULL OR owner_id IS NULL
             OR target_document.status <> 'accepted'
             OR target_document.ocr_status <> 'reviewed'
             OR target_document.current_ocr_run_id <> target_run.id
             OR target_document.voided_at IS NOT NULL
             OR target_document.deletion_requested_at IS NOT NULL
             OR target_document.erased_at IS NOT NULL
             OR target_run.status <> 'succeeded'
             OR target_run.review_status <> 'finalized'
             OR target_run.review_patient_decision_id <> target_decision.id
             OR target_decision.decision NOT IN ('match','not_present') THEN
            RAISE EXCEPTION 'Lab draft context changed' USING ERRCODE = 'HC409';
          END IF;
          IF target_draft.updated_at <> p_expected_updated_at
             OR target_document.updated_at <> p_expected_document_updated_at
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

          SELECT count(*) INTO source_count
          FROM jsonb_to_recordset(p_sources) AS x(
            candidate_id uuid,
            source_role text,
            expected_updated_at timestamptz
          )
          JOIN {S}.document_ocr_candidates c ON c.id = x.candidate_id
          WHERE c.run_id = target_run.id
            AND c.document_id = target_document.id
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
          p_expected_document_updated_at timestamptz,
          p_expected_review_finalized_at timestamptz,
          p_expected_patient_decision_updated_at timestamptz,
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
          SELECT d.* INTO target_document
          FROM {S}.profile_documents d
          WHERE d.id = target_draft.document_id
            AND d.profile_id = target_draft.profile_id
          FOR UPDATE;
          SELECT r.* INTO target_run
          FROM {S}.document_ocr_runs r
          WHERE r.id = target_draft.ocr_run_id
            AND r.document_id = target_document.id
            AND r.profile_id = target_document.profile_id
          FOR UPDATE;
          SELECT pd.* INTO target_decision
          FROM {S}.document_ocr_patient_decisions pd
          WHERE pd.id = target_draft.patient_decision_id
            AND pd.run_id = target_run.id
          FOR UPDATE;
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp WHERE hp.id = target_draft.profile_id;

          IF target_draft.status <> 'draft'
             OR target_document.id IS NULL OR target_run.id IS NULL
             OR target_decision.id IS NULL OR owner_id IS NULL
             OR target_document.status <> 'accepted'
             OR target_document.ocr_status <> 'reviewed'
             OR target_document.current_ocr_run_id <> target_run.id
             OR target_document.voided_at IS NOT NULL
             OR target_document.deletion_requested_at IS NOT NULL
             OR target_document.erased_at IS NOT NULL
             OR target_run.status <> 'succeeded'
             OR target_run.review_status <> 'finalized'
             OR target_run.review_patient_decision_id <> target_decision.id
             OR target_decision.decision NOT IN ('match','not_present') THEN
            RAISE EXCEPTION 'Lab draft context changed' USING ERRCODE = 'HC409';
          END IF;
          IF target_draft.updated_at <> p_expected_updated_at
             OR target_document.updated_at <> p_expected_document_updated_at
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

          IF p_status = 'ready' AND (
             NOT EXISTS (
               SELECT 1 FROM {S}.lab_observation_draft_sources s
               WHERE s.draft_id = p_draft_id AND s.source_role = 'analyte'
             ) OR NOT EXISTS (
               SELECT 1 FROM {S}.lab_observation_draft_sources s
               WHERE s.draft_id = p_draft_id AND s.source_role = 'value'
             ) OR EXISTS (
               SELECT 1
               FROM {S}.lab_observation_draft_sources s
               LEFT JOIN {S}.document_ocr_candidates c
                 ON c.id = s.candidate_id
               WHERE s.draft_id = p_draft_id
                 AND (
                   c.id IS NULL
                   OR c.run_id <> target_run.id
                   OR c.document_id <> target_document.id
                   OR c.profile_id <> target_draft.profile_id
                   OR c.status NOT IN ('accepted','edited')
                   OR c.reviewed_text IS NULL
                   OR c.updated_at <> s.candidate_updated_at
                 )
             )) THEN
            RAISE EXCEPTION 'Current analyte and value provenance are required'
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

    for signature in (SET_SOURCES_SIG, SET_STATUS_SIG):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {DEFINER}")
        op.execute(f"ALTER FUNCTION {signature} SET row_security = off")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def upgrade() -> None:
    _drop_app_function(OLD_SET_SOURCES_SIG)
    _drop_app_function(OLD_SET_STATUS_SIG)
    _create_hardened_functions()


def downgrade() -> None:
    _drop_app_function(SET_SOURCES_SIG)
    _drop_app_function(SET_STATUS_SIG)
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_set_lab_draft_sources(
          p_draft_id uuid,
          p_expected_updated_at timestamptz,
          p_sources jsonb,
          p_audit_event_id uuid,
          p_request_id text
        ) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = '' SET row_security = off
        AS $$
        BEGIN
          RAISE EXCEPTION 'Lab source mutation disabled after secure downgrade'
            USING ERRCODE = 'HC409';
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
        ) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = '' SET row_security = off
        AS $$
        BEGIN
          RAISE EXCEPTION 'Lab status mutation disabled after secure downgrade'
            USING ERRCODE = 'HC409';
        END;
        $$
        """
    )
    for signature in (OLD_SET_SOURCES_SIG, OLD_SET_STATUS_SIG):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {DEFINER}")
        op.execute(f"ALTER FUNCTION {signature} SET row_security = off")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")
