# Health Compass — текущее состояние

Дата: 2026-07-13  
Основная ветка: `main`  
Repository application baseline: `fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75`  
Repository Alembic head: `0058`  
Production URL: `https://health.funti.cc`  
Production application: `fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75`  
Production Alembic: `0058`

## Current verdict

```text
HC-015 DEPLOYED / VERIFIED
HC-016 DEPLOYED / MANUALLY ACCEPTED
HC-017 B+C1+C2+D1+D2+E1+E2 DEPLOYED / AUTOMATED SMOKE VERIFIED
HC-017 MANUAL UI SMOKE PENDING
HC-017 DOCUMENT/OCR WORKER PIPELINE DISABLED / NOT OPERATIONALLY ACCEPTED
HC-017 E3 NEXT / NOT IMPLEMENTED
HC-018 MEDICATION REMINDERS PLANNED / NOT IMPLEMENTED
PRODUCTION DOCUMENT UPLOAD DISABLED
```

Repository application code and production now match:

```text
application: fb1e7a2f... 
Alembic: 0058
DOCUMENT_UPLOAD_ENABLED=false
```

The production deployment agent changed no product code and made no GitHub changes. It deployed and verified the exact already-reviewed GitHub SHA only.

## Production capabilities

Production currently provides and has previously accepted:

- Google OIDC and Email Magic Links;
- PostgreSQL sessions;
- workspace/profile permissions and FORCE RLS;
- Basic Health Profile and weight history;
- consent, provenance and audit;
- Clinical Context and review states;
- contextual intake;
- Russian-first Clinical Dictionaries;
- owner-controlled permanent clinical-record erasure.

Production now also contains the HC-017 B–E2 application code, frontend routes, schema and restricted PostgreSQL interfaces for:

- document intake metadata;
- encrypted scanner-worker boundary;
- quotas and reconciliation;
- safe rendering;
- OCR candidates and human review;
- source-preserving Lab drafts;
- explicit confirmation into immutable Lab observations.

These HC-017 components are deployed as a disabled foundation, not as an enabled end-user pipeline.

Production does not yet operationally provide:

- document upload;
- scanner, renderer, reconciler or OCR workers;
- production document encryption/storage;
- malware scanning or safe rendering as a running service;
- OCR execution or OCR review from uploaded documents;
- end-to-end creation and confirmation of Lab observations from documents;
- metric dynamics.

## HC-017 repository and deployment status

### Slice A — Documents/OCR/Labs architecture

Status: `MERGED` through PR `#47`.

### Slice B — Secure Document Intake Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / UPLOAD DISABLED`.

```text
PR: #48
verified head: 46c5ea89d35cc85be0af3b80a9c56f40d5705ac5
merge: ccabab77cf929456a74b69c3478c71f92f167f78
CI: #402
migration: 0050
```

Provides document metadata, FORCE RLS, bounded PDF/JPEG/PNG intake, opaque quarantine keys, document API/UI and fail-safe production disablement.

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / WORKER NOT RUNNING`.

```text
PR: #51
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

Provides authenticated encrypted objects, protected key-file loading, ClamAV scanning contract, a separate NOBYPASSRLS scanner role and restricted worker functions.

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / WORKERS NOT RUNNING`.

```text
PR: #53
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
migrations: 0052–0053
```

Provides transaction-safe quotas, encrypted safe-page artifacts, separate renderer/reconciler roles, complete GCM verification, sealed-memory parsing, bounded rendering and storage reconciliation.

### Slice D1 — Local OCR Candidate Extraction

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / OCR WORKER NOT RUNNING`.

```text
PR: #56
verified head: dc28e9e220dd51264e6dab1244ce8d8696f501b2
merge: a33c3d515b885c6ea0e8f51291a1d25bed77cd7d
CI: #442
migration: 0054
```

Provides bounded local Tesseract, encrypted TSV provenance and owner/edit-only review candidates. OCR creates no clinical or Lab facts.

### Slice D2 — Human OCR Review and Patient Matching

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / NO LIVE OCR INPUT`.

```text
PR: #58
verified head: 4ecae1fb0816803b2d858db1f5016bce589544d5
merge: f67a1128e29a1c62e8a3b27dd20c973df82947ad
CI: #454
migration: 0055
```

Provides accept/edit/reject/defer review, optimistic concurrency, explicit patient decisions and manifest-bound finalization. Finalized OCR remains source transcription, not a clinical fact.

### Slice E1 — Source-preserving Lab Drafts

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / NO LIVE DOCUMENT PIPELINE`.

```text
PR: #61
verified head: 419386e909207ab67921c008e210c059aba6658c
merge: 2ad0ca47d994472201c218b3e6af37145cbacdec
CI: #477
migrations: 0056–0057
```

Provides owner/edit-only source-preserving drafts and exact candidate manifests. Drafts preserve source analyte, value, unit, range, date, specimen, flag and comment. They remain invisible to `view`, `analyze`, analytics and AI interpretation.

### Slice E2 — Explicit Confirmation and Confirmed Observations

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / MANUAL UI SMOKE PENDING`.

```text
PR: #65
verified head: 55f10d311d1f39262d557fa7b60cc07060ac5590
merge: 1d61331194edf0f78b94a304d27ccf31dfa2a755
CI: #491
migration: 0058
```

Implemented:

- separate explicit confirmation action;
- immutable `lab_observations` and `lab_observation_sources`;
- owner/edit-only confirmation;
- owner/edit/view/analyze confirmed-only reads;
- no worker confirmation or direct runtime mutation grants;
- exact draft/document/review/patient/candidate version checks;
- deterministic candidate locking before source snapshot copying;
- active health-data consent recheck;
- mandatory source/profile/structured-record acknowledgements;
- additional assignment acknowledgement for `not_present`;
- one observation per source draft;
- profile-scoped idempotency and concurrent replay handling;
- content-free audit;
- separate confirmation API and UI;
- no automatic mapping, unit conversion or medical interpretation.

## Production rollout evidence

Exact Phase 1 production state:

```text
application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
Alembic before: 0049
Alembic after: 0058
frontend release: /opt/health-compass/releases/hc017-erasure-20260712T223445Z-fb1e7a2f
production bundle: assets/index-WPvMNLMb.js
backend service: health-compass-api.service / active
DOCUMENT_UPLOAD_ENABLED=false
worker services: not created and not running
```

Verified backup:

```text
/opt/health-compass/backups/hc017-pre-migrate-20260712T223356Z.dump
size: 265335 bytes
sha256: 0ef5ace5fabeaa45db35b2d5b66430e1e160e140f096af710cdc07c5254b797d
pg_restore --list: 341 entries / success
```

Build and test evidence:

```text
backend: compile success, Ruff success, 191 passed, 14 skipped, 0 failed
frontend: lint 0 errors, typecheck success, 55 passed, build success
HTTP: /, /login, /api/health, /app, /app/documents, /app/lab-drafts healthy
fresh logs: 0 Traceback/ERROR/CRITICAL/54001/42501/permission denied/5xx
```

Canonical evidence:

```text
docs/changes/2026-07-13-hc-017-phase1-production-deployed.md
docs/implementation/HC-017-B-E2-CONTROLLED-PRODUCTION-ROLLOUT.md
```

## Production Python compatibility

The production CPython 3.12.13 build has `HAVE_MEMFD_CREATE=0`, despite the Linux kernel and libc supporting memfd and sealing.

PR #68 added a centralized fail-closed compatibility layer:

```text
PR: #68
verified head: 4984088d5e9e5d1412d9a071480cf7dabe408c71
merge: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
CI: #500
```

Properties:

- native CPython API remains preferred;
- fallback calls libc `memfd_create` for the same kernel primitive;
- no filesystem plaintext fallback exists;
- file seals remain mandatory;
- all original rendering/OCR tests remain enabled;
- production preflight passed on the actual self-contained Python runtime.

## Immediate acceptance work

Before marking Phase 1 fully accepted, the owner must manually verify in a browser:

- Google login and logout;
- Email Magic Link login;
- dashboard/profile loading;
- Clinical Context create/edit/remove regression;
- HC-016 permanent deletion;
- `/app/documents` and Lab routes navigation/direct refresh;
- disabled-upload state is clear and does not break navigation.

Current acceptance state:

```text
SERVER ROLLOUT ACCEPTED
AUTOMATED SMOKE PASSED
SECURITY CHECKS PASSED
MANUAL UI SMOKE PENDING
FULL DOCUMENT/OCR PIPELINE DISABLED / NOT ACCEPTED
```

## Next allowed repository work

```text
HC-017 Slice E3 — Correction, Void and Owner-only Erasure
```

E3 must preserve confirmed source/value immutability:

- corrections create replacement observations and supersession chains;
- no confirmed value is edited in place;
- voiding is explicit and reasoned;
- owner-only permanent erasure removes observation and immutable sources atomically;
- document erasure cannot leave unsupported sole-provenance observations;
- restricted functions and negative PostgreSQL tests are required before API/UI;
- no automatic production enablement.

Metric dynamics remain later than E3 and may use only active confirmed compatible numeric observations. No silent unit conversion is allowed.

HC-018 medication reminders remain a separate planned stage and must not be mixed into E3.

## Remaining blockers before full Documents/OCR/Labs enablement

- production encryption credentials, recovery and rotation;
- private encrypted storage and bounded spool directories;
- dedicated scanner/renderer/reconciler/OCR OS users;
- hardened systemd services;
- verified Poppler, ImageMagick, Tesseract and traineddata versions;
- ClamAV/FreshClam health and current signatures;
- reverse-proxy request-body limit;
- measured profile/global quotas and disk reserve;
- hostile-file, timeout, memory and decompression-bomb probes;
- database plus encrypted-object backup/restore validation;
- no-sensitive-log verification under the running document pipeline;
- disposable document/OCR/Labs owner smoke;
- reviewed code/config change permitting controlled production upload;
- explicit owner approval to set `DOCUMENT_UPLOAD_ENABLED=true`.

## Stop conditions

Stop merge or rollout when:

- OCR or a ready draft creates a confirmed observation automatically;
- a worker, viewer or analyzer can confirm;
- patient decision `unknown` or `mismatch` is accepted;
- `not_present` lacks explicit profile assignment acknowledgement;
- source wording/value/unit/range or exact provenance is lost;
- stale versions can be confirmed;
- concurrent/idempotent confirmation can create duplicates;
- confirmed source/value fields can be edited in place;
- drafts or raw OCR become visible to `view`/`analyze`;
- direct broad mutation grants exist;
- source erasure can orphan a sole-provenance observation;
- medical text or values enter ordinary audit/logs;
- Alembic has multiple heads;
- exact-head CI or negative PostgreSQL tests are absent;
- production upload is enabled before Phase 2 controls and explicit approval.
