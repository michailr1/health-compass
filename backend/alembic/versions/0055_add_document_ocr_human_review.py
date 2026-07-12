"""Add HC-017 D2 human OCR review and explicit patient matching.

Revision ID: 0055
Revises: 0054

This migration adds owner/editor review mutations, patient decisions and atomic
review finalization. Reviewed OCR text remains document transcription and no
clinical or laboratory facts are created.
"""

from __future__ import annotations

from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"

REVIEW_CANDIDATE_SIG = (
    f"{S}.app_review_document_ocr_candidate("
    "uuid,text,text,text,timestamp with time zone,uuid,text)"
)
PATIENT_DECISION_SIG = (
    f"{S}.app_set_document_ocr_patient_decision("
    "uuid,uuid,text,text,timestamp with time zone,timestamp with time zone,uuid,text)"
)
FINALIZE_REVIEW_SIG = (
    f"{S}.app_finalize_document_ocr_review("
    "uuid,timestamp with time zone,jsonb,timestamp with time zone,uuid,text)"
)

AUDIT_ACTIONS_0054 = """
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
            'document.ocr_storage_missing'
"""


def _replace_audit_constraint(*, include_review_actions: bool) -> None:
    actions = AUDIT_ACTIONS_0054
    if include_review_actions:
        actions = (
            f"{actions.rstrip()},\n"
            "            'document.ocr_candidate_reviewed',\n"
            "            'document.ocr_patient_decision',\n"
            "            'document.ocr_review_finalized'\n"
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


def _create_review_functions() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_review_document_ocr_candidate(
          p_candidate_id uuid,
          p_action text,
          p_reviewed_text text,
          p_review_note text,
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
          target_candidate {S}.document_ocr_candidates%ROWTYPE;
          target_document {S}.profile_documents%ROWTYPE;
          target_run {S}.document_ocr_runs%ROWTYPE;
          owner_id uuid;
          now_value timestamptz := pg_catalog.now();
          next_text text;
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'OCR review operation denied' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL THEN
            RAISE EXCEPTION 'OCR review operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_expected_updated_at IS NULL THEN
            RAISE EXCEPTION 'expected_updated_at is required' USING ERRCODE = 'HC428';
          END IF;
          IF p_action NOT IN ('accept','edit','reject','defer') THEN
            RAISE EXCEPTION 'Invalid OCR review action' USING ERRCODE = 'HC422';
          END IF;
          IF p_request_id IS NOT NULL AND length(p_request_id) > 128 THEN
            RAISE EXCEPTION 'Invalid request id' USING ERRCODE = 'HC422';
          END IF;
          IF p_review_note IS NOT NULL AND (
               length(p_review_note) NOT BETWEEN 1 AND 500
               OR p_review_note ~ '[[:cntrl:]]'
          ) THEN
            RAISE EXCEPTION 'Invalid OCR review note' USING ERRCODE = 'HC422';
          END IF;

          SELECT c.* INTO target_candidate
          FROM {S}.document_ocr_candidates c
          WHERE c.id = p_candidate_id
          FOR UPDATE;
          IF target_candidate.id IS NULL THEN
            RAISE EXCEPTION 'OCR candidate not found' USING ERRCODE = 'HC404';
          END IF;

          SELECT d.* INTO target_document
          FROM {S}.profile_documents d
          WHERE d.id = target_candidate.document_id
            AND d.profile_id = target_candidate.profile_id
          FOR UPDATE;
          SELECT r.* INTO target_run
          FROM {S}.document_ocr_runs r
          WHERE r.id = target_candidate.run_id
            AND r.document_id = target_candidate.document_id
            AND r.profile_id = target_candidate.profile_id
          FOR UPDATE;
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp
          WHERE hp.id = target_candidate.profile_id;

          IF target_document.id IS NULL OR target_run.id IS NULL OR owner_id IS NULL
             OR NOT {S}.app_can_edit_profile(target_candidate.profile_id) THEN
            RAISE EXCEPTION 'OCR candidate not found' USING ERRCODE = 'HC404';
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM {S}.user_consents uc
            WHERE uc.user_id = owner_id
              AND uc.consent_type = 'health_data_processing'
              AND uc.revoked_at IS NULL
          ) THEN
            RAISE EXCEPTION 'Health data consent is required' USING ERRCODE = 'HC409';
          END IF;
          IF target_document.current_ocr_run_id <> target_candidate.run_id
             OR target_document.ocr_status <> 'review_required'
             OR target_run.status <> 'succeeded'
             OR target_run.review_status = 'finalized' THEN
            RAISE EXCEPTION 'OCR review state conflict' USING ERRCODE = 'HC409';
          END IF;
          IF target_candidate.updated_at <> p_expected_updated_at THEN
            RAISE EXCEPTION 'OCR candidate was updated elsewhere' USING ERRCODE = 'HC409';
          END IF;

          IF p_action = 'accept' THEN
            IF p_reviewed_text IS NOT NULL
               AND p_reviewed_text IS DISTINCT FROM target_candidate.original_text THEN
              RAISE EXCEPTION 'Accept cannot change OCR text' USING ERRCODE = 'HC422';
            END IF;
            next_text := target_candidate.original_text;
          ELSIF p_action = 'edit' THEN
            IF p_reviewed_text IS NULL
               OR length(p_reviewed_text) NOT BETWEEN 1 AND 4000
               OR p_reviewed_text ~ '[[:cntrl:]]'
               OR p_reviewed_text = target_candidate.original_text THEN
              RAISE EXCEPTION 'Invalid edited OCR text' USING ERRCODE = 'HC422';
            END IF;
            next_text := p_reviewed_text;
          ELSE
            IF p_reviewed_text IS NOT NULL THEN
              RAISE EXCEPTION 'Rejected or deferred text must be empty' USING ERRCODE = 'HC422';
            END IF;
            next_text := NULL;
          END IF;

          UPDATE {S}.document_ocr_candidates
          SET status = CASE p_action
                WHEN 'accept' THEN 'accepted'
                WHEN 'edit' THEN 'edited'
                WHEN 'reject' THEN 'rejected'
                ELSE 'deferred'
              END,
              reviewed_text = next_text,
              reviewed_by_user_id = actor_id,
              reviewed_at = now_value,
              review_note = p_review_note,
              updated_at = now_value
          WHERE id = p_candidate_id;

          UPDATE {S}.document_ocr_runs
          SET review_status = 'in_progress', updated_at = now_value
          WHERE id = target_run.id AND review_status <> 'finalized';

          UPDATE {S}.profile_documents
          SET updated_at = now_value
          WHERE id = target_document.id AND profile_id = target_document.profile_id;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_candidate.profile_id, actor_id,
            'document_ocr_candidate', target_candidate.id,
            'document.ocr_candidate_reviewed', '{{}}'::jsonb, p_request_id
          );
          RETURN true;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_set_document_ocr_patient_decision(
          p_document_id uuid,
          p_decision_id uuid,
          p_decision text,
          p_note text,
          p_expected_document_updated_at timestamptz,
          p_expected_decision_updated_at timestamptz,
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
          target_document {S}.profile_documents%ROWTYPE;
          target_run {S}.document_ocr_runs%ROWTYPE;
          target_decision {S}.document_ocr_patient_decisions%ROWTYPE;
          owner_id uuid;
          now_value timestamptz := pg_catalog.now();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'OCR patient decision denied' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL THEN
            RAISE EXCEPTION 'OCR patient decision denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_expected_document_updated_at IS NULL THEN
            RAISE EXCEPTION 'expected_document_updated_at is required' USING ERRCODE = 'HC428';
          END IF;
          IF p_decision NOT IN ('unknown','match','mismatch','not_present') THEN
            RAISE EXCEPTION 'Invalid patient decision' USING ERRCODE = 'HC422';
          END IF;
          IF p_note IS NOT NULL AND (
               length(p_note) NOT BETWEEN 1 AND 500 OR p_note ~ '[[:cntrl:]]'
          ) THEN
            RAISE EXCEPTION 'Invalid patient decision note' USING ERRCODE = 'HC422';
          END IF;
          IF p_request_id IS NOT NULL AND length(p_request_id) > 128 THEN
            RAISE EXCEPTION 'Invalid request id' USING ERRCODE = 'HC422';
          END IF;

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
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp WHERE hp.id = target_document.profile_id;

          IF target_run.id IS NULL OR owner_id IS NULL
             OR target_document.ocr_status <> 'review_required'
             OR target_run.status <> 'succeeded'
             OR target_run.review_status = 'finalized' THEN
            RAISE EXCEPTION 'OCR review state conflict' USING ERRCODE = 'HC409';
          END IF;
          IF target_document.updated_at <> p_expected_document_updated_at THEN
            RAISE EXCEPTION 'Document was updated elsewhere' USING ERRCODE = 'HC409';
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM {S}.user_consents uc
            WHERE uc.user_id = owner_id
              AND uc.consent_type = 'health_data_processing'
              AND uc.revoked_at IS NULL
          ) THEN
            RAISE EXCEPTION 'Health data consent is required' USING ERRCODE = 'HC409';
          END IF;

          SELECT pd.* INTO target_decision
          FROM {S}.document_ocr_patient_decisions pd
          WHERE pd.run_id = target_run.id
          FOR UPDATE;

          IF target_decision.id IS NULL THEN
            IF p_expected_decision_updated_at IS NOT NULL THEN
              RAISE EXCEPTION 'Patient decision was updated elsewhere' USING ERRCODE = 'HC409';
            END IF;
            INSERT INTO {S}.document_ocr_patient_decisions (
              id, run_id, document_id, profile_id, decision, note,
              decided_by_user_id, decided_at, created_at, updated_at
            ) VALUES (
              p_decision_id, target_run.id, target_document.id,
              target_document.profile_id, p_decision, p_note,
              actor_id, now_value, now_value, now_value
            );
          ELSE
            IF target_decision.id <> p_decision_id
               OR p_expected_decision_updated_at IS NULL
               OR target_decision.updated_at <> p_expected_decision_updated_at THEN
              RAISE EXCEPTION 'Patient decision was updated elsewhere' USING ERRCODE = 'HC409';
            END IF;
            UPDATE {S}.document_ocr_patient_decisions
            SET decision = p_decision,
                note = p_note,
                decided_by_user_id = actor_id,
                decided_at = now_value,
                updated_at = now_value
            WHERE id = target_decision.id;
          END IF;

          UPDATE {S}.document_ocr_runs
          SET review_status = 'in_progress', updated_at = now_value
          WHERE id = target_run.id AND review_status <> 'finalized';
          UPDATE {S}.profile_documents
          SET updated_at = now_value
          WHERE id = target_document.id AND profile_id = target_document.profile_id;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_document.profile_id, actor_id,
            'document_ocr_patient_decision', p_decision_id,
            'document.ocr_patient_decision', '{{}}'::jsonb, p_request_id
          );
          RETURN true;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_finalize_document_ocr_review(
          p_document_id uuid,
          p_expected_document_updated_at timestamptz,
          p_expected_candidate_versions jsonb,
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
          target_document {S}.profile_documents%ROWTYPE;
          target_run {S}.document_ocr_runs%ROWTYPE;
          target_decision {S}.document_ocr_patient_decisions%ROWTYPE;
          owner_id uuid;
          candidate_count integer;
          expected_count integer;
          expected_distinct integer;
          unresolved_count integer;
          now_value timestamptz := pg_catalog.now();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'OCR review finalization denied' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL THEN
            RAISE EXCEPTION 'OCR review finalization denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_expected_document_updated_at IS NULL
             OR p_expected_patient_decision_updated_at IS NULL THEN
            RAISE EXCEPTION 'Review preconditions are required' USING ERRCODE = 'HC428';
          END IF;
          IF pg_catalog.jsonb_typeof(p_expected_candidate_versions) <> 'array'
             OR pg_catalog.jsonb_array_length(p_expected_candidate_versions) > 5000 THEN
            RAISE EXCEPTION 'Invalid candidate manifest' USING ERRCODE = 'HC422';
          END IF;
          IF p_request_id IS NOT NULL AND length(p_request_id) > 128 THEN
            RAISE EXCEPTION 'Invalid request id' USING ERRCODE = 'HC422';
          END IF;

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
          WHERE pd.run_id = target_run.id
          FOR UPDATE;
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp WHERE hp.id = target_document.profile_id;

          IF target_run.id IS NULL OR target_decision.id IS NULL OR owner_id IS NULL
             OR target_run.status <> 'succeeded' THEN
            RAISE EXCEPTION 'OCR review state conflict' USING ERRCODE = 'HC409';
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM {S}.user_consents uc
            WHERE uc.user_id = owner_id
              AND uc.consent_type = 'health_data_processing'
              AND uc.revoked_at IS NULL
          ) THEN
            RAISE EXCEPTION 'Health data consent is required' USING ERRCODE = 'HC409';
          END IF;

          IF target_document.ocr_status = 'reviewed'
             AND target_run.review_status = 'finalized' THEN
            IF target_run.review_source_document_updated_at = p_expected_document_updated_at
               AND target_run.review_candidate_versions = p_expected_candidate_versions
               AND target_run.review_patient_decision_updated_at =
                   p_expected_patient_decision_updated_at THEN
              RETURN true;
            END IF;
            RAISE EXCEPTION 'OCR review finalization conflict' USING ERRCODE = 'HC409';
          END IF;

          IF target_document.ocr_status <> 'review_required'
             OR target_run.review_status = 'finalized'
             OR target_document.updated_at <> p_expected_document_updated_at THEN
            RAISE EXCEPTION 'OCR review state conflict' USING ERRCODE = 'HC409';
          END IF;
          IF target_decision.updated_at <> p_expected_patient_decision_updated_at
             OR target_decision.decision NOT IN ('match','not_present') THEN
            RAISE EXCEPTION 'Patient decision blocks finalization' USING ERRCODE = 'HC409';
          END IF;

          SELECT count(*) INTO candidate_count
          FROM {S}.document_ocr_candidates c
          WHERE c.run_id = target_run.id;
          SELECT count(*), count(DISTINCT value ->> 'id')
          INTO expected_count, expected_distinct
          FROM pg_catalog.jsonb_array_elements(p_expected_candidate_versions);
          IF expected_count <> candidate_count OR expected_distinct <> candidate_count THEN
            RAISE EXCEPTION 'Candidate manifest changed' USING ERRCODE = 'HC409';
          END IF;
          IF EXISTS (
            SELECT 1
            FROM {S}.document_ocr_candidates c
            WHERE c.run_id = target_run.id
              AND NOT EXISTS (
                SELECT 1
                FROM pg_catalog.jsonb_array_elements(p_expected_candidate_versions) item
                WHERE (item ->> 'id')::uuid = c.id
                  AND (item ->> 'updated_at')::timestamptz = c.updated_at
              )
          ) THEN
            RAISE EXCEPTION 'Candidate manifest changed' USING ERRCODE = 'HC409';
          END IF;
          SELECT count(*) INTO unresolved_count
          FROM {S}.document_ocr_candidates c
          WHERE c.run_id = target_run.id
            AND c.status IN ('needs_review','deferred');
          IF unresolved_count > 0 THEN
            RAISE EXCEPTION 'OCR review is incomplete' USING ERRCODE = 'HC409';
          END IF;

          UPDATE {S}.document_ocr_runs
          SET review_status = 'finalized',
              review_finalized_by_user_id = actor_id,
              review_finalized_at = now_value,
              review_source_document_updated_at = p_expected_document_updated_at,
              review_candidate_versions = p_expected_candidate_versions,
              review_patient_decision_id = target_decision.id,
              review_patient_decision_updated_at = target_decision.updated_at,
              updated_at = now_value
          WHERE id = target_run.id;

          UPDATE {S}.profile_documents
          SET ocr_status = 'reviewed', updated_at = now_value
          WHERE id = target_document.id AND profile_id = target_document.profile_id;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_document.profile_id, actor_id,
            'document_ocr_review', target_document.id,
            'document.ocr_review_finalized', '{{}}'::jsonb, p_request_id
          );
          RETURN true;
        END;
        $$
        """
    )

    for signature in (
        REVIEW_CANDIDATE_SIG,
        PATIENT_DECISION_SIG,
        FINALIZE_REVIEW_SIG,
    ):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {DEFINER}")
        op.execute(f"ALTER FUNCTION {signature} SET row_security = off")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "DROP CONSTRAINT ck_profile_documents_ocr_metadata, "
        "DROP CONSTRAINT ck_profile_documents_ocr_status"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "ADD CONSTRAINT ck_profile_documents_ocr_status CHECK ("
        "ocr_status IN ('not_started','queued','processing','review_required','reviewed','error')), "
        "ADD CONSTRAINT ck_profile_documents_ocr_metadata CHECK ("
        "ocr_status NOT IN ('review_required','reviewed') OR ("
        "current_ocr_run_id IS NOT NULL AND ocr_completed_at IS NOT NULL))"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.document_ocr_patient_decisions (
          id uuid PRIMARY KEY,
          run_id uuid NOT NULL REFERENCES {S}.document_ocr_runs(id) ON DELETE CASCADE,
          document_id uuid NOT NULL,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          decision varchar(32) NOT NULL,
          note varchar(500) NULL,
          decided_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          decided_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_document_ocr_patient_decisions_document_profile
            FOREIGN KEY (document_id, profile_id)
            REFERENCES {S}.profile_documents(id, profile_id) ON DELETE CASCADE,
          CONSTRAINT uq_document_ocr_patient_decisions_run UNIQUE (run_id),
          CONSTRAINT ck_document_ocr_patient_decision CHECK (
            decision IN ('unknown','match','mismatch','not_present')
          ),
          CONSTRAINT ck_document_ocr_patient_note CHECK (
            note IS NULL OR (length(note) BETWEEN 1 AND 500 AND note !~ '[[:cntrl:]]')
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_document_ocr_patient_decisions_document "
        f"ON {S}.document_ocr_patient_decisions (document_id, run_id)"
    )

    op.execute(
        f"ALTER TABLE {S}.document_ocr_runs "
        "ADD COLUMN review_status varchar(32) NOT NULL DEFAULT 'not_started', "
        "ADD COLUMN review_finalized_by_user_id uuid NULL REFERENCES "
        f"{S}.users(id), "
        "ADD COLUMN review_finalized_at timestamptz NULL, "
        "ADD COLUMN review_source_document_updated_at timestamptz NULL, "
        "ADD COLUMN review_candidate_versions jsonb NULL, "
        "ADD COLUMN review_patient_decision_id uuid NULL REFERENCES "
        f"{S}.document_ocr_patient_decisions(id), "
        "ADD COLUMN review_patient_decision_updated_at timestamptz NULL, "
        "ADD CONSTRAINT ck_document_ocr_runs_review_status CHECK ("
        "review_status IN ('not_started','in_progress','finalized')), "
        "ADD CONSTRAINT ck_document_ocr_runs_review_completion CHECK ("
        "(review_status = 'finalized' AND review_finalized_by_user_id IS NOT NULL "
        "AND review_finalized_at IS NOT NULL "
        "AND review_source_document_updated_at IS NOT NULL "
        "AND review_candidate_versions IS NOT NULL "
        "AND review_patient_decision_id IS NOT NULL "
        "AND review_patient_decision_updated_at IS NOT NULL) OR "
        "(review_status <> 'finalized' AND review_finalized_by_user_id IS NULL "
        "AND review_finalized_at IS NULL "
        "AND review_source_document_updated_at IS NULL "
        "AND review_candidate_versions IS NULL "
        "AND review_patient_decision_id IS NULL "
        "AND review_patient_decision_updated_at IS NULL))"
    )

    op.execute(
        f"ALTER TABLE {S}.document_ocr_candidates "
        "DROP CONSTRAINT ck_document_ocr_candidates_review"
    )
    op.execute(
        f"""
        ALTER TABLE {S}.document_ocr_candidates
        ADD CONSTRAINT ck_document_ocr_candidates_review CHECK (
          (status = 'needs_review' AND reviewed_text IS NULL
           AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL
           AND review_note IS NULL)
          OR
          (status = 'accepted' AND reviewed_text = original_text
           AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)
          OR
          (status = 'edited' AND reviewed_text IS NOT NULL
           AND reviewed_text <> original_text
           AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)
          OR
          (status IN ('rejected','deferred') AND reviewed_text IS NULL
           AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)
        )
        """
    )

    op.execute(
        f"ALTER TABLE {S}.document_ocr_patient_decisions ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        f"ALTER TABLE {S}.document_ocr_patient_decisions FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        f"CREATE POLICY document_ocr_patient_decisions_select "
        f"ON {S}.document_ocr_patient_decisions FOR SELECT "
        f"USING ({S}.app_can_review_document_ocr(profile_id))"
    )
    op.execute(f"GRANT SELECT ON {S}.document_ocr_patient_decisions TO {APP}")
    op.execute(
        f"REVOKE INSERT, UPDATE, DELETE ON {S}.document_ocr_patient_decisions FROM {APP}"
    )

    _replace_audit_constraint(include_review_actions=True)

    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON {S}.document_ocr_patient_decisions TO {DEFINER}"
    )
    op.execute(f"GRANT SELECT, UPDATE ON {S}.document_ocr_candidates TO {DEFINER}")
    op.execute(f"GRANT SELECT, UPDATE ON {S}.document_ocr_runs TO {DEFINER}")
    op.execute(f"GRANT SELECT, UPDATE ON {S}.profile_documents TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.health_profiles TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.user_consents TO {DEFINER}")
    op.execute(f"GRANT INSERT ON {S}.profile_audit_events TO {DEFINER}")

    _create_review_functions()


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM {S}.document_ocr_patient_decisions)
             OR EXISTS (
               SELECT 1 FROM {S}.document_ocr_runs
               WHERE review_status <> 'not_started'
             )
             OR EXISTS (
               SELECT 1 FROM {S}.document_ocr_candidates
               WHERE status <> 'needs_review'
             ) THEN
            RAISE EXCEPTION
              'Cannot downgrade 0055 while OCR human-review data exists';
          END IF;
        END $$;
        """
    )

    for signature in (
        FINALIZE_REVIEW_SIG,
        PATIENT_DECISION_SIG,
        REVIEW_CANDIDATE_SIG,
    ):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")

    _replace_audit_constraint(include_review_actions=False)

    op.execute(
        f"DROP POLICY IF EXISTS document_ocr_patient_decisions_select "
        f"ON {S}.document_ocr_patient_decisions"
    )
    op.execute(f"REVOKE SELECT ON {S}.document_ocr_patient_decisions FROM {APP}")

    op.execute(
        f"ALTER TABLE {S}.document_ocr_runs "
        "DROP CONSTRAINT ck_document_ocr_runs_review_completion, "
        "DROP CONSTRAINT ck_document_ocr_runs_review_status, "
        "DROP COLUMN review_patient_decision_updated_at, "
        "DROP COLUMN review_patient_decision_id, "
        "DROP COLUMN review_candidate_versions, "
        "DROP COLUMN review_source_document_updated_at, "
        "DROP COLUMN review_finalized_at, "
        "DROP COLUMN review_finalized_by_user_id, "
        "DROP COLUMN review_status"
    )
    op.execute(f"DROP TABLE {S}.document_ocr_patient_decisions")

    op.execute(
        f"ALTER TABLE {S}.document_ocr_candidates "
        "DROP CONSTRAINT ck_document_ocr_candidates_review"
    )
    op.execute(
        f"""
        ALTER TABLE {S}.document_ocr_candidates
        ADD CONSTRAINT ck_document_ocr_candidates_review CHECK (
          (status = 'needs_review' AND reviewed_text IS NULL
           AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL)
          OR status <> 'needs_review'
        )
        """
    )

    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "DROP CONSTRAINT ck_profile_documents_ocr_metadata, "
        "DROP CONSTRAINT ck_profile_documents_ocr_status"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "ADD CONSTRAINT ck_profile_documents_ocr_status CHECK ("
        "ocr_status IN ('not_started','queued','processing','review_required','error')), "
        "ADD CONSTRAINT ck_profile_documents_ocr_metadata CHECK ("
        "ocr_status <> 'review_required' OR ("
        "current_ocr_run_id IS NOT NULL AND ocr_completed_at IS NOT NULL))"
    )
