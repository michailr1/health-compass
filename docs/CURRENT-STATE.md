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
HC-017 B+C1+C2+D1+D2+E1+E2 PHASE 1 DEPLOYED / MANUALLY ACCEPTED
HC-017 DOCUMENT/OCR PIPELINE DISABLED / NOT OPERATIONALLY ACCEPTED
HC-017 E3 NEXT / NOT IMPLEMENTED
HC-019 NAVIGATION AND EMPTY-STATE UX DEFINED / SCHEDULED AFTER E3
HC-018 MEDICATION REMINDERS PLANNED / NOT IMPLEMENTED
PRODUCTION DOCUMENT UPLOAD DISABLED
```

Application code and production schema match:

```text
application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
Alembic: 0058
DOCUMENT_UPLOAD_ENABLED=false
```

## Production capabilities

Production currently provides and has been manually accepted for:

- Google OIDC and Email Magic Links;
- PostgreSQL sessions;
- workspace/profile permissions and FORCE RLS;
- Basic Health Profile and weight history;
- consent, provenance and audit;
- Clinical Context and review states;
- contextual intake;
- Russian-first Clinical Dictionaries;
- owner-controlled permanent clinical-record erasure;
- navigation and direct refresh of deployed HC-017 document/Lab routes while upload is disabled.

Production also contains the disabled HC-017 B–E2 foundation:

- document intake metadata and RLS;
- encrypted scanner-worker boundary;
- quotas and reconciliation;
- safe-rendering contracts;
- OCR candidates and human-review contracts;
- source-preserving Lab drafts;
- explicit confirmation into immutable Lab observations;
- restricted PostgreSQL worker functions and roles.

These components are deployed as code/schema foundation only. Production does not yet operationally provide:

- document upload;
- production document encryption/storage;
- scanner, renderer, reconciler or OCR services;
- malware scanning or safe rendering as a running pipeline;
- OCR execution from uploaded documents;
- end-to-end document → Lab observation processing;
- metric dynamics.

## HC-017 Phase 1 acceptance

Phase 1 server rollout and owner UI smoke are accepted.

Owner confirmed that the deployed UI opens correctly, including the new document and Lab routes. The acceptance closes the manual-smoke gate for the disabled foundation; it does not enable or accept the full OCR pipeline.

```text
SERVER ROLLOUT: ACCEPTED
AUTOMATED SMOKE: PASSED
SECURITY CHECKS: PASSED
MANUAL UI SMOKE: PASSED
PHASE 1: MANUALLY ACCEPTED
FULL DOCUMENT/OCR PIPELINE: DISABLED / NOT ACCEPTED
```

Verified rollout state:

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

Build and smoke evidence:

```text
backend: compile success, Ruff success, 191 passed, 14 skipped, 0 failed
frontend: lint 0 errors, typecheck success, 55 passed, build success
HTTP: /, /login, /api/health, /app, /app/documents, /app/lab-drafts healthy
fresh logs: 0 Traceback/ERROR/CRITICAL/54001/42501/permission denied/5xx
```

Canonical evidence:

```text
docs/changes/2026-07-13-hc-017-phase1-production-deployed.md
docs/changes/2026-07-13-hc-017-phase1-manually-accepted.md
docs/implementation/HC-017-B-E2-CONTROLLED-PRODUCTION-ROLLOUT.md
```

## Production Python compatibility

The production CPython 3.12.13 build has `HAVE_MEMFD_CREATE=0`, although the Linux kernel and libc support memfd and file sealing.

PR #68 added a centralized fail-closed compatibility layer:

```text
PR: #68
verified head: 4984088d5e9e5d1412d9a071480cf7dabe408c71
merge/deployed application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
CI: #500
```

Security properties:

- native CPython API remains preferred;
- fallback calls libc `memfd_create` for the same kernel primitive;
- no filesystem plaintext fallback exists;
- file seals remain mandatory;
- original rendering/OCR tests remain enabled;
- production preflight passed on the actual self-contained Python runtime.

## HC-019 accepted UX decisions

PR #69 defines the follow-up frontend task and synchronizes the project plan with production.

Binding decisions:

- primary mobile navigation: `Главная · История · Добавить · Ассистент · Ещё`;
- `Документы` becomes `Анализы`;
- the Analyses empty state explains upload, review, confirmation and downstream use;
- `Oura` is not a top-level tab; `Сон` is the data domain;
- integrations live under Sources/settings;
- `Подключить источник` is hidden until a real integration exists;
- primary empty-state CTA must be executable;
- storage-path and `карантин` developer language is removed from UI;
- upload action is `Загрузить` when available.

Canonical specification:

```text
docs/implementation/HC-019-NAVIGATION-AND-EMPTY-STATE-UX.md
docs/PRODUCT-UX-BASELINE.md
docs/PROJECT-PLAN.md
```

HC-019 is scheduled after HC-017 E3 and must not be mixed into its database/security contract.

## Next allowed repository work

```text
HC-017 Slice E3 — Correction, Void and Owner-only Erasure
```

E3 invariants:

- confirmed source/value fields are never edited in place;
- corrections create replacement observations and supersession chains;
- voiding is explicit and reasoned;
- owner-only permanent erasure removes observation and immutable sources atomically;
- document erasure cannot leave unsupported sole-provenance observations;
- restricted functions and negative PostgreSQL tests come before API/UI;
- no automatic production rollout.

Metric dynamics remain later than E3 and may use only active confirmed compatible numeric observations. No silent unit conversion is allowed.

HC-018 medication reminders remain a separate planned stage and must not be mixed into E3.

## Remaining blockers before enabling Documents/OCR/Labs

Before setting `DOCUMENT_UPLOAD_ENABLED=true` or starting workers:

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
- no-sensitive-log verification under the running pipeline;
- disposable document/OCR/Labs owner smoke;
- reviewed code/config change permitting controlled production upload;
- explicit owner approval.

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
