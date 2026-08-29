# HC-021 — controlled E3 production rollout

Status: `RUNBOOK READY / NOT EXECUTED / OWNER APPROVAL REQUIRED`  
Target environment: `https://health.funti.cc`  
Production host: `funti.cc` / `172.245.108.154`  
Repository: `/opt/health-compass/repo`

## 1. Purpose

HC-021 moves the already merged HC-017 E3 application/schema from the current production baseline to Alembic `0062` without enabling document intake.

Current verified production baseline:

```text
application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
alembic: 0058
backend: health-compass-api.service / active
DOCUMENT_UPLOAD_ENABLED=false
scanner/renderer/reconciler/OCR services: not created and not running
```

Repository E3 baseline:

```text
application baseline: c7dcae4da3860f6f73224f639be78424c6f3fa63
alembic head: 0062
migrations: 0059 -> 0060 -> 0061 -> 0062
```

This document is a narrow delta runbook. `docs/DEPLOYMENT-RUNBOOK.md` remains canonical for host verification, build, backup, release, smoke, security and reporting mechanics.

## 2. Non-goals and hard locks

HC-021 does not authorize:

- `DOCUMENT_UPLOAD_ENABLED=true`;
- creation/start of scanner, renderer, reconciler or OCR workers;
- production encryption/storage provisioning;
- changes to Apache, DNS, OAuth or SMTP;
- migration `0063` or HC-020 changes while PR #75 is unmerged;
- automatic Alembic downgrade;
- production deployment by the development agent.

The VPS agent only executes this runbook after the owner supplies an exact approved `TARGET_SHA`.

## 3. Target SHA acceptance

Before touching production, prove all of the following:

1. `TARGET_SHA` is exact, immutable and reachable from `origin/main`.
2. The checkout is clean and exactly equals `TARGET_SHA`.
3. `TARGET_SHA` contains HC-017 E3 application baseline `c7dcae4da3860f6f73224f639be78424c6f3fa63` or a reviewed descendant.
4. Repository Alembic has exactly one head and that head is exactly `0062`.
5. `TARGET_SHA` does not contain migration `0063` unless a separate owner-approved rollout supersedes HC-021.
6. CI for the application baseline covering E3 is green; local production-host preflight tests below must also pass.

If any item differs, stop without production changes.

## 4. Mandatory preflight

Follow `docs/DEPLOYMENT-RUNBOOK.md` and record evidence for:

```text
hostname/IP/repository verification
clean git tree
HEAD_BEFORE
backend unit/status
frontend current-subdomain target
production Alembic current
repository Alembic heads
DOCUMENT_UPLOAD_ENABLED=false (value only; never print env file)
worker service absence/inactive state
```

Expected database boundary before migration:

```text
production current: 0058
repository heads: 0062
```

If production is not exactly `0058`, stop for architecture review rather than improvising a migration path.

Run exact-target validation before release:

```text
backend compileall
Ruff
pytest
frontend npm ci
frontend lint
typecheck
frontend tests
frontend production build
```

No failed test may be waived by the VPS agent.

## 5. Backup gate

Immediately before migration, create a fresh PostgreSQL custom-format backup using the existing production mechanism.

Record:

```text
backup path
byte size
sha256
pg_restore --list result and entry count
```

The backup gate passes only when:

- dump command succeeded;
- file is non-empty;
- `pg_restore --list` succeeds;
- checksum is recorded.

Do not use the July HC-017 backup as the rollback source for this release. It is evidence only. HC-021 requires a new backup representing the exact database immediately before `0058 -> 0062`.

## 6. Migration semantics that affect rollback

### 0059

Adds the immutable Lab observation lifecycle, correction/void/erasure functions and document-linked Lab erasure. Its downgrade is intentionally fail-closed and refuses `0059 -> 0058` if E3 lifecycle data exists, including non-active/corrected observations, correction links, voided observations, or a document with pending erasure.

### 0060

Adds an independent document-availability guard to Lab reads. Its downgrade restores the 0059 policies and removes the helper function.

### 0061

Hardens correction acknowledgement and erasure concurrency. Its partial downgrade intentionally retains the strengthened same-signature chain-erasure function instead of weakening concurrency safety.

### 0062

Extends the closed audit action vocabulary required by hardened E3 functions. Its downgrade intentionally keeps that additive vocabulary at `0061`.

Operational consequence: `0062 -> 0058` is not a symmetric release rollback and must never be treated as one.

## 7. Release sequence

Only after all preflight and backup gates pass:

1. Fetch and checkout exact approved `TARGET_SHA`.
2. Reconfirm clean tree and exact SHA.
3. Reconfirm `DOCUMENT_UPLOAD_ENABLED=false` without printing secrets.
4. Reconfirm scanner/renderer/reconciler/OCR services are not running.
5. Run Alembic `current` and `heads` through the production migrator environment.
6. Require `current=0058` and `heads=0062`.
7. Run `alembic upgrade head`.
8. Require `alembic current=0062` and a single head.
9. Restart only the existing backend unit.
10. Require local backend health `200`.
11. Build/release frontend using the immutable release-directory and atomic `current-subdomain` switch from the canonical runbook.
12. Run Apache config test/reload only as required by the canonical frontend switch; do not alter Apache configuration.
13. Verify the production HTML references the new bundle and that referenced assets return `200`.
14. Execute automated smoke/security checks below.
15. Owner performs the authenticated browser smoke.

## 8. Automated smoke after 0062

Baseline smoke from `docs/DEPLOYMENT-RUNBOOK.md` remains mandatory.

HC-021 additionally requires:

```text
/api/health -> 200
/app/labs direct refresh -> SPA / no 404
/app/documents direct refresh -> SPA / no 404
/app/lab-drafts direct refresh -> SPA / no 404
DOCUMENT_UPLOAD_ENABLED=false
no scanner/renderer/reconciler/OCR runtime started
Alembic current=0062, one head
```

For an existing authenticated test account/profile with safe test data, exercise E3 API/UI only where it does not require the disabled document pipeline:

- Lab observation history endpoint loads without 5xx;
- owner/edit/view privacy boundaries remain enforced;
- cross-user Lab read remains denied;
- permanent-erasure controls are owner-only;
- correction/void endpoints reject invalid/stale preconditions with controlled 4xx rather than 5xx.

Do not manufacture medical values in production merely to prove E3. If no suitable existing test observation exists, report the mutation-path smoke as `NOT EXERCISED — NO SAFE TEST DATA`, not as passed.

## 9. PostgreSQL security regression

After migration verify, without outputting sensitive row contents:

- `health_compass_app` remains `NOBYPASSRLS`;
- worker roles remain `NOBYPASSRLS` and retain no broad direct table mutation grants;
- `health_compass_rls_definer` remains `NOLOGIN BYPASSRLS`;
- E3 SECURITY DEFINER functions are owned by the expected definer;
- PUBLIC execute remains revoked from restricted E3 functions;
- application execution is limited to intended application interfaces;
- Lab read policies hide data linked to pending/erased documents;
- no unexpected `42501`, `54001`, deadlock, traceback or HTTP 5xx appears in fresh logs;
- logs contain no tokens, raw documents/OCR text, medical values, encryption keys or database URLs.

Any cross-user visibility is a release-blocking security incident: stop normal traffic/enter maintenance as appropriate and follow the rollback decision tree.

## 10. Rollback decision tree

### A. Failure before database migration

No schema change occurred. Revert code/frontend using the canonical runbook and report the failed gate.

### B. Migration failed transactionally and Alembic remains 0058

Do not retry blindly. Capture sanitized error, confirm application/database health, restore previous application/frontend if needed, and stop for development review.

### C. Database reached 0062, but application/frontend release failed

Do not automatically run `alembic downgrade`.

Preferred order:

1. Keep `DOCUMENT_UPLOAD_ENABLED=false`.
2. Prevent E3 mutation traffic if compatibility is uncertain.
3. Fix-forward the application at schema `0062` when possible.
4. Roll back frontend independently if necessary.
5. Roll back backend code only if compatibility of the previous backend with schema `0062` has been explicitly proven for the incident.
6. If database rollback is required, owner chooses restore of the fresh verified HC-021 backup.

### D. E3 writes may have occurred after migration

Never attempt automatic `0062 -> 0058`. Migration `0059` can intentionally refuse downgrade once lifecycle or pending-erasure state exists.

If restoration is chosen by the owner:

- stop/freeze application writes first;
- preserve incident evidence and current database backup if operationally safe;
- restore only the fresh verified HC-021 pre-migration backup using the existing production restore procedure;
- restore previous compatible backend/frontend release;
- verify Alembic `0058`, health, auth isolation and logs before reopening normal traffic.

A database restore discards post-backup writes. That consequence requires explicit owner approval.

## 11. Stop conditions

The VPS agent stops without improvisation if any of these occur:

- wrong host/IP/repository;
- dirty production checkout;
- target SHA not approved/reachable from `origin/main`;
- production Alembic not exactly `0058` before migration;
- repository head not exactly `0062`;
- fresh backup cannot be verified;
- preflight tests fail;
- document upload is enabled;
- unexpected document workers are active;
- migration result is not exactly `0062` single-head;
- local/public health fails;
- cross-user data becomes visible;
- restricted function/RLS privilege regression appears;
- unexpected 5xx/traceback/database permission errors appear.

## 12. Owner browser acceptance

After automated gates are green, the owner verifies in production:

- login/session still works;
- normal dashboard/profile navigation works;
- `/app/labs` opens and refreshes directly;
- existing Lab data, if present, renders correctly;
- lifecycle/history UI does not expose another profile/user;
- owner-only permanent-erasure affordance is not exposed to non-owner context;
- documents remain disabled and no upload CTA unexpectedly opens a production intake path.

No document/OCR end-to-end acceptance belongs to HC-021.

## 13. Required execution report

Hermes returns facts only; it does not update GitHub.

```text
HC021_ROLLOUT_OK=true|false
reason=<short reason>

target_sha=<exact SHA>
head_before=<SHA>
head_after=<SHA>
working_tree_clean=true|false

alembic_before=0058
alembic_heads=0062
alembic_after=0062
single_head=true|false

backup_path=<path>
backup_size=<bytes>
backup_sha256=<sha256>
backup_pg_restore_list=<success/failure + count>

backend_unit=health-compass-api.service
backend_active=true|false
local_health=200|<status>
public_health=200|<status>

frontend_before=<release path>
frontend_after=<release path>
production_bundle_before=<asset>
production_bundle_after=<asset>
production_assets_ok=true|false

document_upload_enabled=false
scanner_worker_running=false
renderer_worker_running=false
reconciler_worker_running=false
ocr_worker_running=false

baseline_smoke_ok=true|false
hc021_route_smoke_ok=true|false
hc021_mutation_smoke=passed|not_exercised_no_safe_test_data|failed
security_regression_ok=true|false
cross_user_leak=false|true
sanitized_logs_ok=true|false
secrets_printed=false

owner_browser_smoke=pending|accepted|rejected
production_changes_outside_runbook=false
```

## 14. Completion boundary

HC-021 is complete only when:

1. owner explicitly authorizes the exact production rollout;
2. Hermes executes this runbook on the verified production host;
3. server evidence is green at `0062`;
4. owner browser smoke is accepted;
5. the development agent records exact production evidence and updates canonical current state.

Until then the correct status remains:

```text
HC-017 E3: IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED
PRODUCTION: 0058
DOCUMENT UPLOAD: DISABLED
```
