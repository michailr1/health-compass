# Health Compass — канонический план проекта

Версия: 2.9  
Дата: 2026-07-13  
Основная ветка: `main`

## 1. Product goal

Create a secure multi-user personal-health portal combining profile data, clinical context, documents, laboratory results, wearable sources and an evidence-grounded AI assistant.

## 2. Source priority

1. Code, migrations and automated tests.
2. Confirmed production state.
3. ADRs and security invariants.
4. Canonical Markdown documents.
5. Reference PDF/XLSX/PPTX and external reviews.

## 3. Non-negotiable principles

- Security first.
- PostgreSQL RLS is the tenant boundary.
- Runtime and worker roles remain `NOBYPASSRLS`.
- Medical data requires consent, provenance and content-free audit.
- Verified email does not silently merge accounts.
- Free text is not silently rewritten.
- OCR output is not a fact before explicit human review.
- Reviewed OCR remains transcription until separate clinical confirmation.
- Confirmed source/value fields are immutable; correction creates replacement records.
- Correction creates a new medical fact and requires fresh acknowledgements.
- Void is explicit, reasoned and excluded from active use.
- Permanent Lab erasure is owner-only and removes the complete connected chain atomically.
- OCR source snapshots are not exposed to `view`/`analyze`.
- No automatic diagnosis, prescription or dose calculation.
- Human and Pet contours remain separated.
- Production rollout is backup-first and exact-SHA.
- `DEFINED`, `IMPLEMENTED`, `MERGED`, `CI VERIFIED`, `DEPLOYED` and `OPERATIONALLY ENABLED` are separate states.
- Navigation is organized by tasks and health-data domains, not implementation modules or vendors.

## 4. Repository and production state

Repository application baseline:

```text
application: c7dcae4da3860f6f73224f639be78424c6f3fa63
Alembic head: 0062
```

Production:

```text
https://health.funti.cc
application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
Alembic: 0058
DOCUMENT_UPLOAD_ENABLED=false
scanner/renderer/reconciler/OCR services: not running
```

Current verdict:

```text
HC-015 DEPLOYED / VERIFIED
HC-016 DEPLOYED / MANUALLY ACCEPTED
HC-017 B–E2 PHASE 1 DEPLOYED / MANUALLY ACCEPTED
HC-017 E3 MERGED / CI VERIFIED / NOT DEPLOYED
HC-017 DOCUMENT/OCR PIPELINE DISABLED / NOT OPERATIONALLY ACCEPTED
HC-019 NAVIGATION AND EMPTY-STATE UX DEFINED / NEXT
HC-018 MEDICATION REMINDERS PLANNED / NOT IMPLEMENTED
```

Canonical state/evidence:

```text
docs/CURRENT-STATE.md
docs/changes/2026-07-13-hc-017-phase1-production-deployed.md
docs/changes/2026-07-13-hc-017-phase1-manually-accepted.md
docs/changes/2026-07-13-hc-017-e3-merged.md
```

## 5. Completed platform foundations

### PHASE-01 — Platform and production

Status: `COMPLETED`.

- FastAPI + React/Vite;
- PostgreSQL + Alembic;
- HTTPS production;
- systemd/release workflow;
- exact-SHA deployment discipline.

### PHASE-02 — Identity and tenant isolation

Status: `COMPLETED / NON-BLOCKING HARDENING REMAINS`.

- Google OIDC;
- Email Magic Links;
- PostgreSQL sessions;
- workspace/profile bootstrap;
- FORCE RLS;
- account linking and duplicate resolution;
- structured logging and secret/query redaction.

### PHASE-02.5 — Progressive Health Intake

Status: `CORE SLICES DEPLOYED`.

- Basic Health Profile;
- weight history;
- consent/provenance/audit;
- Clinical Context;
- review states;
- contextual intake;
- Clinical Dictionaries v2.

### HC-015 — Code review remediation

Status: `DEPLOYED / VERIFIED`.

### HC-016 — Permanent clinical-record erasure

Status: `DEPLOYED / MANUALLY ACCEPTED`.

## 6. PHASE-03 — Documents, OCR and Labs

Status: `IN PROGRESS / B–E2 FOUNDATION DEPLOYED / E3 MERGED / PIPELINE DISABLED`.

Target flow:

```text
Upload
→ encrypted intake
→ malware scan
→ safe rendering
→ OCR candidates
→ human review
→ patient matching
→ source-preserving Lab draft
→ explicit observation confirmation
→ correction/void/erasure
→ metric dynamics
```

### Slice A — Architecture

Status: `MERGED` through PR `#47`.

### Slice B — Secure Document Intake Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / UPLOAD DISABLED`.

```text
PR: #48
migration: 0050
```

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / WORKER NOT RUNNING`.

```text
PR: #51
migration: 0051
```

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / WORKERS NOT RUNNING`.

```text
PR: #53
migrations: 0052–0053
```

### Slice D1 — Local OCR Candidates

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / OCR WORKER NOT RUNNING`.

```text
PR: #56
migration: 0054
```

### Slice D2 — Human Review and Patient Matching

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / NO LIVE OCR INPUT`.

```text
PR: #58
migration: 0055
```

Finalized D2 transcription remains source text, not a clinical fact.

### Slice E1 — Source-preserving Lab Drafts

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / NO LIVE DOCUMENT PIPELINE`.

```text
PR: #61
migrations: 0056–0057
```

Drafts preserve source wording and exact candidate provenance. They remain owner/edit-only and are not visible to `view`, `analyze`, analytics or AI interpretation.

### Slice E2 — Explicit Confirmation and Confirmed Observations

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / MANUALLY ACCEPTED`.

```text
PR: #65
migration: 0058
```

- separate explicit confirmation action;
- immutable confirmed observation and source snapshots;
- owner/edit confirmation;
- active structured observations visible by profile permission;
- exact source-version checks;
- `not_present` assignment acknowledgement;
- idempotent and concurrent-safe confirmation;
- no worker confirmation;
- no interpretation, normalization or silent unit conversion.

### Production memfd compatibility

Status: `DEPLOYED / VERIFIED`.

```text
PR: #68
merge/deployed application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
CI: #500
```

The compatibility layer uses the same Linux memfd primitive through libc when the self-contained Python omits the wrapper. It never falls back to plaintext disk files and all rendering/OCR tests remain enabled.

### Slice E3 — Correction, Void and Owner-only Erasure

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #70
verified head: 0b7b72b87c0f046385eb12849dc37cab8d558c02
merge: c7dcae4da3860f6f73224f639be78424c6f3fa63
CI: #544
migrations: 0059–0062
```

Implemented:

- immutable correction by replacement;
- predecessor/successor chains with exactly one successor;
- fresh source/unit/date/profile/structured-record acknowledgements;
- separate `not_present` profile assignment;
- acknowledgement-free legacy correction signature revoked from the app role;
- explicit void with bounded reason;
- active-only normal reads;
- owner/edit-only lifecycle history and OCR source snapshots;
- owner-only complete-chain erasure;
- content-free erasure tombstone;
- document-linked Lab erasure;
- independent document-state RLS guard;
- deterministic `NOWAIT` transition/chain locking;
- controlled `HC409` on contention;
- lifecycle API and `/app/labs` UI;
- frontend acknowledgement tests and PostgreSQL concurrency/RLS negatives.

Independent review:

```text
ACCEPT / NO UNRESOLVED CRITICAL OR HIGH FINDING
```

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-E3-OBSERVATION-LIFECYCLE.md
docs/changes/2026-07-13-hc-017-e3-merged.md
```

E3 has not been deployed. A production rollout requires a separate exact-SHA decision.

### Slice F — Metric Dynamics

Status: `PLANNED AFTER E3 / NOT STARTED`.

- active confirmed numeric observations only;
- compatible units only;
- no silent conversion;
- accessible table plus chart;
- source-specific ranges and provenance links;
- no diagnosis or treatment advice.

### Controlled production rollout

Status: `PHASE 1 COMPLETED / PHASE 2 BLOCKED / E3 NOT DEPLOYED`.

Phase 1 deployed the B–E2 application/schema foundation with upload disabled and workers stopped.

Phase 2 may enable document processing only after infrastructure, security, backup/restore and hostile-file gates pass.

## 7. HC-019 — Navigation and Empty-State UX Revision

Status: `DEFINED / NEXT / NOT IMPLEMENTED / NOT DEPLOYED`.

Binding scope:

- mobile bottom navigation: `Главная · История · Добавить · Ассистент · Ещё`;
- implementation/demo tabs leave primary navigation;
- `Документы` becomes `Анализы`;
- Analyses empty state explains upload, review, confirmation and downstream use;
- `Oura` is not a top-level tab; `Сон` is the data domain;
- device vendors live inside Sources/integration settings;
- `Подключить источник` is hidden until a real integration exists;
- primary empty-dashboard CTA is executable;
- storage-path and `карантин` developer language is removed;
- upload button is `Загрузить` when upload is available.

Canonical specification:

```text
docs/implementation/HC-019-NAVIGATION-AND-EMPTY-STATE-UX.md
docs/PRODUCT-UX-BASELINE.md
```

HC-019 must not enable upload, start workers or modify the E3 database/security contract.

## 8. HC-018 — Medication Reminders and Telegram Notifications

Status: `PLANNED / NOT IMPLEMENTED / NOT DEPLOYED`.

Placement requires a separate scheduling decision. It must remain separate from HC-017 and HC-019.

Initial scope:

- verified Telegram account linking;
- medication reminder plans and timezone-safe schedules;
- Telegram actions `Принял`, `Отложить`, `Пропустить`;
- reminder/response history in Health Compass;
- neutral default and explicit opt-in detailed mode;
- profile default plus per-reminder override;
- `no_response` distinct from skipped;
- Telegram only as delivery/interaction channel, never system of record.

Canonical contract:

```text
docs/implementation/HC-018-MEDICATION-REMINDERS-AND-TELEGRAM.md
```

## 9. Remaining blockers before enabling Documents/OCR/Labs

Before setting `DOCUMENT_UPLOAD_ENABLED=true` or starting workers:

- production encryption credentials, recovery and rotation;
- private encrypted storage and bounded spool directories;
- dedicated scanner/renderer/reconciler/OCR OS users;
- hardened systemd services;
- verified Poppler, ImageMagick, Tesseract and traineddata versions;
- ClamAV/FreshClam health and current signatures;
- reverse-proxy request-body limit;
- measured quotas and disk reserve;
- hostile-file, timeout, memory and decompression-bomb probes;
- database plus encrypted-object backup/restore validation;
- no-sensitive-log verification under the running pipeline;
- disposable document/OCR/Labs owner smoke;
- reviewed code/config change permitting controlled enablement;
- explicit owner approval.

## 10. Deferred platform work

- HC-013 session-management UI/rotation from stale PR `#25`;
- wearable ingestion and Oura;
- Apple Health / Health Connect ingestion under a separate ADR;
- AI safety foundation and evidence-grounded assistant;
- reports and doctor-visit preparation;
- family sharing expansion;
- Pet Health MVP;
- monetization and entitlements.

## 11. Current next action

```text
START HC-019 FROM CURRENT MAIN
APPLICATION BASELINE: c7dcae4da3860f6f73224f639be78424c6f3fa63
FRONTEND / PRODUCT LANGUAGE ONLY
DO NOT ENABLE DOCUMENT UPLOAD
DO NOT START WORKERS
DO NOT DEPLOY E3 WITHOUT A SEPARATE ROLLOUT DECISION
```
