# 2026-07-13 — HC-017 B–E2 Phase 1 deployed to production

Status: `DEPLOYED / AUTOMATED SMOKE VERIFIED / MANUAL UI SMOKE PENDING`.

## Exact production state

```text
host: funti.cc
ip: 172.245.108.154
application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
alembic: 0058 (single head)
DOCUMENT_UPLOAD_ENABLED=false
workers: not created as services and not running
```

## Rollout transition

```text
application before: 80c7ec3f60ff6d74e2db15a8c6363c82d8cac4d8
application after:  fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
alembic before: 0049
alembic after:  0058
frontend before: /opt/health-compass/releases/hc016-erasure-20260712T051208Z
frontend after:  /opt/health-compass/releases/hc017-erasure-20260712T223445Z-fb1e7a2f
bundle before: assets/index-DwM_RbXx.js
bundle after:  assets/index-WPvMNLMb.js
```

## Verified backup

```text
path: /opt/health-compass/backups/hc017-pre-migrate-20260712T223356Z.dump
size: 265335 bytes
sha256: 0ef5ace5fabeaa45db35b2d5b66430e1e160e140f096af710cdc07c5254b797d
format: PostgreSQL CUSTOM
pg_restore --list: 341 entries / success
```

## Runtime compatibility incident resolved

The first preflight stopped before migration because the self-contained CPython 3.12.13 runtime had been built with `HAVE_MEMFD_CREATE=0` and omitted the Python `os.memfd_create` and `fcntl` sealing wrappers.

The host kernel, libc memfd call and file sealing were independently proven functional. PR #68 added a fail-closed compatibility layer using the same libc/kernel primitive, with no filesystem plaintext fallback and no skipped rendering/OCR security tests.

```text
PR: #68
verified head: 4984088d5e9e5d1412d9a071480cf7dabe408c71
merge: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
CI: #500 / success
```

## Build and test evidence

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

All eight memfd-dependent rendering/OCR tests that failed during the first preflight passed after the compatibility fix. The three new compatibility regression tests also passed.

## PostgreSQL security evidence

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

Confirmed:

- `health_compass_rls_definer` remains `NOLOGIN BYPASSRLS`;
- `health_compass_migrator` remains a member of the definer role;
- `health_compass_app` remains `NOBYPASSRLS`;
- worker roles have no direct table grants;
- restricted worker functions exist;
- PUBLIC execute is revoked from restricted worker functions;
- the application role has no execute permission on worker claim functions.

Review functions intentionally callable by the application role are not worker claim functions:

```text
app_can_review_document_ocr
app_finalize_document_ocr_review
app_review_document_ocr_candidate
app_set_document_ocr_patient_decision
```

## Service and HTTP evidence

```text
backend unit: health-compass-api.service
backend state: active
local /health: 200
public /api/health: 200
production JS asset: 200
production CSS asset: 200
```

Smoke results:

```text
/                             200
/login                        200
/api/health                   200
/api/auth/provider/google     307 to accounts.google.com
/app                          200 SPA
/app/documents                200 SPA
/app/lab-drafts               200 SPA
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

## Operational boundary

Phase 1 deployed the code, schema, frontend routes and restricted PostgreSQL interfaces through HC-017 E2. It did not enable the document processing product capability.

Still disabled/not provisioned:

- document upload;
- encryption production credentials and recovery/rotation;
- private document storage and bounded spools;
- scanner, renderer, reconciler and OCR systemd services;
- ClamAV/FreshClam;
- production Poppler/ImageMagick/Tesseract toolchain verification;
- hostile-file and resource-exhaustion probes;
- document/object backup and restore validation;
- disposable upload → scan → render → OCR → review → Lab confirmation smoke.

## Acceptance boundary

```text
SERVER ROLLOUT: ACCEPTED
AUTOMATED SMOKE: PASSED
SECURITY CHECKS: PASSED
MANUAL UI SMOKE: PENDING
FULL DOCUMENT/OCR PIPELINE: DISABLED / NOT ACCEPTED
```

Required owner browser checks:

- Google login and logout;
- Email Magic Link login;
- profile/dashboard loading;
- Clinical Context regression;
- HC-016 permanent deletion;
- `/app/documents` and Lab route navigation/direct refresh;
- clear disabled-upload state.

No production code or GitHub changes were performed by the VPS deployment agent.
