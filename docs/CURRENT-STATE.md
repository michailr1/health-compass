# Health Compass — текущее состояние

Дата: 2026-07-13  
Основная ветка: `main`  
Repository application baseline: `c7dcae4da3860f6f73224f639be78424c6f3fa63`  
Repository Alembic head: `0062`  
Production URL: `https://health.funti.cc`  
Production application: `fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75`  
Production Alembic: `0058`

## Current verdict

```text
HC-015 DEPLOYED / VERIFIED
HC-016 DEPLOYED / MANUALLY ACCEPTED
HC-017 B+C1+C2+D1+D2+E1+E2 PHASE 1 DEPLOYED / MANUALLY ACCEPTED
HC-017 E3 IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED
HC-017 DOCUMENT/OCR PIPELINE DISABLED / NOT OPERATIONALLY ACCEPTED
HC-019 NAVIGATION AND EMPTY-STATE UX DEFINED / NEXT IMPLEMENTATION SLICE
HC-018 MEDICATION REMINDERS PLANNED / NOT IMPLEMENTED
PRODUCTION DOCUMENT UPLOAD DISABLED
```

Repository and production intentionally differ:

```text
repository application: c7dcae4da3860f6f73224f639be78424c6f3fa63
repository Alembic: 0062
production application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
production Alembic: 0058
DOCUMENT_UPLOAD_ENABLED=false
```

No E3 production rollout has been authorized or performed.

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
- navigation/direct refresh of deployed HC-017 document/Lab routes while upload is disabled.

Production contains the disabled HC-017 B–E2 foundation:

- document intake metadata and RLS;
- encrypted scanner-worker boundary;
- quotas and reconciliation;
- safe-rendering contracts;
- OCR candidates and human-review contracts;
- source-preserving Lab drafts;
- explicit confirmation into immutable Lab observations;
- restricted PostgreSQL worker functions and roles.

Production does not yet operationally provide:

- document upload;
- production document encryption/storage;
- scanner, renderer, reconciler or OCR services;
- malware scanning or safe rendering as a running pipeline;
- OCR execution from uploaded documents;
- end-to-end document → Lab observation processing;
- E3 correction/void/erasure UI or functions;
- metric dynamics.

## HC-017 Phase 1 acceptance

```text
SERVER ROLLOUT: ACCEPTED
AUTOMATED SMOKE: PASSED
SECURITY CHECKS: PASSED
MANUAL UI SMOKE: PASSED
PHASE 1: MANUALLY ACCEPTED
FULL DOCUMENT/OCR PIPELINE: DISABLED / NOT ACCEPTED
```

Verified production state:

```text
application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
Alembic: 0058
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

## HC-017 E3 repository state

E3 adds a lifecycle for confirmed laboratory observations:

### Correction

- never edits confirmed source/value fields in place;
- creates a new immutable replacement;
- preserves predecessor/successor chain and exact source snapshots;
- requires owner/edit, active consent, optimistic version and idempotency;
- requires fresh source/unit/date/profile/structured-record acknowledgements;
- requires separate `not_present` profile assignment;
- revokes app execute from the older acknowledgement-free correction signature.

### Void

- owner/edit can explicitly remove an active observation from active use;
- reason and optimistic version are mandatory;
- source/value/provenance remain immutable;
- remains available after consent withdrawal;
- voided observations disappear from normal view/analyze reads.

### Permanent erasure

- only the profile owner can erase;
- complete connected correction chain is removed atomically;
- immutable source snapshots, originating drafts and value-bearing Lab audit rows are removed;
- only a generic content-free tombstone remains;
- remains available after consent withdrawal.

### Document-linked protection

- owner-only document Lab erasure marks the source document `deletion_pending`;
- all document-derived Lab observations/drafts are removed atomically;
- independent RLS guard hides rows for pending/erased documents;
- transition trigger and chain erasure use deterministic `NOWAIT` locking;
- contention returns controlled `HC409`, not deadlock or post-erasure orphan creation.

### Privacy hardening

```text
active structured observation: owner/edit/view/analyze
superseded/voided lifecycle history: owner/edit only
OCR reviewed-text source snapshots: owner/edit only
```

### API/UI

```text
GET    /profiles/{profile_id}/labs/observations/history
POST   /profiles/{profile_id}/labs/observations/{id}/correct
POST   /profiles/{profile_id}/labs/observations/{id}/void
DELETE /profiles/{profile_id}/labs/observations/{id}
DELETE /profiles/{profile_id}/documents/{document_id}/lab-data
frontend: /app/labs
```

The UI creates corrections as new records, requires reasons, repeats confirmation before correction, restricts permanent erasure to the owner and requires typing `УДАЛИТЬ`.

Exact evidence:

```text
PR: #70
verified head: 0b7b72b87c0f046385eb12849dc37cab8d558c02
merge: c7dcae4da3860f6f73224f639be78424c6f3fa63
CI: #544 / success
migrations: 0059–0062
review: ACCEPT / NO UNRESOLVED CRITICAL OR HIGH FINDING
```

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-E3-OBSERVATION-LIFECYCLE.md
docs/changes/2026-07-13-hc-017-e3-merged.md
```

## Production Python compatibility

Production CPython 3.12.13 has `HAVE_MEMFD_CREATE=0`, although Linux and libc support memfd/file sealing.

PR #68 added a fail-closed compatibility layer:

```text
PR: #68
merge/deployed application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
CI: #500
```

- native CPython API remains preferred;
- fallback calls libc `memfd_create` for the same kernel primitive;
- no filesystem plaintext fallback exists;
- file seals remain mandatory;
- original rendering/OCR tests remain enabled.

## HC-019 accepted UX decisions

HC-019 is the next implementation slice after E3:

- primary mobile navigation: `Главная · История · Добавить · Ассистент · Ещё`;
- `Документы` becomes `Анализы`;
- Analyses empty state explains upload, review, confirmation and downstream use;
- `Oura` is not a top-level tab; `Сон` is the data domain;
- integrations live under Sources/settings;
- `Подключить источник` is hidden until a real integration exists;
- primary empty-state CTA must be executable;
- storage-path and `карантин` developer language is removed;
- upload action is `Загрузить` when available.

Canonical specification:

```text
docs/implementation/HC-019-NAVIGATION-AND-EMPTY-STATE-UX.md
docs/PRODUCT-UX-BASELINE.md
```

## Next repository work

```text
HC-019 — Navigation and Empty-State UX Revision
```

HC-019 is frontend/product-language work. It must not enable upload, start workers or change the HC-017 database/security contract.

HC-018 medication reminders remain planned separately.

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

- a confirmed source/value field can be edited in place;
- correction can bypass fresh acknowledgements;
- correction loses provenance or creates multiple active successors;
- a non-owner can permanently erase;
- erasure leaves broken links or sole-provenance rows;
- document deletion can deadlock or create post-erasure Lab data;
- view/analyze can read OCR source text;
- pending/erased document observations remain visible;
- medical values/reasons enter ordinary audit/logs;
- direct broad runtime mutation grants exist;
- Alembic has multiple heads;
- exact-head negative tests are absent;
- production upload is enabled before Phase 2 controls and explicit approval.
