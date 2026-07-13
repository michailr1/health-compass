"""Add HC-017 E3 correction, void and owner-only erasure lifecycle.

Revision ID: 0059
Revises: 0058

Confirmed source/value fields remain immutable. Correction inserts a replacement
snapshot, voiding only changes lifecycle metadata, and permanent erasure removes
the complete connected correction chain and its value-bearing provenance.
"""

from __future__ import annotations

from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"

VOID_SIG = f"{S}.app_void_lab_observation(uuid,integer,text,uuid,text)"
CORRECT_SIG = (
    f"{S}.app_correct_lab_observation("
    "uuid,uuid,integer,text,text,jsonb,uuid,text)"
)
ERASE_SIG = f"{S}.app_erase_lab_observation(uuid,integer,boolean,uuid,text)"
ERASE_DOCUMENT_LABS_SIG = (
    f"{S}.app_request_document_lab_erasure("
    "uuid,timestamp with time zone,boolean,uuid,text)"
)

AUDIT_ACTIONS_0058 = """
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
            'document.ocr_review_finalized',
            'lab.draft_created',
            'lab.draft_updated',
            'lab.draft_sources_changed',
            'lab.draft_status_changed',
            'lab.observation_confirmed'
"""


def _replace_audit_constraint(*, include_e3: bool) -> None:
    actions = AUDIT_ACTIONS_0058
    if include_e3:
        actions = (
            f"{actions.rstrip()},\n"
            "            'lab.observation_corrected',\n"
            "            'lab.observation_voided',\n"
            "            'lab.observation_erased',\n"
            "            'document.lab_erasure_requested'\n"
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
        CREATE FUNCTION {S}.app_void_lab_observation(
          p_observation_id uuid,
          p_expected_lifecycle_version integer,
          p_reason text,
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
          target_observation {S}.lab_observations%ROWTYPE;
          target_document {S}.profile_documents%ROWTYPE;
          now_value timestamptz := pg_catalog.clock_timestamp();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Lab observation not found' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL OR p_expected_lifecycle_version IS NULL THEN
            RAISE EXCEPTION 'Lab lifecycle precondition is required'
              USING ERRCODE = 'HC428';
          END IF;
          IF coalesce(length(btrim(p_reason)), 0) NOT BETWEEN 1 AND 1000
             OR p_reason ~ '[[:cntrl:]]'
             OR (p_request_id IS NOT NULL AND length(p_request_id) > 128) THEN
            RAISE EXCEPTION 'Invalid Lab lifecycle request' USING ERRCODE = 'HC422';
          END IF;

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
          IF target_observation.status <> 'active'
             OR target_document.id IS NULL
             OR target_document.deletion_requested_at IS NOT NULL
             OR target_document.erased_at IS NOT NULL THEN
            RAISE EXCEPTION 'Lab observation lifecycle changed'
              USING ERRCODE = 'HC409';
          END IF;
          IF target_observation.lifecycle_version <> p_expected_lifecycle_version THEN
            RAISE EXCEPTION 'Lab observation was updated elsewhere'
              USING ERRCODE = 'HC409';
          END IF;

          UPDATE {S}.lab_observations
          SET status = 'voided',
              voided_at = now_value,
              voided_by_user_id = actor_id,
              void_reason = btrim(p_reason),
              lifecycle_version = lifecycle_version + 1,
              lifecycle_updated_at = now_value
          WHERE id = p_observation_id;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_observation.profile_id, actor_id,
            'lab_observation', p_observation_id,
            'lab.observation_voided', '{{}}'::jsonb, p_request_id
          );
          RETURN true;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_correct_lab_observation(
          p_new_observation_id uuid,
          p_observation_id uuid,
          p_expected_lifecycle_version integer,
          p_idempotency_key text,
          p_reason text,
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
            target_observation.ack_source,
            target_observation.ack_unit_range,
            target_observation.ack_observed_at,
            target_observation.ack_profile,
            target_observation.ack_structured_record,
            target_observation.ack_not_present_assignment,
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
            'lab.observation_corrected', '{{}}'::jsonb, p_request_id
          );
          RETURN p_new_observation_id;
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
        CREATE FUNCTION {S}.app_erase_lab_observation(
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

          WITH RECURSIVE chain(id) AS (
            SELECT root_id
            UNION ALL
            SELECT o.id
            FROM {S}.lab_observations o
            JOIN chain c ON o.supersedes_observation_id = c.id
          )
          SELECT array_agg(id ORDER BY id) INTO chain_ids FROM chain;

          PERFORM o.id
          FROM {S}.lab_observations o
          WHERE o.id = ANY(chain_ids)
          ORDER BY o.id
          FOR UPDATE;

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
            'lab.observation_erased', '{{}}'::jsonb, p_request_id
          );
          RETURN deleted_count;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_request_document_lab_erasure(
          p_document_id uuid,
          p_expected_document_updated_at timestamptz,
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
          target_document {S}.profile_documents%ROWTYPE;
          observation_ids uuid[];
          draft_ids uuid[];
          deleted_count integer := 0;
          now_value timestamptz := pg_catalog.clock_timestamp();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Document not found' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL OR p_expected_document_updated_at IS NULL
             OR p_confirm_permanent_deletion IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'Permanent erasure confirmation is required'
              USING ERRCODE = 'HC428';
          END IF;
          IF p_request_id IS NOT NULL AND length(p_request_id) > 128 THEN
            RAISE EXCEPTION 'Invalid request id' USING ERRCODE = 'HC422';
          END IF;

          SELECT d.* INTO target_document
          FROM {S}.profile_documents d
          WHERE d.id = p_document_id
          FOR UPDATE;
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp
          WHERE hp.id = target_document.profile_id;
          IF target_document.id IS NULL OR owner_id IS NULL OR owner_id <> actor_id THEN
            RAISE EXCEPTION 'Document not found' USING ERRCODE = 'HC404';
          END IF;
          IF target_document.updated_at <> p_expected_document_updated_at THEN
            RAISE EXCEPTION 'Document was updated elsewhere' USING ERRCODE = 'HC409';
          END IF;
          IF target_document.erased_at IS NOT NULL THEN
            RAISE EXCEPTION 'Document not found' USING ERRCODE = 'HC404';
          END IF;

          UPDATE {S}.profile_documents
          SET status = 'deletion_pending',
              deletion_requested_at = coalesce(deletion_requested_at, now_value),
              updated_at = now_value
          WHERE id = target_document.id;

          SELECT array_agg(o.id), array_agg(o.source_draft_id)
          INTO observation_ids, draft_ids
          FROM {S}.lab_observations o
          WHERE o.document_id = target_document.id;

          IF observation_ids IS NOT NULL THEN
            IF draft_ids IS NOT NULL THEN
              UPDATE {S}.lab_observation_drafts
              SET status = 'rejected',
                  confirmed_at = NULL,
                  confirmed_by_user_id = NULL,
                  confirmed_observation_id = NULL,
                  updated_by_user_id = actor_id,
                  updated_at = now_value
              WHERE id = ANY(draft_ids);
            END IF;
            DELETE FROM {S}.lab_observation_sources
            WHERE observation_id = ANY(observation_ids);
            DELETE FROM {S}.profile_audit_events
            WHERE profile_id = target_document.profile_id
              AND entity_type = 'lab_observation'
              AND entity_id = ANY(observation_ids);
            DELETE FROM {S}.lab_observations
            WHERE id = ANY(observation_ids);
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
          END IF;

          SELECT array_agg(d.id) INTO draft_ids
          FROM {S}.lab_observation_drafts d
          WHERE d.document_id = target_document.id;
          IF draft_ids IS NOT NULL THEN
            DELETE FROM {S}.profile_audit_events
            WHERE profile_id = target_document.profile_id
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
            p_audit_event_id, target_document.profile_id, actor_id,
            'document', target_document.id,
            'document.lab_erasure_requested', '{{}}'::jsonb, p_request_id
          );
          RETURN deleted_count;
        END;
        $$
        """
    )

    for signature in (VOID_SIG, CORRECT_SIG, ERASE_SIG, ERASE_DOCUMENT_LABS_SIG):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {DEFINER}")
        op.execute(f"ALTER FUNCTION {signature} SET row_security = off")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {S}.lab_observations "
        "DROP CONSTRAINT ck_lab_observations_status"
    )
    op.execute(
        f"ALTER TABLE {S}.lab_observations "
        "ALTER COLUMN source_draft_id DROP NOT NULL"
    )
    op.execute(
        f"""
        ALTER TABLE {S}.lab_observations
          ADD COLUMN lifecycle_version integer NOT NULL DEFAULT 1,
          ADD COLUMN lifecycle_updated_at timestamptz NOT NULL DEFAULT now(),
          ADD COLUMN supersedes_observation_id uuid NULL,
          ADD COLUMN superseded_by_observation_id uuid NULL,
          ADD COLUMN superseded_at timestamptz NULL,
          ADD COLUMN superseded_by_user_id uuid NULL REFERENCES {S}.users(id),
          ADD COLUMN correction_reason varchar(1000) NULL,
          ADD COLUMN voided_at timestamptz NULL,
          ADD COLUMN voided_by_user_id uuid NULL REFERENCES {S}.users(id),
          ADD COLUMN void_reason varchar(1000) NULL,
          ADD CONSTRAINT fk_lab_observations_supersedes
            FOREIGN KEY (supersedes_observation_id)
            REFERENCES {S}.lab_observations(id)
            DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT fk_lab_observations_superseded_by
            FOREIGN KEY (superseded_by_observation_id)
            REFERENCES {S}.lab_observations(id)
            DEFERRABLE INITIALLY DEFERRED,
          ADD CONSTRAINT uq_lab_observations_supersedes
            UNIQUE (supersedes_observation_id),
          ADD CONSTRAINT uq_lab_observations_superseded_by
            UNIQUE (superseded_by_observation_id),
          ADD CONSTRAINT ck_lab_observations_status CHECK (
            status IN ('active','superseded','voided')
          ),
          ADD CONSTRAINT ck_lab_observations_lifecycle_version CHECK (
            lifecycle_version >= 1
          ),
          ADD CONSTRAINT ck_lab_observations_no_self_link CHECK (
            id IS DISTINCT FROM supersedes_observation_id
            AND id IS DISTINCT FROM superseded_by_observation_id
          ),
          ADD CONSTRAINT ck_lab_observations_origin CHECK (
            (source_draft_id IS NOT NULL
             AND supersedes_observation_id IS NULL
             AND correction_reason IS NULL)
            OR
            (source_draft_id IS NULL
             AND supersedes_observation_id IS NOT NULL
             AND correction_reason IS NOT NULL
             AND btrim(correction_reason) <> '')
          ),
          ADD CONSTRAINT ck_lab_observations_lifecycle_state CHECK (
            (status = 'active'
             AND superseded_by_observation_id IS NULL
             AND superseded_at IS NULL
             AND superseded_by_user_id IS NULL
             AND voided_at IS NULL
             AND voided_by_user_id IS NULL
             AND void_reason IS NULL)
            OR
            (status = 'superseded'
             AND superseded_by_observation_id IS NOT NULL
             AND superseded_at IS NOT NULL
             AND superseded_by_user_id IS NOT NULL
             AND voided_at IS NULL
             AND voided_by_user_id IS NULL
             AND void_reason IS NULL)
            OR
            (status = 'voided'
             AND superseded_by_observation_id IS NULL
             AND superseded_at IS NULL
             AND superseded_by_user_id IS NULL
             AND voided_at IS NOT NULL
             AND voided_by_user_id IS NOT NULL
             AND void_reason IS NOT NULL
             AND btrim(void_reason) <> '')
          )
        """
    )
    op.execute(
        f"CREATE INDEX ix_lab_observations_profile_lifecycle "
        f"ON {S}.lab_observations "
        "(profile_id, status, lifecycle_updated_at DESC)"
    )

    op.execute(
        f"ALTER TABLE {S}.lab_observation_sources "
        "DROP CONSTRAINT lab_observation_sources_observation_id_fkey"
    )
    op.execute(
        f"ALTER TABLE {S}.lab_observation_sources "
        f"ADD CONSTRAINT lab_observation_sources_observation_id_fkey "
        f"FOREIGN KEY (observation_id) REFERENCES {S}.lab_observations(id) "
        "ON DELETE CASCADE"
    )

    op.execute(
        f"DROP POLICY IF EXISTS lab_observations_select "
        f"ON {S}.lab_observations"
    )
    op.execute(
        f"DROP POLICY IF EXISTS lab_observation_sources_select "
        f"ON {S}.lab_observation_sources"
    )
    op.execute(
        f"""
        CREATE POLICY lab_observations_select_active
        ON {S}.lab_observations FOR SELECT
        USING (
          status = 'active'
          AND {S}.app_can_view_profile(profile_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY lab_observations_select_lifecycle_edit
        ON {S}.lab_observations FOR SELECT
        USING ({S}.app_can_edit_profile(profile_id))
        """
    )
    op.execute(
        f"""
        CREATE POLICY lab_observation_sources_select_edit
        ON {S}.lab_observation_sources FOR SELECT
        USING ({S}.app_can_edit_profile(profile_id))
        """
    )

    for table in (
        "lab_observations",
        "lab_observation_sources",
        "lab_observation_drafts",
        "lab_observation_draft_sources",
    ):
        op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {S}.{table} FROM {APP}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
        f"{S}.lab_observations, {S}.lab_observation_sources, "
        f"{S}.lab_observation_drafts, {S}.lab_observation_draft_sources "
        f"TO {DEFINER}"
    )
    op.execute(f"GRANT SELECT, UPDATE ON {S}.profile_documents TO {DEFINER}")
    op.execute(
        f"GRANT SELECT, INSERT, DELETE ON {S}.profile_audit_events TO {DEFINER}"
    )

    _replace_audit_constraint(include_e3=True)
    _create_functions()


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM {S}.lab_observations
            WHERE status <> 'active'
               OR source_draft_id IS NULL
               OR supersedes_observation_id IS NOT NULL
               OR superseded_by_observation_id IS NOT NULL
               OR voided_at IS NOT NULL
          ) THEN
            RAISE EXCEPTION 'Cannot downgrade 0059 while E3 lifecycle data exists';
          END IF;
          IF EXISTS (
            SELECT 1 FROM {S}.profile_documents
            WHERE status = 'deletion_pending' AND deletion_requested_at IS NOT NULL
          ) THEN
            RAISE EXCEPTION 'Cannot downgrade 0059 while document erasure is pending';
          END IF;
        END $$;
        """
    )

    for signature in (ERASE_DOCUMENT_LABS_SIG, ERASE_SIG, CORRECT_SIG, VOID_SIG):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {APP}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")

    _replace_audit_constraint(include_e3=False)

    op.execute(
        f"DROP POLICY IF EXISTS lab_observation_sources_select_edit "
        f"ON {S}.lab_observation_sources"
    )
    op.execute(
        f"DROP POLICY IF EXISTS lab_observations_select_lifecycle_edit "
        f"ON {S}.lab_observations"
    )
    op.execute(
        f"DROP POLICY IF EXISTS lab_observations_select_active "
        f"ON {S}.lab_observations"
    )
    op.execute(
        f"CREATE POLICY lab_observations_select ON {S}.lab_observations "
        f"FOR SELECT USING ({S}.app_can_view_profile(profile_id))"
    )
    op.execute(
        f"CREATE POLICY lab_observation_sources_select "
        f"ON {S}.lab_observation_sources "
        f"FOR SELECT USING ({S}.app_can_view_profile(profile_id))"
    )

    op.execute(
        f"ALTER TABLE {S}.lab_observation_sources "
        "DROP CONSTRAINT lab_observation_sources_observation_id_fkey"
    )
    op.execute(
        f"ALTER TABLE {S}.lab_observation_sources "
        f"ADD CONSTRAINT lab_observation_sources_observation_id_fkey "
        f"FOREIGN KEY (observation_id) REFERENCES {S}.lab_observations(id) "
        "ON DELETE RESTRICT"
    )

    op.execute(f"DROP INDEX {S}.ix_lab_observations_profile_lifecycle")
    op.execute(
        f"""
        ALTER TABLE {S}.lab_observations
          DROP CONSTRAINT ck_lab_observations_status,
          DROP CONSTRAINT ck_lab_observations_lifecycle_state,
          DROP CONSTRAINT ck_lab_observations_origin,
          DROP CONSTRAINT ck_lab_observations_no_self_link,
          DROP CONSTRAINT ck_lab_observations_lifecycle_version,
          DROP CONSTRAINT uq_lab_observations_superseded_by,
          DROP CONSTRAINT uq_lab_observations_supersedes,
          DROP CONSTRAINT fk_lab_observations_superseded_by,
          DROP CONSTRAINT fk_lab_observations_supersedes,
          DROP COLUMN void_reason,
          DROP COLUMN voided_by_user_id,
          DROP COLUMN voided_at,
          DROP COLUMN correction_reason,
          DROP COLUMN superseded_by_user_id,
          DROP COLUMN superseded_at,
          DROP COLUMN superseded_by_observation_id,
          DROP COLUMN supersedes_observation_id,
          DROP COLUMN lifecycle_updated_at,
          DROP COLUMN lifecycle_version
        """
    )
    op.execute(
        f"ALTER TABLE {S}.lab_observations "
        "ALTER COLUMN source_draft_id SET NOT NULL"
    )
    op.execute(
        f"ALTER TABLE {S}.lab_observations "
        "ADD CONSTRAINT ck_lab_observations_status CHECK (status = 'active')"
    )
