"""Add HC-017 D1 local OCR candidate extraction boundary.

Revision ID: 0054
Revises: 0053

This migration creates OCR run, encrypted provenance and review-candidate
metadata. It does not create clinical or laboratory facts and does not enable
production document upload.
"""

from __future__ import annotations

from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"
RENDERER = "health_compass_renderer"
RECONCILER = "health_compass_reconciler"
OCR = "health_compass_ocr_worker"

REVIEW_HELPER_SIG = f"{S}.app_can_review_document_ocr(uuid)"
QUEUE_SIG = f"{S}.app_queue_document_ocr(uuid,uuid,uuid,text,text,text,integer)"
CLAIM_SIG = f"{S}.app_claim_document_ocr_run(text,integer,integer)"
HEARTBEAT_SIG = (
    f"{S}.app_heartbeat_document_ocr_run(uuid,text,timestamp with time zone,integer)"
)
COMPLETE_SIG = (
    f"{S}.app_complete_document_ocr_run("
    "uuid,text,timestamp with time zone,text,text,text,text,jsonb,jsonb,uuid)"
)
FAIL_SIG = (
    f"{S}.app_fail_document_ocr_run("
    "uuid,text,timestamp with time zone,text,boolean,integer,integer,uuid)"
)
LIST_REFS_SIG = f"{S}.app_list_document_storage_references()"
LIST_REFS_PRE_SIG = f"{S}.app_list_document_storage_references_pre_ocr()"
MARK_MISSING_SIG = f"{S}.app_mark_document_object_missing(text,text,uuid)"
MARK_MISSING_PRE_SIG = f"{S}.app_mark_document_object_missing_pre_ocr(text,text,uuid)"

AUDIT_ACTIONS_0053 = """
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
            'document.storage_missing'
"""


def _replace_audit_constraint(*, include_ocr_actions: bool) -> None:
    actions = AUDIT_ACTIONS_0053
    if include_ocr_actions:
        actions = (
            f"{actions.rstrip()},\n"
            "            'document.ocr_ready',\n"
            "            'document.ocr_failed',\n"
            "            'document.ocr_storage_missing'\n"
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


def _require_role(role_name: str) -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
          target_role record;
        BEGIN
          SELECT * INTO target_role FROM pg_roles WHERE rolname = '{role_name}';
          IF target_role IS NULL THEN
            RAISE EXCEPTION
              'Provision first: CREATE ROLE {role_name} LOGIN NOBYPASSRLS '
              'NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION';
          END IF;
          IF NOT target_role.rolcanlogin
             OR target_role.rolbypassrls
             OR target_role.rolsuper
             OR target_role.rolcreatedb
             OR target_role.rolcreaterole
             OR target_role.rolreplication THEN
            RAISE EXCEPTION
              'Role {role_name} must be LOGIN NOBYPASSRLS NOSUPERUSER '
              'NOCREATEDB NOCREATEROLE NOREPLICATION';
          END IF;
        END $$;
        """
    )


def _create_review_helper() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_can_review_document_ocr(target_profile_id uuid)
        RETURNS boolean
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        BEGIN
          RETURN EXISTS (
            SELECT 1
            FROM {S}.health_profiles hp
            WHERE hp.id = target_profile_id
              AND hp.owner_user_id = {S}.app_current_user_id()
          ) OR EXISTS (
            SELECT 1
            FROM {S}.profile_permissions pp
            WHERE pp.profile_id = target_profile_id
              AND pp.user_id = {S}.app_current_user_id()
              AND pp.permission IN ('owner', 'edit')
          );
        END;
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {REVIEW_HELPER_SIG} OWNER TO {DEFINER}")
    op.execute(f"ALTER FUNCTION {REVIEW_HELPER_SIG} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {REVIEW_HELPER_SIG} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {REVIEW_HELPER_SIG} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def _create_queue_function() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_queue_document_ocr(
          p_document_id uuid,
          p_render_run_id uuid,
          p_ocr_run_id uuid,
          p_idempotency_key text,
          p_input_manifest_sha256 text,
          p_language_spec text,
          p_psm integer
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          target_profile_id uuid;
          existing_run record;
        BEGIN
          IF SESSION_USER <> '{RENDERER}' THEN
            RAISE EXCEPTION 'OCR queue operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_idempotency_key IS NULL OR length(p_idempotency_key) > 255
             OR p_input_manifest_sha256 !~ '^[0-9a-f]{{64}}$'
             OR p_language_spec !~ '^[a-z]{{3}}([+][a-z]{{3}}){{0,4}}$'
             OR p_psm NOT IN (3, 4, 6, 11, 12) THEN
            RAISE EXCEPTION 'Invalid OCR queue payload' USING ERRCODE = 'HC422';
          END IF;

          SELECT d.profile_id INTO target_profile_id
          FROM {S}.profile_documents d
          WHERE d.id = p_document_id
            AND d.status = 'accepted'
            AND d.render_status = 'ready'
            AND d.render_run_id = p_render_run_id
            AND d.erased_at IS NULL
            AND d.voided_at IS NULL
          FOR UPDATE;
          IF target_profile_id IS NULL THEN
            RAISE EXCEPTION 'Document render state conflict' USING ERRCODE = 'HC409';
          END IF;

          SELECT r.* INTO existing_run
          FROM {S}.document_ocr_runs r
          WHERE r.idempotency_key = p_idempotency_key
          FOR UPDATE;
          IF existing_run.id IS NOT NULL THEN
            IF existing_run.id <> p_ocr_run_id
               OR existing_run.document_id <> p_document_id
               OR existing_run.render_run_id <> p_render_run_id
               OR existing_run.input_manifest_sha256 <> p_input_manifest_sha256
               OR existing_run.language_spec <> p_language_spec
               OR existing_run.psm <> p_psm THEN
              RAISE EXCEPTION 'OCR queue idempotency conflict' USING ERRCODE = 'HC409';
            END IF;
          ELSE
            INSERT INTO {S}.document_ocr_runs (
              id, document_id, profile_id, render_run_id, status, attempt,
              idempotency_key, input_manifest_sha256, language_spec, psm
            ) VALUES (
              p_ocr_run_id, p_document_id, target_profile_id, p_render_run_id,
              'queued', 0, p_idempotency_key, p_input_manifest_sha256,
              p_language_spec, p_psm
            );
          END IF;

          UPDATE {S}.profile_documents
          SET ocr_status = CASE
                WHEN ocr_status IN ('review_required') THEN ocr_status
                ELSE 'queued'
              END,
              current_ocr_run_id = p_ocr_run_id,
              updated_at = pg_catalog.now()
          WHERE id = p_document_id AND profile_id = target_profile_id;
          RETURN true;
        END;
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {QUEUE_SIG} OWNER TO {DEFINER}")
    op.execute(f"ALTER FUNCTION {QUEUE_SIG} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {QUEUE_SIG} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {QUEUE_SIG} FROM {APP}")
    op.execute(f"GRANT EXECUTE ON FUNCTION {QUEUE_SIG} TO {RENDERER}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def _create_worker_functions() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_claim_document_ocr_run(
          p_worker_id text,
          p_lease_seconds integer,
          p_max_attempts integer
        )
        RETURNS TABLE (
          run_id uuid,
          document_id uuid,
          profile_id uuid,
          render_run_id uuid,
          attempt integer,
          lease_expires_at timestamptz,
          input_manifest_sha256 text,
          language_spec text,
          psm integer,
          pages jsonb
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          selected_run_id uuid;
          expected_pages integer;
          actual_pages integer;
        BEGIN
          IF SESSION_USER <> '{OCR}' THEN
            RAISE EXCEPTION 'OCR worker operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_worker_id IS NULL OR p_worker_id !~ '^[A-Za-z0-9._:-]{{1,128}}$'
             OR p_lease_seconds < 30 OR p_lease_seconds > 1800
             OR p_max_attempts < 1 OR p_max_attempts > 10 THEN
            RAISE EXCEPTION 'Invalid OCR claim policy' USING ERRCODE = 'HC422';
          END IF;

          SELECT r.id, d.page_count INTO selected_run_id, expected_pages
          FROM {S}.document_ocr_runs r
          JOIN {S}.profile_documents d
            ON d.id = r.document_id AND d.profile_id = r.profile_id
          WHERE r.status = 'queued'
            AND (r.next_attempt_at IS NULL OR r.next_attempt_at <= pg_catalog.now())
            AND r.attempt < p_max_attempts
            AND d.status = 'accepted'
            AND d.render_status = 'ready'
            AND d.render_run_id = r.render_run_id
            AND d.current_ocr_run_id = r.id
            AND d.voided_at IS NULL
            AND d.erased_at IS NULL
          ORDER BY r.created_at, r.id
          FOR UPDATE OF r SKIP LOCKED
          LIMIT 1;

          IF selected_run_id IS NULL THEN
            RETURN;
          END IF;

          SELECT count(*) INTO actual_pages
          FROM {S}.document_artifacts a
          JOIN {S}.document_ocr_runs r ON r.id = selected_run_id
          WHERE a.document_id = r.document_id
            AND a.profile_id = r.profile_id
            AND a.run_id = r.render_run_id
            AND a.artifact_type = 'safe_page'
            AND a.status = 'ready'
            AND a.erased_at IS NULL;
          IF expected_pages IS NULL OR actual_pages <> expected_pages THEN
            RAISE EXCEPTION 'OCR page manifest conflict' USING ERRCODE = 'HC409';
          END IF;

          UPDATE {S}.document_ocr_runs r
          SET status = 'leased',
              attempt = r.attempt + 1,
              lease_owner = p_worker_id,
              lease_expires_at = pg_catalog.now()
                + pg_catalog.make_interval(secs => p_lease_seconds),
              started_at = coalesce(r.started_at, pg_catalog.now()),
              updated_at = pg_catalog.now(),
              safe_error_code = NULL,
              next_attempt_at = NULL
          WHERE r.id = selected_run_id;

          UPDATE {S}.profile_documents d
          SET ocr_status = 'processing', updated_at = pg_catalog.now()
          FROM {S}.document_ocr_runs r
          WHERE r.id = selected_run_id
            AND d.id = r.document_id AND d.profile_id = r.profile_id;

          RETURN QUERY
          SELECT
            r.id,
            r.document_id,
            r.profile_id,
            r.render_run_id,
            r.attempt,
            r.lease_expires_at,
            r.input_manifest_sha256::text,
            r.language_spec::text,
            r.psm,
            (
              SELECT pg_catalog.jsonb_agg(
                pg_catalog.jsonb_build_object(
                  'artifact_id', a.id,
                  'page_number', a.page_number,
                  'storage_key', a.storage_key,
                  'encryption_format', a.encryption_format,
                  'encryption_key_id', a.encryption_key_id,
                  'sha256', a.sha256,
                  'width', a.width,
                  'height', a.height
                ) ORDER BY a.page_number
              )
              FROM {S}.document_artifacts a
              WHERE a.document_id = r.document_id
                AND a.profile_id = r.profile_id
                AND a.run_id = r.render_run_id
                AND a.artifact_type = 'safe_page'
                AND a.status = 'ready'
                AND a.erased_at IS NULL
            )
          FROM {S}.document_ocr_runs r
          WHERE r.id = selected_run_id;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_heartbeat_document_ocr_run(
          p_run_id uuid,
          p_worker_id text,
          p_expected_lease timestamptz,
          p_lease_seconds integer
        )
        RETURNS timestamptz
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          new_lease timestamptz;
        BEGIN
          IF SESSION_USER <> '{OCR}' THEN
            RAISE EXCEPTION 'OCR worker operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_lease_seconds < 30 OR p_lease_seconds > 1800 THEN
            RAISE EXCEPTION 'Invalid OCR lease duration' USING ERRCODE = 'HC422';
          END IF;
          UPDATE {S}.document_ocr_runs
          SET lease_expires_at = pg_catalog.now()
                + pg_catalog.make_interval(secs => p_lease_seconds),
              updated_at = pg_catalog.now()
          WHERE id = p_run_id
            AND status = 'leased'
            AND lease_owner = p_worker_id
            AND lease_expires_at = p_expected_lease
            AND lease_expires_at > pg_catalog.now()
          RETURNING lease_expires_at INTO new_lease;
          IF new_lease IS NULL THEN
            RAISE EXCEPTION 'OCR worker lease conflict' USING ERRCODE = 'HC409';
          END IF;
          RETURN new_lease;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_complete_document_ocr_run(
          p_run_id uuid,
          p_worker_id text,
          p_expected_lease timestamptz,
          p_engine_name text,
          p_engine_version text,
          p_traineddata_manifest_sha256 text,
          p_output_manifest_sha256 text,
          p_artifacts jsonb,
          p_candidates jsonb,
          p_audit_event_id uuid
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          target_run {S}.document_ocr_runs%ROWTYPE;
          target_actor_id uuid;
          artifact_item jsonb;
          candidate_item jsonb;
          artifact_count integer;
          candidate_count integer;
          total_text_bytes bigint;
        BEGIN
          IF SESSION_USER <> '{OCR}' THEN
            RAISE EXCEPTION 'OCR worker operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_engine_name IS NULL OR length(p_engine_name) > 64
             OR p_engine_version IS NULL OR length(p_engine_version) > 64
             OR p_traineddata_manifest_sha256 !~ '^[0-9a-f]{{64}}$'
             OR p_output_manifest_sha256 !~ '^[0-9a-f]{{64}}$'
             OR pg_catalog.jsonb_typeof(p_artifacts) <> 'array'
             OR pg_catalog.jsonb_typeof(p_candidates) <> 'array' THEN
            RAISE EXCEPTION 'Invalid OCR completion payload' USING ERRCODE = 'HC422';
          END IF;

          SELECT * INTO target_run
          FROM {S}.document_ocr_runs
          WHERE id = p_run_id
          FOR UPDATE;
          IF target_run.id IS NULL THEN
            RAISE EXCEPTION 'OCR run not found' USING ERRCODE = 'HC404';
          END IF;
          IF target_run.status = 'succeeded' THEN
            IF target_run.output_manifest_sha256 = p_output_manifest_sha256 THEN
              RETURN true;
            END IF;
            RAISE EXCEPTION 'OCR completion conflict' USING ERRCODE = 'HC409';
          END IF;
          IF target_run.status <> 'leased'
             OR target_run.lease_owner <> p_worker_id
             OR target_run.lease_expires_at <> p_expected_lease
             OR target_run.lease_expires_at <= pg_catalog.now() THEN
            RAISE EXCEPTION 'OCR worker lease conflict' USING ERRCODE = 'HC409';
          END IF;

          PERFORM 1
          FROM {S}.profile_documents d
          WHERE d.id = target_run.document_id
            AND d.profile_id = target_run.profile_id
            AND d.status = 'accepted'
            AND d.render_status = 'ready'
            AND d.render_run_id = target_run.render_run_id
            AND d.current_ocr_run_id = target_run.id
            AND d.voided_at IS NULL
            AND d.erased_at IS NULL
          FOR UPDATE;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'OCR document state conflict' USING ERRCODE = 'HC409';
          END IF;

          artifact_count := pg_catalog.jsonb_array_length(p_artifacts);
          candidate_count := pg_catalog.jsonb_array_length(p_candidates);
          IF artifact_count < 1 OR artifact_count > 50
             OR candidate_count > 5000
             OR pg_catalog.octet_length(p_artifacts::text) > 1048576
             OR pg_catalog.octet_length(p_candidates::text) > 4194304 THEN
            RAISE EXCEPTION 'OCR completion bounds exceeded' USING ERRCODE = 'HC422';
          END IF;

          SELECT coalesce(sum(pg_catalog.octet_length(value ->> 'original_text')), 0)
          INTO total_text_bytes
          FROM pg_catalog.jsonb_array_elements(p_candidates);
          IF total_text_bytes > 1048576 THEN
            RAISE EXCEPTION 'OCR candidate text bounds exceeded' USING ERRCODE = 'HC422';
          END IF;

          FOR artifact_item IN
            SELECT value FROM pg_catalog.jsonb_array_elements(p_artifacts)
          LOOP
            IF artifact_item ->> 'storage_key'
                 !~ '^ocr/[0-9a-f-]{{36}}/[0-9a-f-]{{36}}/page-[1-9][0-9]*[.]tsv[.]hcenc$'
               OR artifact_item ->> 'sha256' !~ '^[0-9a-f]{{64}}$'
               OR artifact_item ->> 'encryption_format' <> 'hcenc1'
               OR artifact_item ->> 'encryption_key_id'
                    !~ '^[A-Za-z0-9._-]{{1,64}}$'
               OR (artifact_item ->> 'page_number')::integer NOT BETWEEN 1 AND 50
               OR (artifact_item ->> 'byte_size')::bigint < 1
               OR (artifact_item ->> 'encrypted_size')::bigint
                    <= (artifact_item ->> 'byte_size')::bigint THEN
              RAISE EXCEPTION 'Invalid OCR artifact payload' USING ERRCODE = 'HC422';
            END IF;
            PERFORM 1
            FROM {S}.document_artifacts a
            WHERE a.id = (artifact_item ->> 'page_artifact_id')::uuid
              AND a.document_id = target_run.document_id
              AND a.profile_id = target_run.profile_id
              AND a.run_id = target_run.render_run_id
              AND a.page_number = (artifact_item ->> 'page_number')::integer
              AND a.artifact_type = 'safe_page'
              AND a.status = 'ready'
              AND a.erased_at IS NULL;
            IF NOT FOUND THEN
              RAISE EXCEPTION 'OCR source artifact conflict' USING ERRCODE = 'HC409';
            END IF;
            INSERT INTO {S}.document_ocr_artifacts (
              id, run_id, document_id, profile_id, page_artifact_id,
              page_number, artifact_type, status, storage_backend, storage_key,
              byte_size, encrypted_size, sha256, encryption_format,
              encryption_key_id, engine_name, engine_version, language_spec
            ) VALUES (
              (artifact_item ->> 'id')::uuid,
              target_run.id,
              target_run.document_id,
              target_run.profile_id,
              (artifact_item ->> 'page_artifact_id')::uuid,
              (artifact_item ->> 'page_number')::integer,
              'tesseract_tsv', 'ready', 'local_encrypted',
              artifact_item ->> 'storage_key',
              (artifact_item ->> 'byte_size')::bigint,
              (artifact_item ->> 'encrypted_size')::bigint,
              artifact_item ->> 'sha256',
              artifact_item ->> 'encryption_format',
              artifact_item ->> 'encryption_key_id',
              p_engine_name, p_engine_version, target_run.language_spec
            )
            ON CONFLICT (run_id, page_number) DO NOTHING;
          END LOOP;

          FOR candidate_item IN
            SELECT value FROM pg_catalog.jsonb_array_elements(p_candidates)
          LOOP
            IF pg_catalog.jsonb_typeof(candidate_item -> 'original_text') <> 'string'
               OR length(candidate_item ->> 'original_text') NOT BETWEEN 1 AND 4000
               OR (candidate_item ->> 'page_number')::integer NOT BETWEEN 1 AND 50
               OR (candidate_item ->> 'candidate_index')::integer < 0
               OR (candidate_item ->> 'word_count')::integer NOT BETWEEN 1 AND 200
               OR (candidate_item ->> 'left_px')::integer < 0
               OR (candidate_item ->> 'top_px')::integer < 0
               OR (candidate_item ->> 'width_px')::integer < 1
               OR (candidate_item ->> 'height_px')::integer < 1
               OR (candidate_item ->> 'confidence_min')::double precision < 0
               OR (candidate_item ->> 'confidence_min')::double precision > 100
               OR (candidate_item ->> 'confidence_mean')::double precision < 0
               OR (candidate_item ->> 'confidence_mean')::double precision > 100 THEN
              RAISE EXCEPTION 'Invalid OCR candidate payload' USING ERRCODE = 'HC422';
            END IF;
            PERFORM 1
            FROM {S}.document_artifacts a
            WHERE a.id = (candidate_item ->> 'page_artifact_id')::uuid
              AND a.document_id = target_run.document_id
              AND a.profile_id = target_run.profile_id
              AND a.run_id = target_run.render_run_id
              AND a.page_number = (candidate_item ->> 'page_number')::integer
              AND (candidate_item ->> 'left_px')::integer
                    + (candidate_item ->> 'width_px')::integer <= a.width
              AND (candidate_item ->> 'top_px')::integer
                    + (candidate_item ->> 'height_px')::integer <= a.height
              AND a.status = 'ready';
            IF NOT FOUND THEN
              RAISE EXCEPTION 'OCR candidate source conflict' USING ERRCODE = 'HC409';
            END IF;
            INSERT INTO {S}.document_ocr_candidates (
              id, run_id, document_id, profile_id, page_artifact_id,
              page_number, candidate_index, status, original_text,
              confidence_min, confidence_mean, left_px, top_px,
              width_px, height_px, source_word_count
            ) VALUES (
              (candidate_item ->> 'id')::uuid,
              target_run.id,
              target_run.document_id,
              target_run.profile_id,
              (candidate_item ->> 'page_artifact_id')::uuid,
              (candidate_item ->> 'page_number')::integer,
              (candidate_item ->> 'candidate_index')::integer,
              'needs_review',
              candidate_item ->> 'original_text',
              (candidate_item ->> 'confidence_min')::double precision,
              (candidate_item ->> 'confidence_mean')::double precision,
              (candidate_item ->> 'left_px')::integer,
              (candidate_item ->> 'top_px')::integer,
              (candidate_item ->> 'width_px')::integer,
              (candidate_item ->> 'height_px')::integer,
              (candidate_item ->> 'word_count')::integer
            )
            ON CONFLICT (run_id, page_number, candidate_index) DO NOTHING;
          END LOOP;

          UPDATE {S}.document_ocr_runs
          SET status = 'succeeded',
              engine_name = p_engine_name,
              engine_version = p_engine_version,
              traineddata_manifest_sha256 = p_traineddata_manifest_sha256,
              output_manifest_sha256 = p_output_manifest_sha256,
              lease_owner = NULL,
              lease_expires_at = NULL,
              completed_at = pg_catalog.now(),
              updated_at = pg_catalog.now(),
              safe_error_code = NULL,
              next_attempt_at = NULL
          WHERE id = target_run.id;

          UPDATE {S}.profile_documents
          SET ocr_status = 'review_required',
              ocr_completed_at = pg_catalog.now(),
              updated_at = pg_catalog.now()
          WHERE id = target_run.document_id AND profile_id = target_run.profile_id;

          SELECT uploaded_by_user_id INTO target_actor_id
          FROM {S}.profile_documents
          WHERE id = target_run.document_id AND profile_id = target_run.profile_id;
          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_run.profile_id, target_actor_id,
            'document', target_run.document_id, 'document.ocr_ready',
            '{{}}'::jsonb, 'document-ocr-worker'
          );
          RETURN true;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_fail_document_ocr_run(
          p_run_id uuid,
          p_worker_id text,
          p_expected_lease timestamptz,
          p_error_code text,
          p_retryable boolean,
          p_max_attempts integer,
          p_retry_after_seconds integer,
          p_audit_event_id uuid
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          target_run {S}.document_ocr_runs%ROWTYPE;
          should_retry boolean;
          target_actor_id uuid;
        BEGIN
          IF SESSION_USER <> '{OCR}' THEN
            RAISE EXCEPTION 'OCR worker operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_error_code !~ '^[a-z0-9_:-]{{1,64}}$'
             OR p_max_attempts < 1 OR p_max_attempts > 10
             OR p_retry_after_seconds < 0 OR p_retry_after_seconds > 86400 THEN
            RAISE EXCEPTION 'Invalid OCR retry policy' USING ERRCODE = 'HC422';
          END IF;
          SELECT * INTO target_run
          FROM {S}.document_ocr_runs
          WHERE id = p_run_id
            AND status = 'leased'
            AND lease_owner = p_worker_id
            AND lease_expires_at = p_expected_lease
          FOR UPDATE;
          IF target_run.id IS NULL THEN
            RAISE EXCEPTION 'OCR worker lease conflict' USING ERRCODE = 'HC409';
          END IF;
          should_retry := p_retryable AND target_run.attempt < p_max_attempts;
          UPDATE {S}.document_ocr_runs
          SET status = CASE WHEN should_retry THEN 'queued' ELSE 'failed' END,
              lease_owner = NULL,
              lease_expires_at = NULL,
              completed_at = CASE WHEN should_retry THEN NULL ELSE pg_catalog.now() END,
              safe_error_code = p_error_code,
              next_attempt_at = CASE WHEN should_retry THEN
                pg_catalog.now() + pg_catalog.make_interval(secs => p_retry_after_seconds)
                ELSE NULL END,
              updated_at = pg_catalog.now()
          WHERE id = target_run.id;
          UPDATE {S}.profile_documents
          SET ocr_status = CASE WHEN should_retry THEN 'queued' ELSE 'error' END,
              failure_code = CASE WHEN should_retry THEN failure_code ELSE p_error_code END,
              updated_at = pg_catalog.now()
          WHERE id = target_run.document_id AND profile_id = target_run.profile_id;
          IF NOT should_retry THEN
            SELECT uploaded_by_user_id INTO target_actor_id
            FROM {S}.profile_documents
            WHERE id = target_run.document_id AND profile_id = target_run.profile_id;
            INSERT INTO {S}.profile_audit_events (
              id, profile_id, actor_user_id, entity_type, entity_id,
              action, changed_fields, request_id
            ) VALUES (
              p_audit_event_id, target_run.profile_id, target_actor_id,
              'document', target_run.document_id, 'document.ocr_failed',
              '{{}}'::jsonb, 'document-ocr-worker'
            );
          END IF;
          RETURN true;
        END;
        $$
        """
    )

    for signature in (CLAIM_SIG, HEARTBEAT_SIG, COMPLETE_SIG, FAIL_SIG):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {DEFINER}")
        op.execute(f"ALTER FUNCTION {signature} SET row_security = off")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {APP}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {RENDERER}")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {RECONCILER}")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {OCR}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def _wrap_reconciliation() -> None:
    op.execute(
        f"ALTER FUNCTION {LIST_REFS_SIG} "
        "RENAME TO app_list_document_storage_references_pre_ocr"
    )
    op.execute(
        f"ALTER FUNCTION {MARK_MISSING_SIG} "
        "RENAME TO app_mark_document_object_missing_pre_ocr"
    )
    for signature in (LIST_REFS_PRE_SIG, MARK_MISSING_PRE_SIG):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {RECONCILER}")

    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_list_document_storage_references()
        RETURNS TABLE (
          storage_key text,
          document_id uuid,
          profile_id uuid,
          artifact_role text
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        BEGIN
          IF SESSION_USER <> '{RECONCILER}' THEN
            RAISE EXCEPTION 'Reconciliation operation denied' USING ERRCODE = 'HC404';
          END IF;
          RETURN QUERY SELECT * FROM {S}.app_list_document_storage_references_pre_ocr();
          RETURN QUERY
          SELECT a.storage_key::text, a.document_id, a.profile_id,
                 ('ocr_tsv:' || a.page_number::text)::text
          FROM {S}.document_ocr_artifacts a
          WHERE a.erased_at IS NULL
            AND a.status IN ('ready', 'deletion_pending');
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_mark_document_object_missing(
          p_storage_key text,
          p_error_code text,
          p_audit_event_id uuid
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          target_artifact_id uuid;
          target_run_id uuid;
          target_document_id uuid;
          target_profile_id uuid;
          target_actor_id uuid;
          already_marked boolean;
        BEGIN
          IF SESSION_USER <> '{RECONCILER}' THEN
            RAISE EXCEPTION 'Reconciliation operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_storage_key IS NULL OR length(p_storage_key) > 512
             OR p_storage_key !~ '^(quarantine|accepted|derived|ocr)/[A-Za-z0-9._/-]+[.]hcenc$'
             OR p_error_code !~ '^[a-z0-9_:-]{{1,64}}$' THEN
            RAISE EXCEPTION 'Invalid reconciliation input' USING ERRCODE = 'HC422';
          END IF;
          SELECT a.id, a.run_id, a.document_id, a.profile_id,
                 d.uploaded_by_user_id,
                 (a.status = 'deletion_pending'
                  AND r.status = 'failed'
                  AND r.safe_error_code = p_error_code)
          INTO target_artifact_id, target_run_id, target_document_id,
               target_profile_id, target_actor_id, already_marked
          FROM {S}.document_ocr_artifacts a
          JOIN {S}.document_ocr_runs r ON r.id = a.run_id
          JOIN {S}.profile_documents d
            ON d.id = a.document_id AND d.profile_id = a.profile_id
          WHERE a.storage_key = p_storage_key AND a.erased_at IS NULL
          FOR UPDATE OF a, r, d;
          IF target_artifact_id IS NULL THEN
            RETURN {S}.app_mark_document_object_missing_pre_ocr(
              p_storage_key, p_error_code, p_audit_event_id
            );
          END IF;
          IF already_marked THEN
            RETURN true;
          END IF;
          UPDATE {S}.document_ocr_artifacts
          SET status = 'deletion_pending',
              deletion_requested_at = coalesce(deletion_requested_at, pg_catalog.now()),
              updated_at = pg_catalog.now()
          WHERE id = target_artifact_id;
          UPDATE {S}.document_ocr_runs
          SET status = 'failed', safe_error_code = p_error_code,
              completed_at = coalesce(completed_at, pg_catalog.now()),
              updated_at = pg_catalog.now()
          WHERE id = target_run_id;
          UPDATE {S}.profile_documents
          SET ocr_status = 'error', failure_code = p_error_code,
              updated_at = pg_catalog.now()
          WHERE id = target_document_id AND profile_id = target_profile_id;
          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_profile_id, target_actor_id,
            'document', target_document_id, 'document.ocr_storage_missing',
            '{{}}'::jsonb, 'document-reconciler'
          );
          RETURN true;
        END;
        $$
        """
    )
    for signature in (LIST_REFS_SIG, MARK_MISSING_SIG):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {DEFINER}")
        op.execute(f"ALTER FUNCTION {signature} SET row_security = off")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {APP}")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {RECONCILER}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def upgrade() -> None:
    _require_role(OCR)

    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "ADD COLUMN ocr_status varchar(32) NOT NULL DEFAULT 'not_started', "
        "ADD COLUMN current_ocr_run_id uuid NULL, "
        "ADD COLUMN ocr_completed_at timestamptz NULL, "
        "ADD CONSTRAINT ck_profile_documents_ocr_status CHECK ("
        "ocr_status IN ('not_started','queued','processing','review_required','error')), "
        "ADD CONSTRAINT ck_profile_documents_ocr_metadata CHECK ("
        "ocr_status <> 'review_required' OR ("
        "current_ocr_run_id IS NOT NULL AND ocr_completed_at IS NOT NULL))"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.document_ocr_runs (
          id uuid PRIMARY KEY,
          document_id uuid NOT NULL,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          render_run_id uuid NOT NULL,
          status varchar(32) NOT NULL,
          attempt integer NOT NULL DEFAULT 0,
          idempotency_key varchar(255) NOT NULL UNIQUE,
          input_manifest_sha256 varchar(64) NOT NULL,
          output_manifest_sha256 varchar(64) NULL,
          engine_name varchar(64) NULL,
          engine_version varchar(64) NULL,
          language_spec varchar(64) NOT NULL,
          traineddata_manifest_sha256 varchar(64) NULL,
          psm integer NOT NULL,
          lease_owner varchar(128) NULL,
          lease_expires_at timestamptz NULL,
          next_attempt_at timestamptz NULL,
          started_at timestamptz NULL,
          completed_at timestamptz NULL,
          safe_error_code varchar(64) NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_document_ocr_runs_document_profile
            FOREIGN KEY (document_id, profile_id)
            REFERENCES {S}.profile_documents(id, profile_id) ON DELETE CASCADE,
          CONSTRAINT uq_document_ocr_runs_document_render_config
            UNIQUE (document_id, render_run_id, language_spec, psm),
          CONSTRAINT ck_document_ocr_runs_status CHECK (
            status IN ('queued','leased','succeeded','failed','cancelled')
          ),
          CONSTRAINT ck_document_ocr_runs_attempt CHECK (attempt >= 0),
          CONSTRAINT ck_document_ocr_runs_hashes CHECK (
            input_manifest_sha256 ~ '^[0-9a-f]{{64}}$'
            AND (output_manifest_sha256 IS NULL
                 OR output_manifest_sha256 ~ '^[0-9a-f]{{64}}$')
            AND (traineddata_manifest_sha256 IS NULL
                 OR traineddata_manifest_sha256 ~ '^[0-9a-f]{{64}}$')
          ),
          CONSTRAINT ck_document_ocr_runs_language CHECK (
            language_spec ~ '^[a-z]{{3}}([+][a-z]{{3}}){{0,4}}$'
          ),
          CONSTRAINT ck_document_ocr_runs_psm CHECK (psm IN (3,4,6,11,12)),
          CONSTRAINT ck_document_ocr_runs_lease CHECK (
            (status = 'leased' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
            OR (status <> 'leased' AND lease_owner IS NULL AND lease_expires_at IS NULL)
          ),
          CONSTRAINT ck_document_ocr_runs_completion CHECK (
            (status = 'succeeded' AND completed_at IS NOT NULL
             AND output_manifest_sha256 IS NOT NULL
             AND engine_name IS NOT NULL AND engine_version IS NOT NULL
             AND traineddata_manifest_sha256 IS NOT NULL)
            OR status <> 'succeeded'
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_document_ocr_runs_claim "
        f"ON {S}.document_ocr_runs (status, next_attempt_at, created_at)"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.document_ocr_artifacts (
          id uuid PRIMARY KEY,
          run_id uuid NOT NULL REFERENCES {S}.document_ocr_runs(id) ON DELETE CASCADE,
          document_id uuid NOT NULL,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          page_artifact_id uuid NOT NULL REFERENCES {S}.document_artifacts(id),
          page_number integer NOT NULL,
          artifact_type varchar(32) NOT NULL,
          status varchar(32) NOT NULL,
          storage_backend varchar(32) NOT NULL,
          storage_key varchar(512) NOT NULL UNIQUE,
          byte_size bigint NOT NULL,
          encrypted_size bigint NOT NULL,
          sha256 varchar(64) NOT NULL,
          encryption_format varchar(32) NOT NULL,
          encryption_key_id varchar(64) NOT NULL,
          engine_name varchar(64) NOT NULL,
          engine_version varchar(64) NOT NULL,
          language_spec varchar(64) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          deletion_requested_at timestamptz NULL,
          erased_at timestamptz NULL,
          CONSTRAINT fk_document_ocr_artifacts_document_profile
            FOREIGN KEY (document_id, profile_id)
            REFERENCES {S}.profile_documents(id, profile_id) ON DELETE CASCADE,
          CONSTRAINT uq_document_ocr_artifacts_run_page UNIQUE (run_id, page_number),
          CONSTRAINT ck_document_ocr_artifacts_page CHECK (page_number BETWEEN 1 AND 50),
          CONSTRAINT ck_document_ocr_artifacts_type CHECK (artifact_type = 'tesseract_tsv'),
          CONSTRAINT ck_document_ocr_artifacts_status CHECK (
            status IN ('ready','deletion_pending','erased')
          ),
          CONSTRAINT ck_document_ocr_artifacts_storage CHECK (
            storage_backend = 'local_encrypted'
            AND storage_key ~ '^ocr/[0-9a-f-]{{36}}/[0-9a-f-]{{36}}/page-[1-9][0-9]*[.]tsv[.]hcenc$'
          ),
          CONSTRAINT ck_document_ocr_artifacts_size CHECK (
            byte_size > 0 AND encrypted_size > byte_size
          ),
          CONSTRAINT ck_document_ocr_artifacts_hash CHECK (sha256 ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_document_ocr_artifacts_encryption CHECK (
            encryption_format = 'hcenc1'
            AND encryption_key_id ~ '^[A-Za-z0-9._-]{{1,64}}$'
          ),
          CONSTRAINT ck_document_ocr_artifacts_erasure CHECK (
            erased_at IS NULL OR deletion_requested_at IS NOT NULL
          )
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE {S}.document_ocr_candidates (
          id uuid PRIMARY KEY,
          run_id uuid NOT NULL REFERENCES {S}.document_ocr_runs(id) ON DELETE CASCADE,
          document_id uuid NOT NULL,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          page_artifact_id uuid NOT NULL REFERENCES {S}.document_artifacts(id),
          page_number integer NOT NULL,
          candidate_index integer NOT NULL,
          status varchar(32) NOT NULL,
          original_text text NOT NULL,
          reviewed_text text NULL,
          confidence_min double precision NOT NULL,
          confidence_mean double precision NOT NULL,
          left_px integer NOT NULL,
          top_px integer NOT NULL,
          width_px integer NOT NULL,
          height_px integer NOT NULL,
          source_word_count integer NOT NULL,
          reviewed_by_user_id uuid NULL REFERENCES {S}.users(id),
          reviewed_at timestamptz NULL,
          review_note varchar(500) NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_document_ocr_candidates_document_profile
            FOREIGN KEY (document_id, profile_id)
            REFERENCES {S}.profile_documents(id, profile_id) ON DELETE CASCADE,
          CONSTRAINT uq_document_ocr_candidates_run_index
            UNIQUE (run_id, page_number, candidate_index),
          CONSTRAINT ck_document_ocr_candidates_page CHECK (page_number BETWEEN 1 AND 50),
          CONSTRAINT ck_document_ocr_candidates_index CHECK (candidate_index >= 0),
          CONSTRAINT ck_document_ocr_candidates_status CHECK (
            status IN ('needs_review','accepted','edited','rejected','deferred')
          ),
          CONSTRAINT ck_document_ocr_candidates_text CHECK (
            length(original_text) BETWEEN 1 AND 4000
            AND (reviewed_text IS NULL OR length(reviewed_text) BETWEEN 1 AND 4000)
          ),
          CONSTRAINT ck_document_ocr_candidates_confidence CHECK (
            confidence_min BETWEEN 0 AND 100
            AND confidence_mean BETWEEN 0 AND 100
          ),
          CONSTRAINT ck_document_ocr_candidates_box CHECK (
            left_px >= 0 AND top_px >= 0 AND width_px > 0 AND height_px > 0
          ),
          CONSTRAINT ck_document_ocr_candidates_words CHECK (
            source_word_count BETWEEN 1 AND 200
          ),
          CONSTRAINT ck_document_ocr_candidates_review CHECK (
            (status = 'needs_review' AND reviewed_text IS NULL
             AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL)
            OR status <> 'needs_review'
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_document_ocr_candidates_document_status "
        f"ON {S}.document_ocr_candidates (document_id, status, page_number, candidate_index)"
    )

    for table in (
        'document_ocr_runs', 'document_ocr_artifacts', 'document_ocr_candidates'
    ):
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")

    _create_review_helper()
    op.execute(
        f"CREATE POLICY document_ocr_runs_select ON {S}.document_ocr_runs "
        f"FOR SELECT USING ({S}.app_can_view_document(profile_id))"
    )
    op.execute(
        f"CREATE POLICY document_ocr_candidates_select ON {S}.document_ocr_candidates "
        f"FOR SELECT USING ({S}.app_can_review_document_ocr(profile_id))"
    )
    op.execute(f"GRANT SELECT ON {S}.document_ocr_runs TO {APP}")
    op.execute(f"GRANT SELECT ON {S}.document_ocr_candidates TO {APP}")
    for table in ('document_ocr_runs', 'document_ocr_artifacts', 'document_ocr_candidates'):
        op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {S}.{table} FROM {APP}")

    _replace_audit_constraint(include_ocr_actions=True)

    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.document_ocr_runs TO {DEFINER}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.document_ocr_artifacts TO {DEFINER}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.document_ocr_candidates TO {DEFINER}")
    op.execute(f"GRANT SELECT ON {S}.document_artifacts TO {DEFINER}")
    op.execute(f"GRANT USAGE ON SCHEMA {S} TO {OCR}")

    _create_queue_function()
    _create_worker_functions()
    _wrap_reconciliation()


def downgrade() -> None:
    op.execute(
        f"DROP POLICY IF EXISTS document_ocr_candidates_select "
        f"ON {S}.document_ocr_candidates"
    )
    op.execute(
        f"DROP POLICY IF EXISTS document_ocr_runs_select "
        f"ON {S}.document_ocr_runs"
    )
    for signature, role in (
        (MARK_MISSING_SIG, RECONCILER),
        (LIST_REFS_SIG, RECONCILER),
        (FAIL_SIG, OCR),
        (COMPLETE_SIG, OCR),
        (HEARTBEAT_SIG, OCR),
        (CLAIM_SIG, OCR),
        (QUEUE_SIG, RENDERER),
        (REVIEW_HELPER_SIG, APP),
    ):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {role}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")

    op.execute(
        f"ALTER FUNCTION {LIST_REFS_PRE_SIG} "
        "RENAME TO app_list_document_storage_references"
    )
    op.execute(
        f"ALTER FUNCTION {MARK_MISSING_PRE_SIG} "
        "RENAME TO app_mark_document_object_missing"
    )
    op.execute(f"GRANT EXECUTE ON FUNCTION {LIST_REFS_SIG} TO {RECONCILER}")
    op.execute(f"GRANT EXECUTE ON FUNCTION {MARK_MISSING_SIG} TO {RECONCILER}")

    op.execute(f"REVOKE USAGE ON SCHEMA {S} FROM {OCR}")
    op.execute(f"REVOKE SELECT ON {S}.document_ocr_runs FROM {APP}")
    op.execute(f"REVOKE SELECT ON {S}.document_ocr_candidates FROM {APP}")
    op.execute(
        f"REVOKE SELECT, INSERT, UPDATE ON {S}.document_ocr_candidates FROM {DEFINER}"
    )
    op.execute(
        f"REVOKE SELECT, INSERT, UPDATE ON {S}.document_ocr_artifacts FROM {DEFINER}"
    )
    op.execute(f"REVOKE SELECT, INSERT, UPDATE ON {S}.document_ocr_runs FROM {DEFINER}")

    _replace_audit_constraint(include_ocr_actions=False)

    op.execute(
        f"DROP POLICY IF EXISTS document_ocr_candidates_select ON {S}.document_ocr_candidates"
    )
    op.execute(f"DROP POLICY IF EXISTS document_ocr_runs_select ON {S}.document_ocr_runs")
    op.execute(f"DROP TABLE {S}.document_ocr_candidates")
    op.execute(f"DROP TABLE {S}.document_ocr_artifacts")
    op.execute(f"DROP TABLE {S}.document_ocr_runs")

    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "DROP CONSTRAINT ck_profile_documents_ocr_metadata, "
        "DROP CONSTRAINT ck_profile_documents_ocr_status, "
        "DROP COLUMN ocr_completed_at, "
        "DROP COLUMN current_ocr_run_id, "
        "DROP COLUMN ocr_status"
    )
