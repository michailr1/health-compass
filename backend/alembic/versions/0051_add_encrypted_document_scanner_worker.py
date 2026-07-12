"""Add HC-017 Slice C1 encrypted storage and scanner worker boundary.

Revision ID: 0051
Revises: 0050

The migration does not enable production document upload. It extends document
metadata for authenticated encryption and malware-scan results, and exposes a
narrow SECURITY DEFINER job API to a separately provisioned NOBYPASSRLS worker.
"""

from __future__ import annotations

from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"
WORKER = "health_compass_worker"

CLAIM_SIG = f"{S}.app_claim_document_job(text, integer, integer)"
HEARTBEAT_SIG = (
    f"{S}.app_heartbeat_document_job(uuid, text, timestamp with time zone, integer)"
)
COMPLETE_SIG = (
    f"{S}.app_complete_document_scan("
    "uuid, text, timestamp with time zone, text, text, text, "
    "timestamp with time zone, text, uuid, text, uuid)"
)
FAIL_SIG = (
    f"{S}.app_fail_document_job("
    "uuid, text, timestamp with time zone, text, boolean, integer, integer)"
)

AUDIT_ACTIONS_0050 = """
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
            'document.uploaded'
"""


def _replace_audit_constraint(*, include_scan_actions: bool) -> None:
    actions = AUDIT_ACTIONS_0050
    if include_scan_actions:
        actions = (
            f"{actions.rstrip()},\n"
            "            'document.scan_clean',\n"
            "            'document.scan_rejected'\n"
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


def _require_worker_role() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
          worker_role record;
        BEGIN
          SELECT * INTO worker_role
          FROM pg_roles
          WHERE rolname = '{WORKER}';

          IF worker_role IS NULL THEN
            RAISE EXCEPTION
              'Provision first: CREATE ROLE {WORKER} LOGIN NOBYPASSRLS NOSUPERUSER '
              'NOCREATEDB NOCREATEROLE NOREPLICATION';
          END IF;

          IF NOT worker_role.rolcanlogin
             OR worker_role.rolbypassrls
             OR worker_role.rolsuper
             OR worker_role.rolcreatedb
             OR worker_role.rolcreaterole
             OR worker_role.rolreplication THEN
            RAISE EXCEPTION
              'Role {WORKER} must be LOGIN NOBYPASSRLS NOSUPERUSER '
              'NOCREATEDB NOCREATEROLE NOREPLICATION';
          END IF;
        END $$;
        """
    )


def _create_worker_functions() -> None:
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_claim_document_job(
          p_worker_id text,
          p_lease_seconds integer,
          p_max_attempts integer
        )
        RETURNS TABLE (
          job_id uuid,
          document_id uuid,
          profile_id uuid,
          job_type text,
          attempt integer,
          lease_expires_at timestamptz,
          storage_backend text,
          storage_key text,
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
          IF SESSION_USER <> '{WORKER}' THEN
            RAISE EXCEPTION 'Worker operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_worker_id IS NULL OR p_worker_id !~ '^[A-Za-z0-9._:-]{{1,128}}$' THEN
            RAISE EXCEPTION 'Invalid worker id' USING ERRCODE = 'HC422';
          END IF;
          IF p_lease_seconds < 30 OR p_lease_seconds > 1800 THEN
            RAISE EXCEPTION 'Invalid lease duration' USING ERRCODE = 'HC422';
          END IF;
          IF p_max_attempts < 1 OR p_max_attempts > 10 THEN
            RAISE EXCEPTION 'Invalid max attempts' USING ERRCODE = 'HC422';
          END IF;

          WITH exhausted AS (
            UPDATE {S}.document_processing_jobs j
            SET status = 'failed',
                lease_owner = NULL,
                lease_expires_at = NULL,
                completed_at = pg_catalog.now(),
                updated_at = pg_catalog.now(),
                error_code = 'worker_attempts_exhausted',
                next_attempt_at = NULL
            WHERE j.status = 'leased'
              AND j.lease_expires_at <= pg_catalog.now()
              AND j.attempt >= p_max_attempts
            RETURNING j.document_id, j.profile_id
          )
          UPDATE {S}.profile_documents d
          SET scanner_status = 'error',
              status = 'failed',
              failure_code = 'worker_attempts_exhausted',
              updated_at = pg_catalog.now()
          FROM exhausted e
          WHERE d.id = e.document_id
            AND d.profile_id = e.profile_id
            AND d.status = 'quarantined';

          SELECT j.id INTO selected_job_id
          FROM {S}.document_processing_jobs j
          JOIN {S}.profile_documents d
            ON d.id = j.document_id AND d.profile_id = j.profile_id
          WHERE j.job_type IN ('inspect', 'scan')
            AND (
              (
                j.status = 'queued'
                AND (j.next_attempt_at IS NULL OR j.next_attempt_at <= pg_catalog.now())
              )
              OR (
                j.status = 'leased'
                AND j.lease_expires_at <= pg_catalog.now()
              )
            )
            AND j.attempt < p_max_attempts
            AND d.status = 'quarantined'
            AND d.scanner_status IN ('not_scanned', 'scanning', 'error', 'stale')
            AND d.voided_at IS NULL
            AND d.erased_at IS NULL
            AND d.storage_backend = 'local_encrypted'
            AND d.encryption_format = 'hcenc1'
            AND d.encryption_key_id IS NOT NULL
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
          SET scanner_status = 'scanning',
              updated_at = pg_catalog.now()
          FROM {S}.document_processing_jobs j
          WHERE j.id = selected_job_id
            AND d.id = j.document_id
            AND d.profile_id = j.profile_id;

          RETURN QUERY
          SELECT
            j.id,
            j.document_id,
            j.profile_id,
            j.job_type::text,
            j.attempt,
            j.lease_expires_at,
            d.storage_backend::text,
            d.quarantine_storage_key::text,
            d.encryption_format::text,
            d.encryption_key_id::text,
            j.input_sha256::text
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
        CREATE FUNCTION {S}.app_heartbeat_document_job(
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
          IF SESSION_USER <> '{WORKER}' THEN
            RAISE EXCEPTION 'Worker operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_lease_seconds < 30 OR p_lease_seconds > 1800 THEN
            RAISE EXCEPTION 'Invalid lease duration' USING ERRCODE = 'HC422';
          END IF;

          UPDATE {S}.document_processing_jobs j
          SET lease_expires_at = pg_catalog.now()
                + pg_catalog.make_interval(secs => p_lease_seconds),
              updated_at = pg_catalog.now()
          WHERE j.id = p_job_id
            AND j.status = 'leased'
            AND j.lease_owner = p_worker_id
            AND j.lease_expires_at = p_expected_lease_expires_at
            AND j.lease_expires_at > pg_catalog.now()
          RETURNING j.lease_expires_at INTO new_lease;

          IF new_lease IS NULL THEN
            RAISE EXCEPTION 'Worker lease conflict' USING ERRCODE = 'HC409';
          END IF;
          RETURN new_lease;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_complete_document_scan(
          p_job_id uuid,
          p_worker_id text,
          p_expected_lease_expires_at timestamptz,
          p_scanner_engine text,
          p_scanner_version text,
          p_signature_version text,
          p_signature_timestamp timestamptz,
          p_scan_result text,
          p_render_job_id uuid,
          p_render_idempotency_key text,
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
          audit_action text;
          existing_status text;
        BEGIN
          IF SESSION_USER <> '{WORKER}' THEN
            RAISE EXCEPTION 'Worker operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_scan_result NOT IN ('clean', 'infected') THEN
            RAISE EXCEPTION 'Invalid scanner result' USING ERRCODE = 'HC422';
          END IF;
          IF p_scanner_engine IS NULL OR btrim(p_scanner_engine) = ''
             OR length(p_scanner_engine) > 64
             OR p_scanner_version IS NULL OR btrim(p_scanner_version) = ''
             OR length(p_scanner_version) > 64
             OR p_signature_version IS NULL OR btrim(p_signature_version) = ''
             OR length(p_signature_version) > 128
             OR p_signature_timestamp IS NULL
             OR p_signature_timestamp > pg_catalog.now() + interval '1 hour' THEN
            RAISE EXCEPTION 'Invalid scanner metadata' USING ERRCODE = 'HC422';
          END IF;
          IF p_scan_result = 'clean'
             AND (p_render_job_id IS NULL
                  OR p_render_idempotency_key IS NULL
                  OR btrim(p_render_idempotency_key) = ''
                  OR length(p_render_idempotency_key) > 255) THEN
            RAISE EXCEPTION 'Invalid render job metadata' USING ERRCODE = 'HC422';
          END IF;

          SELECT d.scanner_status
          INTO existing_status
          FROM {S}.document_processing_jobs j
          JOIN {S}.profile_documents d
            ON d.id = j.document_id AND d.profile_id = j.profile_id
          WHERE j.id = p_job_id
            AND j.status = 'succeeded';

          IF existing_status = p_scan_result THEN
            RETURN true;
          ELSIF existing_status IS NOT NULL THEN
            RAISE EXCEPTION 'Document scan result conflict' USING ERRCODE = 'HC409';
          END IF;

          SELECT j.document_id, j.profile_id, j.input_sha256
          INTO target_document_id, target_profile_id, target_hash
          FROM {S}.document_processing_jobs j
          WHERE j.id = p_job_id
            AND j.status = 'leased'
            AND j.lease_owner = p_worker_id
            AND j.lease_expires_at = p_expected_lease_expires_at
            AND j.lease_expires_at > pg_catalog.now()
          FOR UPDATE;

          IF target_document_id IS NULL THEN
            RAISE EXCEPTION 'Worker lease conflict' USING ERRCODE = 'HC409';
          END IF;

          SELECT d.uploaded_by_user_id
          INTO target_actor_id
          FROM {S}.profile_documents d
          WHERE d.id = target_document_id
            AND d.profile_id = target_profile_id
            AND d.sha256 = target_hash
            AND d.status = 'quarantined'
            AND d.voided_at IS NULL
            AND d.erased_at IS NULL
          FOR UPDATE;

          IF target_actor_id IS NULL THEN
            RAISE EXCEPTION 'Document state conflict' USING ERRCODE = 'HC409';
          END IF;

          UPDATE {S}.document_processing_jobs j
          SET status = 'succeeded',
              lease_owner = NULL,
              lease_expires_at = NULL,
              completed_at = pg_catalog.now(),
              updated_at = pg_catalog.now(),
              error_code = NULL,
              next_attempt_at = NULL
          WHERE j.id = p_job_id;

          UPDATE {S}.profile_documents d
          SET scanner_status = p_scan_result,
              scanner_engine = p_scanner_engine,
              scanner_version = p_scanner_version,
              scanner_signature_version = p_signature_version,
              scanner_signature_timestamp = p_signature_timestamp,
              scanner_completed_at = pg_catalog.now(),
              status = CASE
                WHEN p_scan_result = 'infected' THEN 'rejected'
                ELSE d.status
              END,
              failure_code = CASE
                WHEN p_scan_result = 'infected' THEN 'malware_detected'
                ELSE NULL
              END,
              deletion_requested_at = CASE
                WHEN p_scan_result = 'infected'
                THEN coalesce(d.deletion_requested_at, pg_catalog.now())
                ELSE d.deletion_requested_at
              END,
              updated_at = pg_catalog.now()
          WHERE d.id = target_document_id
            AND d.profile_id = target_profile_id;

          IF p_scan_result = 'clean' THEN
            INSERT INTO {S}.document_processing_jobs (
              id, document_id, profile_id, job_type, status, attempt,
              idempotency_key, input_sha256
            ) VALUES (
              p_render_job_id, target_document_id, target_profile_id,
              'render', 'queued', 0, p_render_idempotency_key, target_hash
            )
            ON CONFLICT (idempotency_key) DO NOTHING;
            audit_action := 'document.scan_clean';
          ELSE
            audit_action := 'document.scan_rejected';
          END IF;

          INSERT INTO {S}.profile_audit_events (
            id, profile_id, actor_user_id, entity_type, entity_id,
            action, changed_fields, request_id
          ) VALUES (
            p_audit_event_id, target_profile_id, target_actor_id,
            'document', target_document_id,
            audit_action, '{{}}'::jsonb, 'document-worker'
          );

          RETURN true;
        END;
        $$
        """
    )

    op.execute(
        f"""
        CREATE FUNCTION {S}.app_fail_document_job(
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
          current_status text;
          current_error text;
          should_retry boolean;
        BEGIN
          IF SESSION_USER <> '{WORKER}' THEN
            RAISE EXCEPTION 'Worker operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_error_code IS NULL
             OR p_error_code !~ '^[a-z0-9_:-]{{1,64}}$' THEN
            RAISE EXCEPTION 'Invalid worker error code' USING ERRCODE = 'HC422';
          END IF;
          IF p_max_attempts < 1 OR p_max_attempts > 10
             OR p_retry_after_seconds < 0 OR p_retry_after_seconds > 86400 THEN
            RAISE EXCEPTION 'Invalid retry policy' USING ERRCODE = 'HC422';
          END IF;

          SELECT j.status, j.error_code
          INTO current_status, current_error
          FROM {S}.document_processing_jobs j
          WHERE j.id = p_job_id;

          IF current_status IN ('queued', 'failed') AND current_error = p_error_code THEN
            RETURN true;
          END IF;

          SELECT j.document_id, j.profile_id, j.attempt
          INTO target_document_id, target_profile_id, current_attempt
          FROM {S}.document_processing_jobs j
          WHERE j.id = p_job_id
            AND j.status = 'leased'
            AND j.lease_owner = p_worker_id
            AND j.lease_expires_at = p_expected_lease_expires_at
            AND j.lease_expires_at > pg_catalog.now()
          FOR UPDATE;

          IF target_document_id IS NULL THEN
            RAISE EXCEPTION 'Worker lease conflict' USING ERRCODE = 'HC409';
          END IF;

          should_retry := p_retryable AND current_attempt < p_max_attempts;

          UPDATE {S}.document_processing_jobs j
          SET status = CASE WHEN should_retry THEN 'queued' ELSE 'failed' END,
              lease_owner = NULL,
              lease_expires_at = NULL,
              completed_at = CASE
                WHEN should_retry THEN NULL ELSE pg_catalog.now()
              END,
              updated_at = pg_catalog.now(),
              error_code = p_error_code,
              next_attempt_at = CASE
                WHEN should_retry
                THEN pg_catalog.now()
                  + pg_catalog.make_interval(secs => p_retry_after_seconds)
                ELSE NULL
              END
          WHERE j.id = p_job_id;

          UPDATE {S}.profile_documents d
          SET scanner_status = CASE
                WHEN p_error_code = 'scanner_signatures_stale' THEN 'stale'
                ELSE 'error'
              END,
              status = CASE WHEN should_retry THEN d.status ELSE 'failed' END,
              failure_code = p_error_code,
              deletion_requested_at = CASE
                WHEN NOT should_retry
                     AND p_error_code IN (
                       'encrypted_object_invalid',
                       'unsupported_storage_format'
                     )
                THEN coalesce(d.deletion_requested_at, pg_catalog.now())
                ELSE d.deletion_requested_at
              END,
              updated_at = pg_catalog.now()
          WHERE d.id = target_document_id
            AND d.profile_id = target_profile_id
            AND d.status = 'quarantined';

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
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {WORKER}")

    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def upgrade() -> None:
    _require_worker_role()

    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "ADD COLUMN encrypted_size bigint NULL, "
        "ADD COLUMN encryption_format varchar(32) NULL, "
        "ADD COLUMN encryption_key_id varchar(64) NULL, "
        "ADD COLUMN scanner_status varchar(32) NOT NULL DEFAULT 'not_scanned', "
        "ADD COLUMN scanner_engine varchar(64) NULL, "
        "ADD COLUMN scanner_version varchar(64) NULL, "
        "ADD COLUMN scanner_signature_version varchar(128) NULL, "
        "ADD COLUMN scanner_signature_timestamp timestamptz NULL, "
        "ADD COLUMN scanner_completed_at timestamptz NULL"
    )
    op.execute(
        f"""
        ALTER TABLE {S}.profile_documents
        ADD CONSTRAINT ck_profile_documents_encryption CHECK (
          (
            storage_backend = 'local_encrypted'
            AND encrypted_size IS NOT NULL AND encrypted_size > byte_size
            AND encryption_format = 'hcenc1'
            AND encryption_key_id ~ '^[A-Za-z0-9._-]{{1,64}}$'
          ) OR (
            storage_backend <> 'local_encrypted'
            AND encrypted_size IS NULL
            AND encryption_format IS NULL
            AND encryption_key_id IS NULL
          )
        ),
        ADD CONSTRAINT ck_profile_documents_scanner_status CHECK (
          scanner_status IN (
            'not_scanned', 'scanning', 'clean', 'infected', 'error', 'stale'
          )
        ),
        ADD CONSTRAINT ck_profile_documents_scanner_metadata CHECK (
          scanner_status NOT IN ('clean', 'infected')
          OR (
            scanner_engine IS NOT NULL
            AND scanner_version IS NOT NULL
            AND scanner_signature_version IS NOT NULL
            AND scanner_signature_timestamp IS NOT NULL
            AND scanner_completed_at IS NOT NULL
          )
        )
        """
    )

    op.execute(
        f"ALTER TABLE {S}.document_processing_jobs "
        "ADD COLUMN next_attempt_at timestamptz NULL"
    )
    op.execute(
        f"CREATE INDEX ix_document_processing_jobs_claim "
        f"ON {S}.document_processing_jobs "
        "(job_type, status, next_attempt_at, created_at)"
    )

    _replace_audit_constraint(include_scan_actions=True)

    op.execute(f"GRANT UPDATE ON {S}.profile_documents TO {DEFINER}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON {S}.document_processing_jobs TO {DEFINER}"
    )
    op.execute(f"GRANT USAGE ON SCHEMA {S} TO {WORKER}")

    _create_worker_functions()


def downgrade() -> None:
    for signature in (FAIL_SIG, COMPLETE_SIG, HEARTBEAT_SIG, CLAIM_SIG):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {WORKER}")
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")

    op.execute(f"REVOKE UPDATE ON {S}.profile_documents FROM {DEFINER}")
    op.execute(
        f"REVOKE SELECT, INSERT, UPDATE ON {S}.document_processing_jobs FROM {DEFINER}"
    )
    op.execute(f"REVOKE USAGE ON SCHEMA {S} FROM {WORKER}")

    _replace_audit_constraint(include_scan_actions=False)

    op.execute(f"DROP INDEX IF EXISTS {S}.ix_document_processing_jobs_claim")
    op.execute(
        f"ALTER TABLE {S}.document_processing_jobs DROP COLUMN next_attempt_at"
    )

    op.execute(
        f"ALTER TABLE {S}.profile_documents "
        "DROP CONSTRAINT ck_profile_documents_scanner_metadata, "
        "DROP CONSTRAINT ck_profile_documents_scanner_status, "
        "DROP CONSTRAINT ck_profile_documents_encryption, "
        "DROP COLUMN scanner_completed_at, "
        "DROP COLUMN scanner_signature_timestamp, "
        "DROP COLUMN scanner_signature_version, "
        "DROP COLUMN scanner_version, "
        "DROP COLUMN scanner_engine, "
        "DROP COLUMN scanner_status, "
        "DROP COLUMN encryption_key_id, "
        "DROP COLUMN encryption_format, "
        "DROP COLUMN encrypted_size"
    )
