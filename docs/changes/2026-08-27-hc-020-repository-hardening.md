# HC-020 — Repository hygiene and database hardening

Status: CODE VALIDATED · NOT MERGED · NOT DEPLOYED

Date: 2026-08-27
Base: `main@a9634a2f84933e57e465517f991094629ec131c2`
PR: `#75`

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
- downgrade restores the three tables, exact bootstrap secondary-index names,
  application CRUD grants and the historical magic-link search path;
- PostgreSQL regression coverage verifies legacy-surface absence plus function
  owner/EXECUTE/search-path invariants;
- migration-boundary coverage verifies `0063 → 0062 → 0063`;
- a destructive-stop regression inserts unexpected legacy data, proves `0063`
  fails while revision/data remain at `0062`, then proves upgrade succeeds only
  after the unexpected row is removed.

## Code-validation evidence

Validated code head: `4d1436413b20d7afc82bd7b17d7b8b64cd705ada`
GitHub Actions: CI run `33090961386` / run number `574`

All required jobs passed on that exact code head:

- Backend lint and unit tests — success;
- Frontend lint, typecheck, tests and build — success;
- PostgreSQL migration and RLS cycle — success;
  - migration boundary tests — success;
  - full `head → base → head` migration cycle — success;
  - PostgreSQL integration and RLS tests — success.

The evidence update itself is documentation-only and therefore creates a new
PR head. Final exact-PR-head CI is recorded in the PR acceptance evidence after
this document commit, without another repository commit, so the evidence trail
does not recursively invalidate its own SHA.

## Acceptance invariants

- one Alembic head: `0063`;
- downgrade restores the real `0062` legacy boundary;
- migration refuses silent data loss on non-empty legacy tables;
- magic-link function owner remains `health_compass_rls_definer`;
- application EXECUTE remains granted and PUBLIC EXECUTE remains revoked;
- no production/config/document-upload/worker change is part of this branch;
- final exact-PR-head CI must be green before draft is removed.

## Production boundary

This branch does not deploy anything, does not change production configuration,
does not enable document upload, and does not start document workers. Applying
`0063` belongs to a separate owner-approved rollout with backup-first evidence.
