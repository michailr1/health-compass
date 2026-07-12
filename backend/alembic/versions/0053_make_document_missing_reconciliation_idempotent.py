"""Make HC-017 missing-object reconciliation idempotent.

Revision ID: 0053
Revises: 0052

Repeated inventory passes over the same missing source or artifact must not emit
unbounded duplicate audit events.
"""

from __future__ import annotations

from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
DEFINER = "health_compass_rls_definer"
WORKER = "health_compass_worker"
RENDERER = "health_compass_renderer"
RECONCILER = "health_compass_reconciler"
SIGNATURE = f"{S}.app_mark_document_object_missing(text,text,uuid)"


def _install(*, idempotent: bool) -> None:
    early_source = """
          IF target_document_id IS NOT NULL AND already_marked THEN
            RETURN true;
          END IF;
    """ if idempotent else ""
    early_artifact = """
            IF target_document_id IS NOT NULL AND already_marked THEN
              RETURN true;
            END IF;
    """ if idempotent else ""
    source_projection = (
        ", (d.status = 'failed' AND d.failure_code = p_error_code)"
        if idempotent
        else ""
    )
    source_into = ", already_marked" if idempotent else ""
    artifact_projection = (
        ", (a.status = 'deletion_pending' AND d.status = 'failed' "
        "AND d.failure_code = p_error_code)"
        if idempotent
        else ""
    )
    artifact_into = ", already_marked" if idempotent else ""
    declaration = "          already_marked boolean := false;\n" if idempotent else ""

    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {DEFINER}")
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_mark_document_object_missing(
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
{declaration}        BEGIN
          IF SESSION_USER <> '{RECONCILER}' THEN
            RAISE EXCEPTION 'Reconciliation operation denied' USING ERRCODE = 'HC404';
          END IF;
          IF p_storage_key IS NULL OR length(p_storage_key) > 512
             OR p_storage_key !~ '^(quarantine|accepted|derived)/[A-Za-z0-9._/-]+\\.hcenc$'
             OR p_error_code !~ '^[a-z0-9_:-]{{1,64}}$' THEN
            RAISE EXCEPTION 'Invalid reconciliation input' USING ERRCODE = 'HC422';
          END IF;

          SELECT d.id, d.profile_id, d.uploaded_by_user_id{source_projection}
          INTO target_document_id, target_profile_id, target_actor_id{source_into}
          FROM {S}.profile_documents d
          WHERE d.current_storage_key = p_storage_key AND d.erased_at IS NULL
          FOR UPDATE;
{early_source}
          IF target_document_id IS NULL THEN
            SELECT a.document_id, a.profile_id, d.uploaded_by_user_id{artifact_projection}
            INTO target_document_id, target_profile_id, target_actor_id{artifact_into}
            FROM {S}.document_artifacts a
            JOIN {S}.profile_documents d
              ON d.id = a.document_id AND d.profile_id = a.profile_id
            WHERE a.storage_key = p_storage_key AND a.erased_at IS NULL
            FOR UPDATE OF a, d;
{early_artifact}
            IF target_document_id IS NOT NULL THEN
              UPDATE {S}.document_artifacts
              SET status = 'deletion_pending',
                  deletion_requested_at = coalesce(
                    deletion_requested_at,
                    pg_catalog.now()
                  ),
                  updated_at = pg_catalog.now()
              WHERE storage_key = p_storage_key;
            END IF;
          END IF;

          IF target_document_id IS NULL THEN
            RETURN false;
          END IF;

          UPDATE {S}.profile_documents
          SET status = 'failed',
              render_status = 'error',
              failure_code = p_error_code,
              updated_at = pg_catalog.now()
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
    op.execute(f"ALTER FUNCTION {SIGNATURE} OWNER TO {DEFINER}")
    op.execute(f"ALTER FUNCTION {SIGNATURE} SET row_security = off")
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    for role in (APP, WORKER, RENDERER):
        op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM {role}")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO {RECONCILER}")
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {DEFINER}")


def upgrade() -> None:
    _install(idempotent=True)


def downgrade() -> None:
    _install(idempotent=False)
