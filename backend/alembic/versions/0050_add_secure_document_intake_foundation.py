"""Add HC-017 secure document intake foundation.

Revision ID: 0050
Revises: 0049

This slice stores only document metadata and durable intake jobs. Uploaded bytes
remain in a private quarantine storage adapter; OCR candidates and lab facts are
introduced by later slices.
"""

from __future__ import annotations

from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"
ACTIVITY_SIG = f"{S}.app_duplicate_user_activity(uuid)"
PRE_DOCUMENT_ACTIVITY_SIG = f"{S}.app_duplicate_user_activity_pre_documents(uuid)"
DOCUMENT_VIEW_SIG = f"{S}.app_can_view_document(uuid)"

AUDIT_ACTIONS_0049 = """
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
            'clinical_record.erased'
"""


def _replace_audit_constraint(*, include_document_upload: bool) -> None:
    actions = AUDIT_ACTIONS_0049
    if include_document_upload:
        actions = f"{actions.rstrip()},\n            'document.uploaded'\n"
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


def _create_document_view_function() -> None:
    # Raw-document metadata is intentionally narrower than normal profile read
    # access: analyze may use confirmed structured observations in later slices,
    # but cannot see source-document metadata or OCR drafts.
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_can_view_document(target_profile_id uuid)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
          SELECT EXISTS (
            SELECT 1
            FROM {S}.health_profiles hp
            WHERE hp.id = target_profile_id
              AND hp.owner_user_id = {S}.app_current_user_id()
          ) OR EXISTS (
            SELECT 1
            FROM {S}.profile_permissions pp
            WHERE pp.profile_id = target_profile_id
              AND pp.user_id = {S}.app_current_user_id()
              AND pp.permission IN ('owner', 'edit', 'view')
          )
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {DOCUMENT_VIEW_SIG} OWNER TO {R}")
    op.execute(f"ALTER FUNCTION {DOCUMENT_VIEW_SIG} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {DOCUMENT_VIEW_SIG} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {DOCUMENT_VIEW_SIG} TO {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def _install_document_activity_wrapper() -> None:
    # Preserve the tested HC-015 implementation under a private internal name
    # and add the new table without copying its large body into this migration.
    op.execute(
        f"ALTER FUNCTION {ACTIVITY_SIG} "
        "RENAME TO app_duplicate_user_activity_pre_documents"
    )
    op.execute(f"GRANT SELECT ON {S}.profile_documents TO {R}")
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")
    op.execute(
        f"""
        CREATE FUNCTION {S}.app_duplicate_user_activity(target_user_id uuid)
        RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        SET row_security = off
        AS $$
        DECLARE
          base_activity jsonb;
          document_count integer;
          meaningful_count integer;
          is_empty boolean;
        BEGIN
          base_activity := {S}.app_duplicate_user_activity_pre_documents(target_user_id);

          SELECT count(*) INTO document_count
          FROM {S}.profile_documents pd
          LEFT JOIN {S}.health_profiles hp ON hp.id = pd.profile_id
          WHERE hp.owner_user_id = target_user_id
             OR pd.uploaded_by_user_id = target_user_id
             OR pd.voided_by_user_id = target_user_id;

          meaningful_count :=
            coalesce((base_activity ->> 'meaningful_count')::integer, 0)
            + document_count;
          is_empty :=
            coalesce((base_activity ->> 'is_empty')::boolean, false)
            AND document_count = 0;

          RETURN base_activity || jsonb_build_object(
            'profile_documents', document_count,
            'meaningful_count', meaningful_count,
            'is_empty', is_empty
          );
        END;
        $$
        """
    )
    op.execute(f"ALTER FUNCTION {ACTIVITY_SIG} OWNER TO {R}")
    op.execute(f"ALTER FUNCTION {ACTIVITY_SIG} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {ACTIVITY_SIG} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {ACTIVITY_SIG} FROM {APP}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")


def _restore_previous_activity_function() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {ACTIVITY_SIG}")
    op.execute(
        f"ALTER FUNCTION {PRE_DOCUMENT_ACTIVITY_SIG} "
        "RENAME TO app_duplicate_user_activity"
    )
    op.execute(f"REVOKE SELECT ON {S}.profile_documents FROM {R}")


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {S}.profile_documents (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          uploaded_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          status varchar(32) NOT NULL,
          original_filename varchar(255) NOT NULL,
          declared_media_type varchar(128) NOT NULL,
          detected_media_type varchar(128) NOT NULL,
          byte_size bigint NOT NULL,
          sha256 varchar(64) NOT NULL,
          storage_backend varchar(32) NOT NULL,
          quarantine_storage_key varchar(512) NOT NULL,
          accepted_storage_key varchar(512) NULL,
          page_count integer NULL,
          failure_code varchar(64) NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          voided_at timestamptz NULL,
          voided_by_user_id uuid NULL REFERENCES {S}.users(id),
          void_reason varchar(500) NULL,
          deletion_requested_at timestamptz NULL,
          erased_at timestamptz NULL,
          CONSTRAINT ck_profile_documents_status CHECK (
            status IN (
              'uploading', 'quarantined', 'scanning', 'accepted',
              'ocr_queued', 'processing', 'review_required', 'confirmed',
              'rejected', 'failed', 'voided', 'deletion_pending', 'erased'
            )
          ),
          CONSTRAINT ck_profile_documents_filename CHECK (
            btrim(original_filename) <> ''
          ),
          CONSTRAINT ck_profile_documents_media_type CHECK (
            declared_media_type IN ('application/pdf', 'image/jpeg', 'image/png')
            AND detected_media_type IN ('application/pdf', 'image/jpeg', 'image/png')
            AND declared_media_type = detected_media_type
          ),
          CONSTRAINT ck_profile_documents_size CHECK (
            byte_size > 0 AND byte_size <= 20971520
          ),
          CONSTRAINT ck_profile_documents_sha256 CHECK (
            sha256 ~ '^[0-9a-f]{{64}}$'
          ),
          CONSTRAINT ck_profile_documents_storage CHECK (
            btrim(storage_backend) <> ''
            AND btrim(quarantine_storage_key) <> ''
          ),
          CONSTRAINT ck_profile_documents_page_count CHECK (
            page_count IS NULL OR page_count BETWEEN 1 AND 50
          ),
          CONSTRAINT ck_profile_documents_void CHECK (
            (voided_at IS NULL AND voided_by_user_id IS NULL AND void_reason IS NULL)
            OR
            (voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL
             AND void_reason IS NOT NULL AND btrim(void_reason) <> '')
          ),
          CONSTRAINT ck_profile_documents_erasure_timestamps CHECK (
            erased_at IS NULL OR deletion_requested_at IS NOT NULL
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_profile_documents_profile_status_time "
        f"ON {S}.profile_documents (profile_id, status, created_at DESC)"
    )
    op.execute(
        f"CREATE INDEX ix_profile_documents_profile_sha "
        f"ON {S}.profile_documents (profile_id, sha256)"
    )

    op.execute(
        f"""
        CREATE TABLE {S}.document_processing_jobs (
          id uuid PRIMARY KEY,
          document_id uuid NOT NULL REFERENCES {S}.profile_documents(id) ON DELETE CASCADE,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          job_type varchar(32) NOT NULL,
          status varchar(32) NOT NULL,
          attempt integer NOT NULL DEFAULT 0,
          idempotency_key varchar(255) NOT NULL,
          input_sha256 varchar(64) NOT NULL,
          engine_name varchar(64) NULL,
          engine_version varchar(64) NULL,
          lease_owner varchar(128) NULL,
          lease_expires_at timestamptz NULL,
          started_at timestamptz NULL,
          completed_at timestamptz NULL,
          error_code varchar(64) NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_document_processing_jobs_idempotency UNIQUE (idempotency_key),
          CONSTRAINT ck_document_processing_jobs_type CHECK (
            job_type IN ('inspect', 'scan', 'render', 'ocr')
          ),
          CONSTRAINT ck_document_processing_jobs_status CHECK (
            status IN ('queued', 'leased', 'succeeded', 'failed', 'cancelled')
          ),
          CONSTRAINT ck_document_processing_jobs_attempt CHECK (attempt >= 0),
          CONSTRAINT ck_document_processing_jobs_sha256 CHECK (
            input_sha256 ~ '^[0-9a-f]{{64}}$'
          ),
          CONSTRAINT ck_document_processing_jobs_lease CHECK (
            (status <> 'leased' AND lease_owner IS NULL AND lease_expires_at IS NULL)
            OR
            (status = 'leased' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_document_processing_jobs_status_time "
        f"ON {S}.document_processing_jobs (status, created_at)"
    )
    op.execute(
        f"CREATE INDEX ix_document_processing_jobs_document "
        f"ON {S}.document_processing_jobs (document_id, created_at DESC)"
    )

    for table in ("profile_documents", "document_processing_jobs"):
        op.execute(f"ALTER TABLE {S}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {S}.{table} FORCE ROW LEVEL SECURITY")

    _create_document_view_function()
    op.execute(
        f"CREATE POLICY profile_documents_select ON {S}.profile_documents "
        f"FOR SELECT USING ({S}.app_can_view_document(profile_id))"
    )
    op.execute(
        f"CREATE POLICY profile_documents_insert ON {S}.profile_documents "
        f"FOR INSERT WITH CHECK ("
        f"uploaded_by_user_id = {S}.app_current_user_id() "
        f"AND {S}.app_can_edit_profile(profile_id))"
    )
    op.execute(
        f"CREATE POLICY document_processing_jobs_select ON {S}.document_processing_jobs "
        f"FOR SELECT USING ({S}.app_can_view_document(profile_id))"
    )
    op.execute(
        f"CREATE POLICY document_processing_jobs_insert ON {S}.document_processing_jobs "
        f"FOR INSERT WITH CHECK ({S}.app_can_edit_profile(profile_id))"
    )

    op.execute(f"GRANT SELECT, INSERT ON {S}.profile_documents TO {APP}")
    op.execute(f"GRANT SELECT, INSERT ON {S}.document_processing_jobs TO {APP}")
    op.execute(f"REVOKE UPDATE, DELETE ON {S}.profile_documents FROM {APP}")
    op.execute(f"REVOKE UPDATE, DELETE ON {S}.document_processing_jobs FROM {APP}")

    _replace_audit_constraint(include_document_upload=True)
    _install_document_activity_wrapper()


def downgrade() -> None:
    _restore_previous_activity_function()
    _replace_audit_constraint(include_document_upload=False)

    op.execute(f"REVOKE SELECT, INSERT ON {S}.document_processing_jobs FROM {APP}")
    op.execute(f"REVOKE SELECT, INSERT ON {S}.profile_documents FROM {APP}")

    op.execute(
        f"DROP POLICY IF EXISTS document_processing_jobs_insert "
        f"ON {S}.document_processing_jobs"
    )
    op.execute(
        f"DROP POLICY IF EXISTS document_processing_jobs_select "
        f"ON {S}.document_processing_jobs"
    )
    op.execute(
        f"DROP POLICY IF EXISTS profile_documents_insert ON {S}.profile_documents"
    )
    op.execute(
        f"DROP POLICY IF EXISTS profile_documents_select ON {S}.profile_documents"
    )

    op.execute(f"REVOKE EXECUTE ON FUNCTION {DOCUMENT_VIEW_SIG} FROM {APP}")
    op.execute(f"DROP FUNCTION IF EXISTS {DOCUMENT_VIEW_SIG}")
    op.execute(f"DROP TABLE {S}.document_processing_jobs")
    op.execute(f"DROP TABLE {S}.profile_documents")
