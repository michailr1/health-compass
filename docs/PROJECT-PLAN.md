# Health Compass — канонический план проекта

Версия: 2.8  
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
- Medical data requires consent, provenance and audit.
- Verified email does not silently merge accounts.
- Free text is not silently rewritten.
- OCR output is not a fact before explicit human review.
- Reviewed OCR remains transcription until a separate clinical confirmation.
- Lab drafts remain non-clinical until E2 confirmation.
- Confirmed Labs preserve source wording and exact provenance.
- Confirmed source/value fields are immutable; correction creates replacement records.
- No automatic diagnosis, prescription or dose calculation.
- Human and Pet contours remain separated.
- Production rollout is backup-first and exact-SHA.
- `DEFINED`, `IMPLEMENTED`, `MERGED`, `CI VERIFIED`, `DEPLOYED` and `OPERATIONALLY ENABLED` are separate states.
- User navigation is organized by tasks and health-data domains, not implementation modules or vendors.

## 4. Repository and production state

Application baseline in repository:

```text
application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
Alembic head: 0058
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
HC-017 B+C1+C2+D1+D2+E1+E2 PHASE 1 DEPLOYED / MANUALLY ACCEPTED
HC-017 DOCUMENT/OCR PIPELINE DISABLED / NOT OPERATIONALLY ACCEPTED
HC-017 E3 NEXT / NOT IMPLEMENTED
HC-019 NAVIGATION AND EMPTY-STATE UX DEFINED / SCHEDULED AFTER E3
HC-018 MEDICATION REMINDERS PLANNED / NOT IMPLEMENTED
```

Canonical production evidence:

```text
docs/changes/2026-07-13-hc-017-phase1-production-deployed.md
docs/implementation/HC-017-B-E2-CONTROLLED-PRODUCTION-ROLLOUT.md
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

Status: `IN PROGRESS / PHASE 1 FOUNDATION DEPLOYED / PIPELINE DISABLED`.

Target product flow:

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

The production database, API foundation and frontend routes through E2 are deployed. Upload and all document-processing workers remain disabled until Phase 2 controls are complete.

### Slice A — Architecture

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

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / WORKER NOT RUNNING`.

```text
PR: #51
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / WORKERS NOT RUNNING`.

```text
PR: #53
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
migrations: 0052–0053
```

### Slice D1 — Local OCR Candidates

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / OCR WORKER NOT RUNNING`.

```text
PR: #56
verified head: dc28e9e220dd51264e6dab1244ce8d8696f501b2
merge: a33c3d515b885c6ea0e8f51291a1d25bed77cd7d
CI: #442
migration: 0054
```

### Slice D2 — Human Review and Patient Matching

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / NO LIVE OCR INPUT`.

```text
PR: #58
verified head: 4ecae1fb0816803b2d858db1f5016bce589544d5
merge: f67a1128e29a1c62e8a3b27dd20c973df82947ad
CI: #454
migration: 0055
```

Finalized D2 transcription remains source text, not a clinical fact.

### Slice E1 — Source-preserving Lab Drafts

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / NO LIVE DOCUMENT PIPELINE`.

```text
PR: #61
verified head: 419386e909207ab67921c008e210c059aba6658c
merge: 2ad0ca47d994472201c218b3e6af37145cbacdec
CI: #477
migrations: 0056–0057
```

E1 drafts preserve source wording and exact candidate provenance. They remain owner/edit-only and are not visible to `view`, `analyze`, analytics or AI interpretation.

### Slice E2 — Explicit Confirmation and Confirmed Observations

Status: `IMPLEMENTED / MERGED / CI VERIFIED / PHASE 1 DEPLOYED / MANUAL UI SMOKE PASSED`.

```text
PR: #65
verified head: 55f10d311d1f39262d557fa7b60cc07060ac5590
merge: 1d61331194edf0f78b94a304d27ccf31dfa2a755
CI: #491
migration: 0058
```

Implemented:

- explicit user confirmation separated from E1 draft mutations;
- immutable confirmed observation and source snapshots;
- owner/edit confirmation;
- owner/edit/view/analyze confirmed-only reads;
- active consent and exact source-version checks;
- `not_present` assignment acknowledgement;
- idempotent and concurrent-safe confirmation;
- source-candidate row locking before snapshot copying;
- no worker confirmation;
- no interpretation, normalization or silent unit conversion.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-E2-CONFIRMED-OBSERVATIONS-EVIDENCE-2026-07-13.md
```

### Production memfd compatibility

PR #68 resolved the production CPython build gap without skipping security tests or using disk-backed plaintext files.

```text
PR: #68
verified head: 4984088d5e9e5d1412d9a071480cf7dabe408c71
merge/deployed application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
CI: #500
production backend tests: 191 passed, 14 skipped, 0 failed
```

### Slice E3 — Correction, Void and Erasure

Status: `NEXT / NOT IMPLEMENTED / NOT DEPLOYED`.

Required implementation order:

1. independently review the exact E2 migration/function/API boundaries;
2. define immutable replacement and supersession model;
3. define explicit void state and reason without in-place value mutation;
4. define owner-only erasure transaction;
5. define atomic source-document deletion propagation;
6. add negative PostgreSQL tests before API/UI;
7. prove sole-provenance observations cannot be orphaned;
8. run exact-head backend/frontend/full migration/PostgreSQL CI;
9. perform independent E3 security review;
10. keep production unchanged until a separate rollout decision.

E3 stop conditions:

- confirmed source/value fields can be edited in place;
- correction loses prior observation or source provenance;
- a non-owner can permanently erase;
- document deletion leaves an unsupported observation;
- erasure is not atomic across observation and sources;
- view/analyze can see voided/erased data contrary to the contract;
- broad runtime or worker mutation grants exist;
- audit/logs contain medical text or values;
- exact-head negative tests are absent.

### Slice F — Metric Dynamics

Status: `PLANNED AFTER E3 REVIEW`.

- active confirmed numeric observations only;
- compatible units only;
- no silent conversion;
- accessible table plus chart;
- source-specific ranges and provenance links;
- no diagnosis or treatment advice.

### Slice G — Controlled Production Rollout

Status: `PHASE 1 COMPLETED / PHASE 2 BLOCKED`.

Phase 1 deployed the application/schema foundation through E2 with upload disabled and workers stopped.

Phase 2 may enable the document-processing pipeline only after infrastructure, security, backup/restore and hostile-file gates pass.

## 7. HC-019 — Navigation and Empty-State UX Revision

Status: `DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`.

Scheduling:

```text
AFTER HC-017 E3
DO NOT MIX WITH E3 DATABASE/SECURITY CONTRACT
```

Binding scope:

- mobile bottom navigation returns to no more than five items: `Главная · История · Добавить · Ассистент · Ещё`;
- implementation/demo tabs leave primary navigation;
- `Документы` becomes the user-task section `Анализы`;
- the Analyses empty state explains what to upload, what happens next and that nothing becomes a medical fact without confirmation;
- `Oura` is not a top-level tab; `Сон` is the health-data domain;
- device vendors live inside Sources/integration settings;
- `Подключить источник` is hidden until a real integration exists;
- the primary empty-dashboard CTA is always executable;
- storage-path and `карантин` developer language is removed from UI;
- the upload button is `Загрузить` when upload is actually available.

Canonical specification:

```text
docs/implementation/HC-019-NAVIGATION-AND-EMPTY-STATE-UX.md
docs/PRODUCT-UX-BASELINE.md
```

## 8. HC-018 — Medication Reminders and Telegram Notifications

Status: `PLANNED / NOT IMPLEMENTED / NOT DEPLOYED`.

Planned placement: after HC-017 E3 security review. HC-018 may be implemented before or in parallel with HC-017 F only after an explicit scheduling decision. It is a separate product and security contour and must not be mixed into the HC-017 E3 database contract.

Initial scope:

- verified Telegram account linking;
- medication reminder plans and timezone-safe schedules;
- Telegram actions `Принял`, `Отложить`, `Пропустить`;
- reminder and response history in Health Compass;
- neutral and detailed notification modes;
- neutral mode as the mandatory default;
- explicit opt-in, warning and preview before detailed mode;
- profile-level default plus per-reminder override;
- `no_response` kept distinct from a confirmed skipped dose;
- Telegram used only as a delivery/interaction channel, never as the medical system of record.

Privacy setting:

```text
telegram_message_detail_level = neutral | detailed
default = neutral
per-reminder override = inherit | neutral | detailed
```

Detailed messages may show only user-confirmed reminder fields such as medication name, dosage text, quantity/form, route/timing instruction and a user-authored note. They must not show diagnosis, unrelated clinical history, AI interpretation or inferred adherence conclusions.

No reminder or detailed mode may be created automatically from OCR, documents, AI output, import or a medication list. Health Compass must not prescribe, change dosage or interpret an absent response as a medical fact.

Implementation slices:

```text
R1 — Safe Telegram linking
R2 — Reminder plans and scheduler
R3 — Taken / Snooze / Skip responses
R4 — Privacy modes and adherence view
R5 — Optional repeat, course and stock reminders
```

Canonical contract:

```text
docs/implementation/HC-018-MEDICATION-REMINDERS-AND-TELEGRAM.md
```

## 9. Remaining blockers before enabling Documents/OCR/Labs

The schema and disabled application foundation are already deployed. Before setting `DOCUMENT_UPLOAD_ENABLED=true` or starting workers, all of the following remain mandatory:

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
- reviewed code/config change that permits controlled production enablement;
- explicit owner approval.

## 10. Deferred platform work

The following remains outside the current E3 target and must be rebased/reimplemented from current main when scheduled:

- HC-013 session-management UI and rotation from stale PR `#25`;
- operational frontend-symlink documentation from stale PR `#17`;
- wearable ingestion and Oura;
- Apple Health / Health Connect ingestion under a separate ADR;
- AI safety foundation and evidence-grounded assistant;
- reports and doctor-visit preparation;
- family sharing expansion;
- Pet Health MVP;
- monetization and entitlements.

HC-019 is no longer an untracked deferred note; it is a defined scheduled task in section 7.

## 11. Current next action

```text
START HC-017 E3 FROM CURRENT MAIN
APPLICATION BASELINE: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
DATABASE CONTRACT AND NEGATIVE TESTS FIRST
HC-019 FOLLOWS E3
HC-018 REMAINS PLANNED ONLY
NO PRODUCTION CHANGE DURING E3 IMPLEMENTATION
```
