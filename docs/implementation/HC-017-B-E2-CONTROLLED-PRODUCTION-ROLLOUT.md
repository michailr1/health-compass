# HC-017 B–E2 — controlled production rollout

Status: `PHASE 1 DEPLOYED / AUTOMATED SMOKE VERIFIED / MANUALLY ACCEPTED`  
Target environment: `https://health.funti.cc`  
Target host: `funti.cc` / `172.245.108.154`  
Repository: `/opt/health-compass/repo`

## 1. Result

HC-017 B–E2 Phase 1 was deployed to the existing production host and manually accepted by the owner.

```text
application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
alembic: 0058 (single head)
backend: health-compass-api.service / active
frontend: /opt/health-compass/releases/hc017-erasure-20260712T223445Z-fb1e7a2f
DOCUMENT_UPLOAD_ENABLED=false
worker services: not created and not running
```

The deployment installed the application code, frontend routes, schema and restricted PostgreSQL interfaces through E2. It did not enable the document-processing product capability.

Canonical evidence:

```text
docs/changes/2026-07-13-hc-017-phase1-production-deployed.md
docs/changes/2026-07-13-hc-017-phase1-manually-accepted.md
```

## 2. Responsibility boundary

The VPS agent:

- connected only to `funti.cc` (`172.245.108.154`);
- deployed an exact GitHub SHA;
- did not write or edit product code;
- did not create or edit migrations;
- did not commit, push, merge, open PRs or change GitHub state;
- did not print secrets, `.env` contents, database URLs, encryption keys or OAuth/SMTP credentials;
- stopped on the first preflight failure and resumed only after a reviewed GitHub fix.

GitHub documentation and code changes remained the responsibility of the main development agent.

## 3. Phase 1 scope

Phase 1 deployed:

- application code through HC-017 E2;
- Alembic migrations `0050` through `0058`;
- frontend routes and UI through E2;
- document/OCR/Labs schema and restricted database functions;
- fail-safe production configuration.

Mandatory setting remains:

```text
DOCUMENT_UPLOAD_ENABLED=false
```

Phase 1 did not:

- enable document upload;
- provision encryption credentials;
- start scanner, renderer, reconciler or OCR workers;
- accept ClamAV, Poppler, ImageMagick or Tesseract as production services;
- create production document storage or spool directories;
- perform upload → scan → render → OCR → review → Lab confirmation testing;
- change OAuth, SMTP, DNS or Apache routing.

## 4. Preflight memfd incident

The first preflight stopped before migration because the self-contained CPython 3.12.13 runtime was compiled with:

```text
HAVE_MEMFD_CREATE=0
```

The host itself supported the required primitive:

```text
kernel: 5.4.0-216-generic
libc memfd_create: available
kernel memfd and sealing capability probe: passed
```

PR #68 added a centralized fail-closed compatibility layer that:

- preserves native CPython wrappers when present;
- otherwise calls libc `memfd_create` for the same Linux kernel primitive;
- restores only missing Linux UAPI constants;
- keeps file sealing mandatory;
- never falls back to disk-backed plaintext files;
- leaves every existing rendering/OCR test enabled.

```text
PR: #68
verified head: 4984088d5e9e5d1412d9a071480cf7dabe408c71
merge: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
CI: #500 / success
```

The repeated production preflight passed on the actual self-contained Python runtime.

## 5. Backup and migration evidence

Verified backup:

```text
path: /opt/health-compass/backups/hc017-pre-migrate-20260712T223356Z.dump
size: 265335 bytes
sha256: 0ef5ace5fabeaa45db35b2d5b66430e1e160e140f096af710cdc07c5254b797d
format: PostgreSQL CUSTOM
pg_restore --list: 341 entries / success
```

Migration result:

```text
before: 0049
repository heads: 0058 (single head)
after: 0058 (head)
```

Automatic downgrade was not used.

## 6. PostgreSQL role boundary

Provisioned worker roles:

```text
health_compass_worker
health_compass_renderer
health_compass_reconciler
health_compass_ocr_worker
```

Each role is:

```text
LOGIN
NOBYPASSRLS
NOSUPERUSER
NOCREATEDB
NOCREATEROLE
NOREPLICATION
VALID UNTIL '1970-01-01'
```

Verified:

- `health_compass_rls_definer` is `NOLOGIN BYPASSRLS`;
- `health_compass_migrator` is a member of the definer role;
- `health_compass_app` is `NOBYPASSRLS`;
- worker roles have no direct table grants;
- restricted worker functions exist;
- PUBLIC execute is revoked from worker functions;
- the application role has no execute permission on scanner/renderer/reconciler/OCR claim functions.

The following review functions are intentionally application functions, not worker claim functions:

```text
app_can_review_document_ocr
app_finalize_document_ocr_review
app_review_document_ocr_candidate
app_set_document_ocr_patient_decision
```

## 7. Build and test evidence

Backend:

```text
compileall: success
Ruff: success
pytest: 191 passed, 14 skipped, 0 failed
```

Frontend:

```text
npm ci: success
lint: 0 errors, 27 pre-existing warnings
typecheck: success
tests: 55 passed, 0 failed
build: 2496 modules, success
```

The eight tests that failed in the first memfd preflight passed after PR #68. The new compatibility regression tests also passed.

## 8. Release and HTTP evidence

Serving path:

```text
/opt/health-compass/current-subdomain
```

Transition:

```text
before: /opt/health-compass/releases/hc016-erasure-20260712T051208Z
after:  /opt/health-compass/releases/hc017-erasure-20260712T223445Z-fb1e7a2f
bundle before: assets/index-DwM_RbXx.js
bundle after:  assets/index-WPvMNLMb.js
```

Verified:

```text
local /health: 200
public /api/health: 200
new JS asset: 200
new CSS asset: 200
/ : 200
/login : 200
/api/auth/provider/google : 307 to accounts.google.com
/app : 200 SPA
/app/documents : 200 SPA
/app/lab-drafts : 200 SPA
```

Google redirect retained:

```text
redirect_uri=https://health.funti.cc/api/auth/callback
prompt=select_account
```

Fresh rollout logs contained zero occurrences of:

```text
Traceback
ERROR
CRITICAL
54001
42501
permission denied
HTTP 5xx
```

## 9. Owner manual smoke

The owner confirmed that the deployed UI opens correctly and the new document/Lab routes do not break the existing product.

Accepted browser scope:

- authenticated application shell;
- dashboard/profile access;
- Clinical Context access;
- HC-016 permanent-erasure UI access;
- `/app/documents` navigation and direct refresh;
- `/app/lab-drafts` navigation and direct refresh;
- disabled document state does not break navigation.

Acceptance state:

```text
SERVER ROLLOUT: ACCEPTED
AUTOMATED SMOKE: PASSED
SECURITY CHECKS: PASSED
MANUAL UI SMOKE: PASSED
PHASE 1: MANUALLY ACCEPTED
FULL DOCUMENT/OCR PIPELINE: DISABLED / NOT ACCEPTED
```

UX findings from the manual review are tracked separately as HC-019:

```text
docs/implementation/HC-019-NAVIGATION-AND-EMPTY-STATE-UX.md
```

## 10. Phase 2 boundary

Full HC-017 B–E2 end-to-end owner testing requires a separate Phase 2:

- production encryption-key provisioning and recovery/rotation procedure;
- private encrypted storage and isolated spool directories;
- dedicated OS users and hardened systemd units;
- ClamAV/FreshClam installation and healthy signatures;
- verified Poppler, ImageMagick, Tesseract and `rus+eng` traineddata;
- reverse-proxy body limit;
- measured quotas and free-space reserve;
- hostile-file/resource probes;
- database plus encrypted-object backup/restore test;
- no-sensitive-log validation under the running pipeline;
- reviewed code/config change permitting controlled production enablement;
- explicit owner approval to set `DOCUMENT_UPLOAD_ENABLED=true`.

Until then, production upload remains disabled by configuration and application validation.

## 11. Rollback evidence retained

Previous frontend release and verified database backup remain available. No previous releases were deleted during rollout.

Any future rollback after schema `0058` must not use an automatic Alembic downgrade. Backend compatibility with `0058` must be proven before code rollback, or the verified backup must be restored only by explicit owner decision.
