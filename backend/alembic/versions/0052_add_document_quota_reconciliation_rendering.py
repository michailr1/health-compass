"""Add HC-017 C2 quota, reconciliation and safe-rendering boundary.

Revision ID: 0052
Revises: 0051

This migration remains a repository-only foundation. It does not enable
production document upload or install parser/scanner services.
"""

from __future__ import annotations

from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"
RENDERER = "health_compass_renderer"
RECONCILER = "health_compass_reconciler"

QUOTA_SIG = f"{S}.app_reserve_document_upload(uuid,bigint,bigint,bigint,integer,integer)"
CLAIM_RENDER_SIG = f"{S}.app_claim_render_job(text,integer,integer)"
HEARTBEAT_RENDER_SIG = (
    f"{S}.app_heartbeat_render_job(uuid,text,timestamp with time zone,integer)"
)
COMPLETE_RENDER_SIG = (
    f"{S}.app_complete_document_render("
    "uuid,text,timestamp with time zone,uuid,text,bigint,text,text,integer,text,text,jsonb,uuid)"
)
FAIL_RENDER_SIG = (
    f"{S}.app_fail_render_job("
    "uuid,text,timestamp with time zone,text,boolean,integer,integer)"
)
LIST_REFS_SIG = f"{S}.app_list_document_storage_references()"
MARK_MISSING_SIG = f"{S}.app_mark_document_object_missing(text,text,uuid)"

AUDIT_ACTIONS_0051 = """
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
            'document.scan_rejected'
"""


def _replace_audit_constraint(*, include_c2_actions: bool) -> None:
    actions = AUDIT_ACTIONS_0051
    if include_c2_actions:
        actions = (
            f"{actions.rstrip()},\n"
            "            'document.render_ready',\n"
            "            'document.render_failed',\n"
            "            'document.storage_missing'\n"
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


def _create_quota_function() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_reserve_document_upload(
          p_profile_id uuid,
          p_additional_bytes bigint,
          p_profile_max_bytes bigint,
          p_global_max_bytes bigint,
          p_profile_max_documents integer,
          p_profile_max_queued_jobs integer
        )
        RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          profile_bytes bigint;
          global_bytes bigint;
          profile_documents integer;
          queued_jobs integer;
        BEGIN
          IF SESSION_USER <> '{APP}' THEN
            RAISE EXCEPTION 'Upload quota operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_additional_bytes < 1
             OR p_profile_max_bytes < 1
             OR p_global_max_bytes < 1
             OR p_profile_max_documents < 1
             OR p_profile_max_queued_jobs < 1 THEN
            RAISE EXCEPTION 'Invalid document quota policy' USING ERRCODE = 'HC422';
          END IF;
          IF NOT {S}.app_can_edit_profile(p_profile_id) THEN
            RAISE EXCEPTION 'Profile not found' USING ERRCODE = 'HC404';
          END IF;

          -- Fixed global-then-profile lock order serializes concurrent quota
          -- decisions without introducing a mutable quota counter table.
          PERFORM pg_catalog.pg_advisory_xact_lock(
            pg_catalog.hashtextextended('hc-document-global-quota', 0)
          );
          PERFORM pg_catalog.pg_advisory_xact_lock(
            pg_catalog.hashtextextended(p_profile_id::text, 1)
          );

          SELECT coalesce(sum(coalesce(d.encrypted_size, d.byte_size)), 0)
                 + coalesce((
                   SELECT sum(coalesce(a.encrypted_size, a.byte_size))
                   FROM {S}.document_artifacts a
                   WHERE a.erased_at IS NULL
                 ), 0)
          INTO global_bytes
          FROM {S}.profile_documents d
          WHERE d.erased_at IS NULL;

          SELECT coalesce(sum(coalesce(d.encrypted_size, d.byte_size)), 0)
                 + coalesce((
                   SELECT sum(coalesce(a.encrypted_size, a.byte_size))
                   FROM {S}.document_artifacts a
                   WHERE a.profile_id = p_profile_id
                     AND a.erased_at IS NULL
                 ), 0),
                 count(*)
          INTO profile_bytes, profile_documents
          FROM {S}.profile_documents d
          WHERE d.profile_id = p_profile_id
            AND d.erased_at IS NULL;

          SELECT count(*) INTO queued_jobs
          FROM {S}.document_processing_jobs j
          WHERE j.profile_id = p_profile_id
            AND j.status IN ('queued', 'leased');

          IF p_additional_bytes > p_profile_max_bytes
             OR profile_bytes + p_additional_bytes > p_profile_max_bytes THEN
            RETURN pg_catalog.jsonb_build_object(
              'allowed', false,
              'code', 'profile_document_quota_exceeded',
              'profile_bytes', profile_bytes,
              'global_bytes', global_bytes,
              'profile_documents', profile_documents,
              'queued_jobs', queued_jobs
            );
          END IF;
          IF global_bytes + p_additional_bytes > p_global_max_bytes THEN
            RETURN pg_catalog.jsonb_build_object(
              'allowed', false,
              'code', 'global_document_quota_exceeded',
              'profile_bytes', profile_bytes,
              'global_bytes', global_bytes,
              'profile_documents', profile_documents,
              'queued_jobs', queued_jobs
            );
          END IF;
          IF profile_documents >= p_profile_max_documents THEN
            RETURN pg_catalog.jsonb_build_object(
              'allowed', false,
              'code', 'profile_document_count_exceeded',
              'profile_bytes', profile_bytes,
              'global_bytes', global_bytes,
              'profile_documents', profile_documents,
              'queued_jobs', queued_jobs
            );
          END IF;
          IF queued_jobs >= p_profile_max_queued_jobs THEN
            RETURN pg_catalog.jsonb_build_object(
              'allowed', false,
              'code', 'profile_document_queue_full',
              'profile_bytes', profile_bytes,
              'global_bytes', global_bytes,
              'profile_documents', profile_documents,
              'queued_jobs', queued_jobs
            );
          END IF;

          RETURN pg_catalog.jsonb_build_object(
            'allowed', true,
            'code', 'ok',
            'profile_bytes', profile_bytes,
            'global_bytes', global_bytes,
            'profile_documents', profile_documents,
            'queued_jobs', queued_jobs
          );
        END;
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {QUOTA_SIG} OWNER TO {DEFINER}")
    op.execute(f"ALTER FUNCTION {QUOTA_SIG} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {QUOTA_SIG} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {QUOTA_SIG} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def _create_renderer_functions() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_claim_render_job(
          p_worker_id text,
          p_lease_seconds integer,
          p_max_attempts integer
        )
        RETURNS TABLE (
          job_id uuid,
          document_id uuid,
          profile_id uuid,
          attempt integer,
          lease_expires_at timestamptz,
          source_storage_key text,
          detected_media_type text,
          encryption_format text,
          encryption_key_id text,
          input_sha256 text
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          selected_job_id uuid;
        BEGIN
          IF SESSION_USER <> '{RENDERER}' THEN
            RAISE EXCEPTION 'Renderer operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_worker_id IS NULL OR p_worker_id !~ '^[A-Za-z0-9._:-]{{1,128}}$'
             OR p_lease_seconds < 30 OR p_lease_seconds > 1800
             OR p_max_attempts < 1 OR p_max_attempts > 10 THEN
            RAISE EXCEPTION 'Invalid renderer claim policy' USING ERRCODE = 'HC422';
          END IF;

          WITH exhausted AS (
            UPDATE {S}.document_processing_jobs j
            SET status = 'failed',
                lease_owner = NULL,
                lease_expires_at = NULL,
                completed_at = pg_catalog.now(),
                updated_at = pg_catalog.now(),
                error_code = 'render_attempts_exhausted',
                next_attempt_at = NULL
            WHERE j.job_type = 'render'
              AND j.status = 'leased'
              AND j.lease_expires_at <= pg_catalog.now()
              AND j.attempt >= p_max_attempts
            RETURNING j.document_id, j.profile_id
          )
          UPDATE {S}.profile_documents d
          SET render_status = 'error',
              status = 'failed',
              failure_code = 'render_attempts_exhausted',
              updated_at = pg_catalog.now()
          FROM exhausted e
          WHERE d.id = e.document_id AND d.profile_id = e.profile_id;

          SELECT j.id INTO selected_job_id
          FROM {S}.document_processing_jobs j
          JOIN {S}.profile_documents d
            ON d.id = j.document_id AND d.profile_id = j.profile_id
          WHERE j.job_type = 'render'
            AND (
              (j.status = 'queued'
               AND (j.next_attempt_at IS NULL OR j.next_attempt_at <= pg_catalog.now()))
              OR (j.status = 'leased' AND j.lease_expires_at <= pg_catalog.now())
            )
            AND j.attempt < p_max_attempts
            AND d.status = 'quarantined'
            AND d.scanner_status = 'clean'
            AND d.render_status IN ('not_started', 'queued', 'rendering', 'error')
            AND d.current_storage_key IS NOT NULL
            AND d.storage_backend = 'local_encrypted'
            AND d.encryption_format = 'hcenc1'
            AND d.voided_at IS NULL
            AND d.erased_at IS NULL
          ORDER BY j.created_at, j.id
          FOR UPDATE OF j SKIP LOCKED
          LIMIT 1;

          IF selected_job_id IS NULL THEN
            RETURN;
          END IF;

          UPDATE {S}.document_processing_jobs j
          SET status = 'leased',
              attempt = j.attempt + 1,
              lease_owner = p_worker_id,
              lease_expires_at = pg_catalog.now()
                + pg_catalog.make_interval(secs => p_lease_seconds),
              started_at = coalesce(j.started_at, pg_catalog.now()),
              updated_at = pg_catalog.now(),
              error_code = NULL,
              next_attempt_at = NULL
          WHERE j.id = selected_job_id;

          UPDATE {S}.profile_documents d
          SET render_status = 'rendering', updated_at = pg_catalog.now()
          FROM {S}.document_processing_jobs j
          WHERE j.id = selected_job_id
            AND d.id = j.document_id
            AND d.profile_id = j.profile_id;

          RETURN QUERY
          SELECT j.id, j.document_id, j.profile_id, j.attempt,
                 j.lease_expires_at, d.current_storage_key::text,
                 d.detected_media_type::text, d.encryption_format::text,
                 d.encryption_key_id::text, j.input_sha256::text
          FROM {S}.document_processing_jobs j
          JOIN {S}.profile_documents d
            ON d.id = j.document_id AND d.profile_id = j.profile_id
          WHERE j.id = selected_job_id;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_heartbeat_render_job(
          p_job_id uuid,
          p_worker_id text,
          p_expected_lease_expires_at timestamptz,
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
          IF SESSION_USER <> '{RENDERER}' THEN
            RAISE EXCEPTION 'Renderer operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_lease_seconds < 30 OR p_lease_seconds > 1800 THEN
            RAISE EXCEPTION 'Invalid render lease duration' USING ERRCODE = 'HC422';
          END IF;
          UPDATE {S}.document_processing_jobs j
          SET lease_expires_at = pg_catalog.now()
                + pg_catalog.make_interval(secs => p_lease_seconds),
              updated_at = pg_catalog.now()
          WHERE j.id = p_job_id
            AND j.job_type = 'render'
            AND j.status = 'leased'
            AND j.lease_owner = p_worker_id
            AND j.lease_expires_at = p_expected_lease_expires_at
            AND j.lease_expires_at > pg_catalog.now()
          RETURNING j.lease_expires_at INTO new_lease;
          IF new_lease IS NULL THEN
            RAISE EXCEPTION 'Renderer lease conflict' USING ERRCODE = 'HC409';
          END IF;
          RETURN new_lease;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_complete_document_render(
          p_job_id uuid,
          p_worker_id text,
          p_expected_lease_expires_at timestamptz,
          p_run_id uuid,
          p_accepted_storage_key text,
          p_accepted_encrypted_size bigint,
          p_accepted_encryption_format text,
          p_accepted_encryption_key_id text,
          p_page_count integer,
          p_engine_name text,
          p_engine_version text,
          p_artifacts jsonb,
          p_audit_event_id uuid
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          target_document_id uuid;
          target_profile_id uuid;
          target_hash text;
          target_actor_id uuid;
          existing_run_id uuid;
          item jsonb;
          item_page integer;
          item_id uuid;
          item_key text;
          seen_pages integer[] := ARRAY[]::integer[];
        BEGIN
          IF SESSION_USER <> '{RENDERER}' THEN
            RAISE EXCEPTION 'Renderer operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_run_id IS NULL OR p_page_count < 1 OR p_page_count > 50
             OR p_accepted_encrypted_size < 1
             OR p_accepted_encryption_format <> 'hcenc1'
             OR p_accepted_encryption_key_id !~ '^[A-Za-z0-9._-]{{1,64}}$'
             OR p_engine_name IS NULL OR btrim(p_engine_name) = ''
             OR length(p_engine_name) > 64
             OR p_engine_version IS NULL OR btrim(p_engine_version) = ''
             OR length(p_engine_version) > 64
             OR pg_catalog.jsonb_typeof(p_artifacts) <> 'array'
             OR pg_catalog.jsonb_array_length(p_artifacts) <> p_page_count THEN
            RAISE EXCEPTION 'Invalid render result metadata' USING ERRCODE = 'HC422';
          END IF;

          SELECT d.render_run_id INTO existing_run_id
          FROM {S}.document_processing_jobs j
          JOIN {S}.profile_documents d
            ON d.id = j.document_id AND d.profile_id = j.profile_id
          WHERE j.id = p_job_id
            AND j.job_type = 'render'
            AND j.status = 'succeeded'
            AND d.render_status = 'ready';
          IF existing_run_id = p_run_id THEN
            RETURN true;
          ELSIF existing_run_id IS NOT NULL THEN
            RAISE EXCEPTION 'Render result conflict' USING ERRCODE = 'HC409';
          END IF;

          SELECT j.document_id, j.profile_id, j.input_sha256, d.uploaded_by_user_id
          INTO target_document_id, target_profile_id, target_hash, target_actor_id
          FROM {S}.document_processing_jobs j
          JOIN {S}.profile_documents d
            ON d.id = j.document_id AND d.profile_id = j.profile_id
          WHERE j.id = p_job_id
            AND j.job_type = 'render'
            AND j.status = 'leased'
            AND j.lease_owner = p_worker_id
            AND j.lease_expires_at = p_expected_lease_expires_at
            AND j.lease_expires_at > pg_catalog.now()
            AND d.status = 'quarantined'
            AND d.scanner_status = 'clean'
            AND d.sha256 = j.input_sha256
            AND d.voided_at IS NULL
            AND d.erased_at IS NULL
          FOR UPDATE OF j, d;
          IF target_document_id IS NULL THEN
            RAISE EXCEPTION 'Renderer lease conflict' USING ERRCODE = 'HC409';
          END IF;

          IF p_accepted_storage_key <> pg_catalog.format(
               'accepted/%s/original.hcenc', target_document_id
             ) THEN
            RAISE EXCEPTION 'Invalid accepted storage key' USING ERRCODE = 'HC422';
          END IF;

          FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_artifacts)
          LOOP
            BEGIN
              item_id := (item ->> 'id')::uuid;
              item_page := (item ->> 'page_number')::integer;
              item_key := item ->> 'storage_key';
            EXCEPTION WHEN others THEN
              RAISE EXCEPTION 'Invalid render artifact metadata' USING ERRCODE = 'HC422';
            END;
            IF item_id IS NULL
               OR item_page < 1 OR item_page > p_page_count
               OR item_page = ANY(seen_pages)
               OR item_key <> pg_catalog.format(
                    'derived/%s/%s/page-%s.png.hcenc',
                    target_document_id, p_run_id, item_page
                  )
               OR item ->> 'media_type' <> 'image/png'
               OR (item ->> 'byte_size')::bigint < 1
               OR (item ->> 'encrypted_size')::bigint < 1
               OR item ->> 'sha256' !~ '^[0-9a-f]{{64}}$'
               OR item ->> 'encryption_format' <> 'hcenc1'
               OR item ->> 'encryption_key_id' !~ '^[A-Za-z0-9._-]{{1,64}}$'
               OR (item ->> 'width')::integer < 1
               OR (item ->> 'height')::integer < 1 THEN
              RAISE EXCEPTION 'Invalid render artifact metadata' USING ERRCODE = 'HC422';
            END IF;
            seen_pages := pg_catalog.array_append(seen_pages, item_page);
          END LOOP;

          FOR item IN SELECT value FROM pg_catalog.jsonb_array_elements(p_artifacts)
          LOOP
            INSERT INTO {S}.document_artifacts (
              id, document_id, profile_id, run_id, artifact_type, page_number,
              status, storage_backend, storage_key, media_type, byte_size,
              encrypted_size, sha256, encryption_format, encryption_key_id,
              width, height
            ) VALUES (
              (item ->> 'id')::uuid, target_document_id, target_profile_id,
              p_run_id, 'safe_page', (item ->> 'page_number')::integer,
              'ready', 'local_encrypted', item ->> 'storage_key', 'image/png',
              (item ->> 'byte_size')::bigint,
              (item ->> 'encrypted_size')::bigint,
              item ->> 'sha256', item ->> 'encryption_format',
              item ->> 'encryption_key_id', (item ->> 'width')::integer,
              (item ->> 'height')::integer
            ) ON CONFLICT (document_id, run_id, artifact_type, page_number)
              DO NOTHING;
          END LOOP;

          UPDATE {S}.document_processing_jobs j
          SET status = 'succeeded', lease_owner = NULL, lease_expires_at = NULL,
              completed_at = pg_catalog.now(), updated_at = pg_catalog.now(),
              error_code = NULL, next_attempt_at = NULL,
              engine_name = p_engine_name, engine_version = p_engine_version
          WHERE j.id = p_job_id;

          UPDATE {S}.profile_documents d
          SET status = 'accepted', render_status = 'ready',
              render_run_id = p_run_id, render_engine = p_engine_name,
              render_version = p_engine_version,
              render_completed_at = pg_catalog.now(), page_count = p_page_count,
              current_storage_key = p_accepted_storage_key,
              accepted_storage_key = p_accepted_storage_key,
              encrypted_size = p_accepted_encrypted_size,
              encryption_format = p_accepted_encryption_format,
              encryption_key_id = p_accepted_encryption_key_id,
              failure_code = NULL, updated_at = pg_catalog.now()
          WHERE d.id = target_document_id AND d.profile_id = target_profile_id;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_profile_id, target_actor_id,
            'document', target_document_id, 'document.render_ready',
            '{{}}'::jsonb, 'document-renderer'
          );
          RETURN true;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_fail_render_job(
          p_job_id uuid,
          p_worker_id text,
          p_expected_lease_expires_at timestamptz,
          p_error_code text,
          p_retryable boolean,
          p_max_attempts integer,
          p_retry_after_seconds integer
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          target_document_id uuid;
          target_profile_id uuid;
          current_attempt integer;
          should_retry boolean;
        BEGIN
          IF SESSION_USER <> '{RENDERER}' THEN
            RAISE EXCEPTION 'Renderer operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_error_code IS NULL OR p_error_code !~ '^[a-z0-9_:-]{{1,64}}$'
             OR p_max_attempts < 1 OR p_max_attempts > 10
             OR p_retry_after_seconds < 0 OR p_retry_after_seconds > 86400 THEN
            RAISE EXCEPTION 'Invalid render failure policy' USING ERRCODE = 'HC422';
          END IF;

          SELECT j.document_id, j.profile_id, j.attempt
          INTO target_document_id, target_profile_id, current_attempt
          FROM {S}.document_processing_jobs j
          WHERE j.id = p_job_id AND j.job_type = 'render'
            AND j.status = 'leased' AND j.lease_owner = p_worker_id
            AND j.lease_expires_at = p_expected_lease_expires_at
            AND j.lease_expires_at > pg_catalog.now()
          FOR UPDATE;
          IF target_document_id IS NULL THEN
            RAISE EXCEPTION 'Renderer lease conflict' USING ERRCODE = 'HC409';
          END IF;

          should_retry := p_retryable AND current_attempt < p_max_attempts;
          UPDATE {S}.document_processing_jobs j
          SET status = CASE WHEN should_retry THEN 'queued' ELSE 'failed' END,
              lease_owner = NULL, lease_expires_at = NULL,
              completed_at = CASE WHEN should_retry THEN NULL ELSE pg_catalog.now() END,
              updated_at = pg_catalog.now(), error_code = p_error_code,
              next_attempt_at = CASE WHEN should_retry
                THEN pg_catalog.now() + pg_catalog.make_interval(secs => p_retry_after_seconds)
                ELSE NULL END
          WHERE j.id = p_job_id;

          UPDATE {S}.profile_documents d
          SET render_status = 'error',
              status = CASE WHEN should_retry THEN d.status ELSE 'failed' END,
              failure_code = p_error_code, updated_at = pg_catalog.now()
          WHERE d.id = target_document_id AND d.profile_id = target_profile_id;
          RETURN true;
        END;
        $$
        """
    )

    for signature in (
        CLAIM_RENDER_SIG,
        HEARTBEAT_RENDER_SIG,
        COMPLETE_RENDER_SIG,
        FAIL_RENDER_SIG,
    ):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO {DEFINER}")
        op.execute(f"ALTER FUNCTION {signature} SET row_security = off")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {APP}")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {RENDERER}")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def _create_reconciliation_functions() -> None:
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
          RETURN QUERY
          SELECT d.current_storage_key::text, d.id, d.profile_id, 'source'::text
          FROM {S}.profile_documents d
          WHERE d.erased_at IS NULL AND d.current_storage_key IS NOT NULL
          UNION ALL
          SELECT a.storage_key::text, a.document_id, a.profile_id,
                 ('safe_page:' || a.page_number::text)::text
          FROM {S}.document_artifacts a
          WHERE a.erased_at IS NULL
            AND a.status IN ('staged', 'ready', 'deletion_pending');
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
          target_document_id uuid;
          target_profile_id uuid;
          target_actor_id uuid;
        BEGIN
          IF SESSION_USER <> '{RECONCILER}' THEN
            RAISE EXCEPTION 'Reconciliation operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_storage_key IS NULL OR length(p_storage_key) > 512
             OR p_storage_key !~ '^(quarantine|accepted|derived)/[A-Za-z0-9._/-]+\\.hcenc$'
             OR p_error_code !~ '^[a-z0-9_:-]{{1,64}}$' THEN
            RAISE EXCEPTION 'Invalid reconciliation input' USING ERRCODE = 'HC422';
          END IF;

          SELECT d.id, d.profile_id, d.uploaded_by_user_id
          INTO target_document_id, target_profile_id, target_actor_id
          FROM {S}.profile_documents d
          WHERE d.current_storage_key = p_storage_key AND d.erased_at IS NULL
          FOR UPDATE;

          IF target_document_id IS NULL THEN
            SELECT a.document_id, a.profile_id, d.uploaded_by_user_id
            INTO target_document_id, target_profile_id, target_actor_id
            FROM {S}.document_artifacts a
            JOIN {S}.profile_documents d
              ON d.id = a.document_id AND d.profile_id = a.profile_id
            WHERE a.storage_key = p_storage_key AND a.erased_at IS NULL
            FOR UPDATE OF a, d;
            IF target_document_id IS NOT NULL THEN
              UPDATE {S}.document_artifacts
              SET status = 'deletion_pending',
                  deletion_requested_at = coalesce(deletion_requested_at, pg_catalog.now()),
                  updated_at = pg_catalog.now()
              WHERE storage_key = p_storage_key;
            END IF;
          END IF;

          IF target_document_id IS NULL THEN
            RETURN false;
          END IF;

          UPDATE {S}.profile_documents
          SET status = 'failed', render_status = 'error',
              failure_code = p_error_code, updated_at = pg_catalog.now()
          WHERE id = target_document_id AND profile_id = target_profile_id;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_profile_id, target_actor_id,
            'document', target_document_id, 'document.storage_missing',
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
    _require_role(RENDERER)
    _require_role(RECONCILER)

    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "ADD COLUMN current_storage_key varchar(512) NULL, "
        "ADD COLUMN render_status varchar(32) NOT NULL DEFAULT 'not_started', "
        "ADD COLUMN render_run_id uuid NULL, "
        "ADD COLUMN render_engine varchar(64) NULL, "
        "ADD COLUMN render_version varchar(64) NULL, "
        "ADD COLUMN render_completed_at timestamptz NULL"
    )
    op.execute(
        f"UPDATE {S}.profile_documents "
        "SET current_storage_key = coalesce(accepted_storage_key, quarantine_storage_key)"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "ALTER COLUMN current_storage_key SET NOT NULL, "
        "ADD CONSTRAINT uq_profile_documents_current_storage_key "
        "UNIQUE (current_storage_key), "
        "ADD CONSTRAINT ck_profile_documents_render_status CHECK ("
        "render_status IN ('not_started','queued','rendering','ready','error')), "
        "ADD CONSTRAINT ck_profile_documents_render_metadata CHECK ("
        "render_status <> 'ready' OR ("
        "render_run_id IS NOT NULL AND render_engine IS NOT NULL "
        "AND render_version IS NOT NULL AND render_completed_at IS NOT NULL "
        "AND page_count IS NOT NULL AND accepted_storage_key IS NOT NULL "
        "AND current_storage_key = accepted_storage_key))"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.document_artifacts (
          id uuid PRIMARY KEY,
          document_id uuid NOT NULL,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          run_id uuid NOT NULL,
          artifact_type varchar(32) NOT NULL,
          page_number integer NOT NULL,
          status varchar(32) NOT NULL,
          storage_backend varchar(32) NOT NULL,
          storage_key varchar(512) NOT NULL,
          media_type varchar(128) NOT NULL,
          byte_size bigint NOT NULL,
          encrypted_size bigint NOT NULL,
          sha256 varchar(64) NOT NULL,
          encryption_format varchar(32) NOT NULL,
          encryption_key_id varchar(64) NOT NULL,
          width integer NOT NULL,
          height integer NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          deletion_requested_at timestamptz NULL,
          erased_at timestamptz NULL,
          CONSTRAINT fk_document_artifacts_document_profile
            FOREIGN KEY (document_id, profile_id)
            REFERENCES {S}.profile_documents(id, profile_id) ON DELETE CASCADE,
          CONSTRAINT uq_document_artifacts_page
            UNIQUE (document_id, run_id, artifact_type, page_number),
          CONSTRAINT uq_document_artifacts_storage_key UNIQUE (storage_key),
          CONSTRAINT ck_document_artifacts_type CHECK (artifact_type = 'safe_page'),
          CONSTRAINT ck_document_artifacts_page CHECK (page_number BETWEEN 1 AND 50),
          CONSTRAINT ck_document_artifacts_status CHECK (
            status IN ('staged','ready','deletion_pending','erased')
          ),
          CONSTRAINT ck_document_artifacts_storage CHECK (
            storage_backend = 'local_encrypted'
            AND storage_key ~ '^derived/[0-9a-f-]{{36}}/[0-9a-f-]{{36}}/page-[1-9][0-9]*\\.png\\.hcenc$'
            AND media_type = 'image/png'
          ),
          CONSTRAINT ck_document_artifacts_size CHECK (
            byte_size > 0 AND encrypted_size > byte_size
          ),
          CONSTRAINT ck_document_artifacts_hash CHECK (sha256 ~ '^[0-9a-f]{{64}}$'),
          CONSTRAINT ck_document_artifacts_encryption CHECK (
            encryption_format = 'hcenc1'
            AND encryption_key_id ~ '^[A-Za-z0-9._-]{{1,64}}$'
          ),
          CONSTRAINT ck_document_artifacts_dimensions CHECK (
            width > 0 AND height > 0 AND width::bigint * height::bigint <= 25000000
          ),
          CONSTRAINT ck_document_artifacts_erasure CHECK (
            erased_at IS NULL OR deletion_requested_at IS NOT NULL
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_document_artifacts_document_run "
        f"ON {S}.document_artifacts (document_id, run_id, page_number)"
    )
    op.execute(f"ALTER TABLE {S}.document_artifacts ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.document_artifacts FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY document_artifacts_select ON {S}.document_artifacts "
        f"FOR SELECT USING ({S}.app_can_view_document(profile_id))"
    )
    op.execute(f"GRANT SELECT ON {S}.document_artifacts TO {APP}")
    op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {S}.document_artifacts FROM {APP}")

    _replace_audit_constraint(include_c2_actions=True)

    op.execute(f"GRANT UPDATE ON {S}.profile_documents TO {DEFINER}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON {S}.document_processing_jobs TO {DEFINER}"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {S}.document_artifacts TO {DEFINER}")
    op.execute(f"GRANT USAGE ON SCHEMA {S} TO {RENDERER}")
    op.execute(f"GRANT USAGE ON SCHEMA {S} TO {RECONCILER}")

    _create_quota_function()
    _create_renderer_functions()
    _create_reconciliation_functions()


def downgrade() -> None:
    for signature, role in (
        (MARK_MISSING_SIG, RECONCILER),
        (LIST_REFS_SIG, RECONCILER),
        (FAIL_RENDER_SIG, RENDERER),
        (COMPLETE_RENDER_SIG, RENDERER),
        (HEARTBEAT_RENDER_SIG, RENDERER),
        (CLAIM_RENDER_SIG, RENDERER),
        (QUOTA_SIG, APP),
    ):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {role}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")

    op.execute(f"REVOKE USAGE ON SCHEMA {S} FROM {RENDERER}")
    op.execute(f"REVOKE USAGE ON SCHEMA {S} FROM {RECONCILER}")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE ON {S}.document_artifacts FROM {DEFINER}")
    op.execute(f"REVOKE SELECT ON {S}.document_artifacts FROM {APP}")

    _replace_audit_constraint(include_c2_actions=False)

    op.execute(
        f"DROP POLICY IF EXISTS document_artifacts_select ON {S}.document_artifacts"
    )
    op.execute(f"DROP TABLE {S}.document_artifacts")

    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "DROP CONSTRAINT ck_profile_documents_render_metadata, "
        "DROP CONSTRAINT ck_profile_documents_render_status, "
        "DROP CONSTRAINT uq_profile_documents_current_storage_key, "
        "DROP COLUMN render_completed_at, "
        "DROP COLUMN render_version, "
        "DROP COLUMN render_engine, "
        "DROP COLUMN render_run_id, "
        "DROP COLUMN render_status, "
        "DROP COLUMN current_storage_key"
    )
