"""Add HC-017 E2 immutable confirmed laboratory observations.

Revision ID: 0058
Revises: 0057

E2 consumes one current E1 ready draft through a separate explicit,
atomic and idempotent confirmation transaction. Confirmed observations and
their source snapshots are immutable to application and worker roles.
"""

from __future__ import annotations

from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"

CONFIRM_SIG = (
    f"{S}.app_confirm_lab_observation("
    "uuid,uuid,text,timestamp with time zone,timestamp with time zone,"
    "timestamp with time zone,timestamp with time zone,"
    "boolean,boolean,boolean,boolean,boolean,boolean,uuid,text)"
)

AUDIT_ACTIONS_0057 = """
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
            'lab.draft_status_changed'
"""


def _replace_audit_constraint(*, include_confirmation: bool) -> None:
    actions = AUDIT_ACTIONS_0057
    if include_confirmation:
        actions = f"{actions.rstrip()},\n            'lab.observation_confirmed'\n"
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


def _create_confirmation_function() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_confirm_lab_observation(
          p_observation_id uuid,
          p_draft_id uuid,
          p_idempotency_key text,
          p_expected_draft_updated_at timestamptz,
          p_expected_document_updated_at timestamptz,
          p_expected_review_finalized_at timestamptz,
          p_expected_patient_decision_updated_at timestamptz,
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
          target_draft {S}.lab_observation_drafts%ROWTYPE;
          target_document {S}.profile_documents%ROWTYPE;
          target_run {S}.document_ocr_runs%ROWTYPE;
          target_decision {S}.document_ocr_patient_decisions%ROWTYPE;
          existing_observation {S}.lab_observations%ROWTYPE;
          owner_id uuid;
          source_count integer;
          current_source_count integer;
          inserted_count integer;
          now_value timestamptz := pg_catalog.clock_timestamp();
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Lab confirmation denied' USING ERRCODE = 'HC404';
          END IF;
          actor_id := {S}.app_current_user_id();
          IF actor_id IS NULL OR p_observation_id IS NULL OR p_draft_id IS NULL
             OR p_expected_draft_updated_at IS NULL
             OR p_expected_document_updated_at IS NULL
             OR p_expected_review_finalized_at IS NULL
             OR p_expected_patient_decision_updated_at IS NULL THEN
            RAISE EXCEPTION 'Lab confirmation precondition is required'
              USING ERRCODE = 'HC428';
          END IF;
          IF p_idempotency_key IS NULL
             OR length(p_idempotency_key) NOT BETWEEN 16 AND 128
             OR p_idempotency_key !~ '^[A-Za-z0-9._:-]+$' THEN
            RAISE EXCEPTION 'Invalid confirmation idempotency key'
              USING ERRCODE = 'HC422';
          END IF;
          IF p_request_id IS NOT NULL AND length(p_request_id) > 128 THEN
            RAISE EXCEPTION 'Invalid request id' USING ERRCODE = 'HC422';
          END IF;
          IF NOT coalesce(p_ack_source, false)
             OR NOT coalesce(p_ack_unit_range, false)
             OR NOT coalesce(p_ack_observed_at, false)
             OR NOT coalesce(p_ack_profile, false)
             OR NOT coalesce(p_ack_structured_record, false) THEN
            RAISE EXCEPTION 'All confirmation acknowledgements are required'
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

          SELECT lo.* INTO existing_observation
          FROM {S}.lab_observations lo
          WHERE lo.profile_id = target_draft.profile_id
            AND lo.confirmation_idempotency_key = p_idempotency_key;
          IF existing_observation.id IS NOT NULL THEN
            IF existing_observation.source_draft_id <> target_draft.id
               OR existing_observation.source_draft_updated_at
                    <> p_expected_draft_updated_at
               OR existing_observation.source_document_updated_at
                    <> p_expected_document_updated_at
               OR existing_observation.source_review_finalized_at
                    <> p_expected_review_finalized_at
               OR existing_observation.source_patient_decision_updated_at
                    <> p_expected_patient_decision_updated_at
               OR existing_observation.ack_source <> p_ack_source
               OR existing_observation.ack_unit_range <> p_ack_unit_range
               OR existing_observation.ack_observed_at <> p_ack_observed_at
               OR existing_observation.ack_profile <> p_ack_profile
               OR existing_observation.ack_structured_record
                    <> p_ack_structured_record
               OR existing_observation.ack_not_present_assignment
                    <> coalesce(p_ack_not_present_assignment, false) THEN
              RAISE EXCEPTION 'Confirmation idempotency conflict'
                USING ERRCODE = 'HC409';
            END IF;
            RETURN existing_observation.id;
          END IF;

          SELECT lo.* INTO existing_observation
          FROM {S}.lab_observations lo
          WHERE lo.source_draft_id = target_draft.id;
          IF existing_observation.id IS NOT NULL THEN
            IF existing_observation.source_draft_updated_at
                  <> p_expected_draft_updated_at
               OR existing_observation.source_document_updated_at
                  <> p_expected_document_updated_at
               OR existing_observation.source_review_finalized_at
                  <> p_expected_review_finalized_at
               OR existing_observation.source_patient_decision_updated_at
                  <> p_expected_patient_decision_updated_at
               OR existing_observation.ack_source <> p_ack_source
               OR existing_observation.ack_unit_range <> p_ack_unit_range
               OR existing_observation.ack_observed_at <> p_ack_observed_at
               OR existing_observation.ack_profile <> p_ack_profile
               OR existing_observation.ack_structured_record
                    <> p_ack_structured_record
               OR existing_observation.ack_not_present_assignment
                    <> coalesce(p_ack_not_present_assignment, false) THEN
              RAISE EXCEPTION 'Confirmation replay conflict'
                USING ERRCODE = 'HC409';
            END IF;
            RETURN existing_observation.id;
          END IF;

          IF target_draft.status <> 'ready'
             OR target_draft.updated_at <> p_expected_draft_updated_at THEN
            RAISE EXCEPTION 'Lab draft is not current and ready'
              USING ERRCODE = 'HC409';
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
            AND pd.document_id = target_document.id
            AND pd.profile_id = target_document.profile_id
          FOR UPDATE;
          SELECT hp.owner_user_id INTO owner_id
          FROM {S}.health_profiles hp
          WHERE hp.id = target_draft.profile_id;

          IF target_document.id IS NULL OR target_run.id IS NULL
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
            RAISE EXCEPTION 'Lab confirmation context changed'
              USING ERRCODE = 'HC409';
          END IF;
          IF target_document.updated_at <> p_expected_document_updated_at
             OR target_run.review_finalized_at
                  <> p_expected_review_finalized_at
             OR target_decision.updated_at
                  <> p_expected_patient_decision_updated_at THEN
            RAISE EXCEPTION 'Lab confirmation source was updated elsewhere'
              USING ERRCODE = 'HC409';
          END IF;
          IF target_decision.decision = 'not_present'
             AND NOT coalesce(p_ack_not_present_assignment, false) THEN
            RAISE EXCEPTION 'Explicit profile assignment acknowledgement is required'
              USING ERRCODE = 'HC422';
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

          PERFORM c.id
          FROM {S}.lab_observation_draft_sources ds
          JOIN {S}.document_ocr_candidates c ON c.id = ds.candidate_id
          WHERE ds.draft_id = target_draft.id
          ORDER BY c.id
          FOR UPDATE OF c;

          SELECT count(*) INTO source_count
          FROM {S}.lab_observation_draft_sources ds
          WHERE ds.draft_id = target_draft.id;
          SELECT count(*) INTO current_source_count
          FROM {S}.lab_observation_draft_sources ds
          JOIN {S}.document_ocr_candidates c ON c.id = ds.candidate_id
          WHERE ds.draft_id = target_draft.id
            AND ds.profile_id = target_draft.profile_id
            AND ds.document_id = target_draft.document_id
            AND ds.ocr_run_id = target_draft.ocr_run_id
            AND c.profile_id = ds.profile_id
            AND c.document_id = ds.document_id
            AND c.run_id = ds.ocr_run_id
            AND c.page_artifact_id = ds.page_artifact_id
            AND c.page_number = ds.page_number
            AND c.status IN ('accepted','edited')
            AND c.reviewed_text IS NOT NULL
            AND c.updated_at = ds.candidate_updated_at;
          IF source_count < 2 OR current_source_count <> source_count
             OR NOT EXISTS (
               SELECT 1 FROM {S}.lab_observation_draft_sources ds
               WHERE ds.draft_id = target_draft.id AND ds.source_role = 'analyte'
             )
             OR NOT EXISTS (
               SELECT 1 FROM {S}.lab_observation_draft_sources ds
               WHERE ds.draft_id = target_draft.id AND ds.source_role = 'value'
             ) THEN
            RAISE EXCEPTION 'Lab source manifest changed or is incomplete'
              USING ERRCODE = 'HC409';
          END IF;

          INSERT INTO {S}.lab_observations (
            id, profile_id, document_id, ocr_run_id, patient_decision_id,
            source_draft_id, status, patient_decision,
            source_analyte_text, source_value_text, value_kind, comparator,
            numeric_value, text_value, qualitative_value_text,
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
            confirmed_by_user_id, confirmed_at, created_at
          ) VALUES (
            p_observation_id, target_draft.profile_id, target_draft.document_id,
            target_draft.ocr_run_id, target_draft.patient_decision_id,
            target_draft.id, 'active', target_decision.decision,
            target_draft.source_analyte_text, target_draft.source_value_text,
            target_draft.value_kind, target_draft.comparator,
            target_draft.numeric_value, target_draft.text_value,
            target_draft.qualitative_value_text,
            target_draft.source_unit_text, target_draft.unit_not_present,
            target_draft.source_reference_range_text,
            target_draft.reference_range_not_present,
            target_draft.source_observed_at_text,
            target_draft.observed_time_unknown,
            target_draft.observed_date, target_draft.observed_at,
            target_draft.observed_precision,
            target_draft.source_specimen_text, target_draft.source_flag_text,
            target_draft.source_comment,
            target_draft.updated_at, target_document.updated_at,
            target_run.review_finalized_at, target_decision.updated_at,
            p_idempotency_key,
            p_ack_source, p_ack_unit_range, p_ack_observed_at, p_ack_profile,
            p_ack_structured_record,
            coalesce(p_ack_not_present_assignment, false),
            actor_id, now_value, now_value
          )
          ON CONFLICT (profile_id, confirmation_idempotency_key) DO NOTHING;
          GET DIAGNOSTICS inserted_count = ROW_COUNT;
          IF inserted_count = 0 THEN
            SELECT lo.* INTO existing_observation
            FROM {S}.lab_observations lo
            WHERE lo.profile_id = target_draft.profile_id
              AND lo.confirmation_idempotency_key = p_idempotency_key;
            IF existing_observation.id IS NULL
               OR existing_observation.source_draft_id <> target_draft.id THEN
              RAISE EXCEPTION 'Confirmation idempotency conflict'
                USING ERRCODE = 'HC409';
            END IF;
            RETURN existing_observation.id;
          END IF;

          INSERT INTO {S}.lab_observation_sources (
            observation_id, candidate_id, source_role, candidate_updated_at,
            profile_id, document_id, ocr_run_id, page_artifact_id, page_number,
            reviewed_text_snapshot
          )
          SELECT p_observation_id, ds.candidate_id, ds.source_role,
                 ds.candidate_updated_at, ds.profile_id, ds.document_id,
                 ds.ocr_run_id, ds.page_artifact_id, ds.page_number,
                 c.reviewed_text
          FROM {S}.lab_observation_draft_sources ds
          JOIN {S}.document_ocr_candidates c ON c.id = ds.candidate_id
          WHERE ds.draft_id = target_draft.id;

          UPDATE {S}.lab_observation_drafts
          SET status = 'confirmed',
              confirmed_at = now_value,
              confirmed_by_user_id = actor_id,
              confirmed_observation_id = p_observation_id,
              updated_by_user_id = actor_id,
              updated_at = now_value
          WHERE id = target_draft.id;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_draft.profile_id, actor_id,
            'lab_observation', p_observation_id,
            'lab.observation_confirmed', '{{}}'::jsonb, p_request_id
          );
          RETURN p_observation_id;
        EXCEPTION
          WHEN unique_violation THEN
            SELECT lo.* INTO existing_observation
            FROM {S}.lab_observations lo
            WHERE lo.source_draft_id = p_draft_id;
            IF existing_observation.id IS NOT NULL
               AND existing_observation.source_draft_updated_at
                    = p_expected_draft_updated_at
               AND existing_observation.source_document_updated_at
                    = p_expected_document_updated_at
               AND existing_observation.source_review_finalized_at
                    = p_expected_review_finalized_at
               AND existing_observation.source_patient_decision_updated_at
                    = p_expected_patient_decision_updated_at
               AND existing_observation.ack_source = p_ack_source
               AND existing_observation.ack_unit_range = p_ack_unit_range
               AND existing_observation.ack_observed_at = p_ack_observed_at
               AND existing_observation.ack_profile = p_ack_profile
               AND existing_observation.ack_structured_record
                    = p_ack_structured_record
               AND existing_observation.ack_not_present_assignment
                    = coalesce(p_ack_not_present_assignment, false) THEN
              RETURN existing_observation.id;
            END IF;
            RAISE EXCEPTION 'Confirmation conflict' USING ERRCODE = 'HC409';
        END;
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {CONFIRM_SIG} OWNER TO {DEFINER}")
    op.execute(f"ALTER FUNCTION {CONFIRM_SIG} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {CONFIRM_SIG} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {CONFIRM_SIG} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE {S}.lab_observation_drafts
          DROP CONSTRAINT ck_lab_observation_drafts_status,
          ADD COLUMN confirmed_at timestamptz NULL,
          ADD COLUMN confirmed_by_user_id uuid NULL REFERENCES {S}.users(id),
          ADD COLUMN confirmed_observation_id uuid NULL,
          ADD CONSTRAINT ck_lab_observation_drafts_status CHECK (
            status IN ('draft','ready','rejected','confirmed')
          ),
          ADD CONSTRAINT ck_lab_observation_drafts_confirmation_state CHECK (
            (status = 'confirmed'
             AND confirmed_at IS NOT NULL
             AND confirmed_by_user_id IS NOT NULL
             AND confirmed_observation_id IS NOT NULL)
            OR
            (status <> 'confirmed'
             AND confirmed_at IS NULL
             AND confirmed_by_user_id IS NULL
             AND confirmed_observation_id IS NULL)
          )
        """
    )

    op.execute(
        f"""
        CREATE TABLE {S}.lab_observations (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          document_id uuid NOT NULL,
          ocr_run_id uuid NOT NULL REFERENCES {S}.document_ocr_runs(id),
          patient_decision_id uuid NOT NULL
            REFERENCES {S}.document_ocr_patient_decisions(id),
          source_draft_id uuid NOT NULL UNIQUE
            REFERENCES {S}.lab_observation_drafts(id) ON DELETE RESTRICT,
          status varchar(32) NOT NULL,
          patient_decision varchar(32) NOT NULL,
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
          source_draft_updated_at timestamptz NOT NULL,
          source_document_updated_at timestamptz NOT NULL,
          source_review_finalized_at timestamptz NOT NULL,
          source_patient_decision_updated_at timestamptz NOT NULL,
          confirmation_idempotency_key varchar(128) NOT NULL,
          ack_source boolean NOT NULL,
          ack_unit_range boolean NOT NULL,
          ack_observed_at boolean NOT NULL,
          ack_profile boolean NOT NULL,
          ack_structured_record boolean NOT NULL,
          ack_not_present_assignment boolean NOT NULL,
          confirmed_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          confirmed_at timestamptz NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_lab_observations_document_profile
            FOREIGN KEY (document_id, profile_id)
            REFERENCES {S}.profile_documents(id, profile_id) ON DELETE RESTRICT,
          CONSTRAINT uq_lab_observations_profile_idempotency
            UNIQUE (profile_id, confirmation_idempotency_key),
          CONSTRAINT ck_lab_observations_status CHECK (status = 'active'),
          CONSTRAINT ck_lab_observations_patient_decision CHECK (
            patient_decision IN ('match','not_present')
          ),
          CONSTRAINT ck_lab_observations_not_present_ack CHECK (
            patient_decision <> 'not_present' OR ack_not_present_assignment
          ),
          CONSTRAINT ck_lab_observations_acknowledgements CHECK (
            ack_source AND ack_unit_range AND ack_observed_at
            AND ack_profile AND ack_structured_record
          ),
          CONSTRAINT ck_lab_observations_value_kind CHECK (
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
          CONSTRAINT ck_lab_observations_unit CHECK (
            unit_not_present <> (source_unit_text IS NOT NULL)
          ),
          CONSTRAINT ck_lab_observations_range CHECK (
            reference_range_not_present <>
              (source_reference_range_text IS NOT NULL)
          ),
          CONSTRAINT ck_lab_observations_observed_source CHECK (
            observed_time_unknown <> (source_observed_at_text IS NOT NULL)
          ),
          CONSTRAINT ck_lab_observations_observed_precision CHECK (
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
        f"CREATE INDEX ix_lab_observations_profile_observed "
        f"ON {S}.lab_observations (profile_id, observed_at, observed_date, confirmed_at)"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.lab_observation_sources (
          observation_id uuid NOT NULL
            REFERENCES {S}.lab_observations(id) ON DELETE RESTRICT,
          candidate_id uuid NOT NULL
            REFERENCES {S}.document_ocr_candidates(id) ON DELETE RESTRICT,
          source_role varchar(32) NOT NULL,
          candidate_updated_at timestamptz NOT NULL,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          document_id uuid NOT NULL,
          ocr_run_id uuid NOT NULL
            REFERENCES {S}.document_ocr_runs(id) ON DELETE RESTRICT,
          page_artifact_id uuid NOT NULL
            REFERENCES {S}.document_artifacts(id) ON DELETE RESTRICT,
          page_number integer NOT NULL,
          reviewed_text_snapshot text NOT NULL,
          PRIMARY KEY (observation_id, candidate_id, source_role),
          CONSTRAINT fk_lab_observation_sources_document_profile
            FOREIGN KEY (document_id, profile_id)
            REFERENCES {S}.profile_documents(id, profile_id) ON DELETE RESTRICT,
          CONSTRAINT ck_lab_observation_sources_role CHECK (
            source_role IN (
              'analyte','value','unit','reference_range',
              'observed_at','specimen','flag','comment'
            )
          ),
          CONSTRAINT ck_lab_observation_sources_page CHECK (page_number >= 1),
          CONSTRAINT ck_lab_observation_sources_text CHECK (
            length(reviewed_text_snapshot) BETWEEN 1 AND 10000
            AND reviewed_text_snapshot !~ '[[:cntrl:]]'
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_lab_observation_sources_candidate "
        f"ON {S}.lab_observation_sources (candidate_id, observation_id)"
    )
    op.execute(
        f"""
        ALTER TABLE {S}.lab_observation_drafts
          ADD CONSTRAINT fk_lab_observation_drafts_confirmed_observation
          FOREIGN KEY (confirmed_observation_id)
          REFERENCES {S}.lab_observations(id) ON DELETE RESTRICT,
          ADD CONSTRAINT uq_lab_observation_drafts_confirmed_observation
          UNIQUE (confirmed_observation_id)
        """
    )

    for table in ("lab_observations", "lab_observation_sources"):
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY lab_observations_select "
        f"ON {S}.lab_observations FOR SELECT "
        f"USING ({S}.app_can_view_profile(profile_id))"
    )
    op.execute(
        f"CREATE POLICY lab_observation_sources_select "
        f"ON {S}.lab_observation_sources FOR SELECT "
        f"USING ({S}.app_can_view_profile(profile_id))"
    )

    op.execute(f"GRANT SELECT ON {S}.lab_observations TO {APP}")
    op.execute(f"GRANT SELECT ON {S}.lab_observation_sources TO {APP}")
    op.execute(
        f"REVOKE INSERT, UPDATE, DELETE ON "
        f"{S}.lab_observations, {S}.lab_observation_sources FROM {APP}"
    )

    op.execute(
        f"GRANT SELECT, INSERT ON {S}.lab_observations, "
        f"{S}.lab_observation_sources TO {DEFINER}"
    )
    op.execute(
        f"GRANT SELECT, UPDATE ON {S}.lab_observation_drafts TO {DEFINER}"
    )
    op.execute(f"GRANT SELECT ON {S}.lab_observation_draft_sources TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.document_ocr_candidates TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.document_ocr_runs TO {DEFINER}")
    op.execute(
        f"GRANT SELECT ON {S}.document_ocr_patient_decisions TO {DEFINER}"
    )
    op.execute(f"GRANT SELECT ON {S}.profile_documents TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.health_profiles TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.user_consents TO {DEFINER}")
    op.execute(f"GRANT INSERT ON {S}.profile_audit_events TO {DEFINER}")

    _replace_audit_constraint(include_confirmation=True)
    _create_confirmation_function()


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM {S}.lab_observations)
             OR EXISTS (SELECT 1 FROM {S}.lab_observation_sources) THEN
            RAISE EXCEPTION
              'Cannot downgrade 0058 while confirmed Lab observations exist';
          END IF;
        END $$;
        """
    )
    op.execute(f"REVOKE EXECUTE ON FUNCTION {CONFIRM_SIG} FROM {APP}")
    op.execute(f"DROP FUNCTION IF EXISTS {CONFIRM_SIG}")

    _replace_audit_constraint(include_confirmation=False)

    op.execute(
        f"DROP POLICY IF EXISTS lab_observation_sources_select "
        f"ON {S}.lab_observation_sources"
    )
    op.execute(
        f"DROP POLICY IF EXISTS lab_observations_select "
        f"ON {S}.lab_observations"
    )
    op.execute(f"REVOKE SELECT ON {S}.lab_observation_sources FROM {APP}")
    op.execute(f"REVOKE SELECT ON {S}.lab_observations FROM {APP}")

    op.execute(
        f"ALTER TABLE {S}.lab_observation_drafts "
        "DROP CONSTRAINT uq_lab_observation_drafts_confirmed_observation, "
        "DROP CONSTRAINT fk_lab_observation_drafts_confirmed_observation"
    )
    op.execute(f"DROP TABLE {S}.lab_observation_sources")
    op.execute(f"DROP TABLE {S}.lab_observations")

    op.execute(
        f"""
        ALTER TABLE {S}.lab_observation_drafts
          DROP CONSTRAINT ck_lab_observation_drafts_confirmation_state,
          DROP CONSTRAINT ck_lab_observation_drafts_status,
          DROP COLUMN confirmed_observation_id,
          DROP COLUMN confirmed_by_user_id,
          DROP COLUMN confirmed_at,
          ADD CONSTRAINT ck_lab_observation_drafts_status CHECK (
            status IN ('draft','ready','rejected')
          )
        """
    )
