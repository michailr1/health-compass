# HC-020 — Repository hygiene and database hardening

Status: IMPLEMENTED IN BRANCH · NOT MERGED · NOT DEPLOYED

Date: 2026-08-27
Base: `main@a9634a2f84933e57e465517f991094629ec131c2`

## Reason

Independent revision REV-01/REV-02 identified two dormant security surfaces:
three bootstrap technical tables with direct application CRUD and no RLS, and
two bootstrap-era magic-link `SECURITY DEFINER` functions with a non-empty
`search_path`.

## Implemented

- Alembic `0063` removes `service_metadata`, `audit_events`, `processing_jobs`;
- upgrade refuses to drop them if any contains data;
- drops use no `CASCADE`;
- dead SQLAlchemy models and Alembic registry imports are removed;
- `app_issue_email_login_token` and `app_consume_email_login_token` are changed
  to `search_path=''` without recreating the functions;
- downgrade restores the three tables, indexes, application CRUD grants and
  the historical magic-link search path;
- PostgreSQL regression coverage verifies legacy-surface absence plus function
  owner/EXECUTE/search-path invariants;
- migration-boundary coverage verifies `0063 → 0062 → 0063`.

## Acceptance

Required before marking the PR ready:

- one Alembic head (`0063`);
- backend Ruff/unit suite green;
- PostgreSQL migration/RLS suite green;
- full migration cycle green;
- exact-head GitHub Actions run recorded here;
- self-review confirms no production/config/document-upload change.

## Production boundary

This branch does not deploy anything, does not change production configuration,
does not enable document upload, and does not start document workers. Applying
`0063` belongs to a separate owner-approved rollout with backup-first evidence.
