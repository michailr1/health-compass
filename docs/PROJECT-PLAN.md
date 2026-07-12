# Health Compass — канонический план проекта

Версия: 2.4  
Дата: 2026-07-12  
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
- OCR/AI output is not a fact before explicit human confirmation.
- Reviewed OCR remains transcription until a separate clinical confirmation.
- Confirmed Labs preserve source wording and exact provenance.
- No automatic diagnosis, prescription or dose calculation.
- Human and Pet contours remain separated.
- Production rollout is backup-first and exact-SHA.
- Destructive actions use least privilege and optimistic concurrency.
- Documents remain untrusted until quarantine, scanning and safe rendering succeed.
- Raw documents, OCR drafts, reviewed transcription and confirmed facts have distinct access boundaries.
- Confirmed source/value fields are immutable; corrections create replacement records.
- `DEFINED`, `IMPLEMENTED`, `MERGED`, `CI VERIFIED` and `DEPLOYED` are separate states.

## 4. Repository and production state

Repository application baseline:

```text
34425d89fb205a43d8ce543862b2ab8371dabbb4
Alembic head: 0055
```

Production:

```text
https://health.funti.cc
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

Current verdict:

```text
SLICE D D1+D2 MERGED / CI VERIFIED / NOT DEPLOYED
SLICE E ARCHITECTURE DEFINED / REVIEWED
SLICE E NOT IMPLEMENTED
PRODUCTION UNCHANGED
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
- structured logging and query/token redaction.

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

Status: `IN PROGRESS`.

```text
Upload
→ encrypted quarantine
→ malware scan
→ safe rendering
→ OCR candidates
→ human review
→ explicit patient matching
→ structured Lab draft
→ explicit observation confirmation
→ Labs
→ metric dynamics
```

### Slice A — Architecture

Status: `MERGED` through PR `#47`.

### Slice B — Secure Document Intake Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#48`.

```text
verified head: 46c5ea89d35cc85be0af3b80a9c56f40d5705ac5
merge: ccabab77cf929456a74b69c3478c71f92f167f78
CI: #402
migration: 0050
```

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#51`.

```text
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

Provides authenticated encryption, encrypted quarantine storage, local ClamAV and a restricted scanner worker.

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#53`.

```text
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
migrations: 0052–0053
```

Provides quotas, encrypted safe-page artifacts, restricted renderer/reconciler roles, GCM-before-parser verification, bounded rendering and storage reconciliation.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-C2-SAFE-RENDERING-EVIDENCE-2026-07-12.md
```

### Combined C1+C2 security review

Status: `COMPLETE`.

```text
ACCEPT FOR REPOSITORY FOUNDATION
NO UNRESOLVED CRITICAL OR HIGH FINDING
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

Canonical review:

```text
docs/reviews/HC-017-C1-C2-COMBINED-SECURITY-REVIEW-2026-07-12.md
```

### Slice D — OCR Candidates and Human Review

Status: `D1+D2 IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

Canonical contract:

```text
docs/implementation/HC-017-SLICE-D-OCR-CANDIDATES-AND-HUMAN-REVIEW.md
```

#### D1 — Local OCR Candidate Extraction

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#56`.

```text
verified head: dc28e9e220dd51264e6dab1244ce8d8696f501b2
merge: a33c3d515b885c6ea0e8f51291a1d25bed77cd7d
CI: #442
migration: 0054
```

Implemented:

- OCR runs, encrypted provenance and candidate tables;
- FORCE RLS and owner/edit-only candidate text;
- dedicated OCR-worker role with no direct table grants;
- bounded local Tesseract over authenticated safe-page PNG;
- encrypted TSV artifacts;
- strict parser and deterministic `needs_review` candidates;
- no automatic Clinical Context, measurement or Labs facts.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-D1-OCR-CANDIDATES-EVIDENCE-2026-07-12.md
```

#### D2 — Human Review and Patient Matching

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#58`.

```text
verified head: 4ecae1fb0816803b2d858db1f5016bce589544d5
merge: f67a1128e29a1c62e8a3b27dd20c973df82947ad
CI: #454
migration: 0055
```

Implemented:

- accept/edit/reject/defer candidate actions;
- active consent and optimistic concurrency;
- explicit patient decisions;
- exact candidate manifest;
- mismatch/unresolved/deferred blocking;
- idempotent finalization;
- content-free audit;
- revisable decisions before finalization;
- accessible review UI;
- no Clinical Context, measurement or Labs creation.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-D2-HUMAN-REVIEW-EVIDENCE-2026-07-12.md
```

### Slice E — Confirmed Labs Core

Status: `ARCHITECTURE DEFINED / REVIEWED / NOT IMPLEMENTED / NOT DEPLOYED`.

Canonical contract:

```text
docs/implementation/HC-017-SLICE-E-CONFIRMED-LABS-CORE.md
```

Architecture review:

```text
docs/reviews/HC-017-SLICE-E-ARCHITECTURE-REVIEW-2026-07-12.md
```

Architecture verdict:

```text
ARCHITECTURE ACCEPTED FOR FUTURE IMPLEMENTATION
NO SLICE E CODE YET
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

Selected model:

- finalized D2 transcription remains source, not a Lab fact;
- owner/editor creates a source-preserving Lab draft;
- exact OCR candidates are mapped to analyte/value/unit/range/date/specimen roles;
- source analyte/value/unit/range/date text is retained separately from parsed fields;
- unknown/mismatch patient decision blocks confirmation;
- `not_present` requires an additional explicit profile-assignment acknowledgement;
- confirmation is a separate atomic transaction;
- one draft creates at most one immutable observation;
- corrections create replacement and supersession chains;
- no silent unit conversion, canonical mapping or reference-range interpretation;
- analyze receives active confirmed observations only;
- document erasure removes sole-provenance drafts/observations;
- no worker may confirm, correct, void or erase observations.

#### E1 — Structured Lab Drafts

Status: `NEXT / NOT IMPLEMENTED / NOT DEPLOYED`.

Planned scope:

- draft and draft-source tables;
- FORCE RLS and owner/edit-only access;
- current finalized D2/patient-decision gate;
- explicit value kind and unknown/not-present choices;
- source-preserving fields and optional parsed representations;
- exact candidate/source-role manifest;
- optimistic concurrency;
- draft API and source-fragment selection UI;
- zero confirmed observation rows.

#### E2 — Explicit Confirmation

Status: `PLANNED AFTER E1 REVIEW`.

- immutable confirmed observation/source tables;
- current document/D2/patient/draft/source manifest validation;
- explicit confirmation acknowledgements;
- idempotent atomic confirmation;
- owner/edit confirmation;
- owner/edit/view/analyze confirmed-only reads;
- no interpretation or automatic normalization.

#### E3 — Correction, Void and Erasure

Status: `PLANNED AFTER E2 REVIEW`.

- replacement correction chain;
- explicit void reason;
- owner-only permanent erasure;
- document-linked deletion propagation;
- no orphaned sole-provenance observation.

#### Slice E stop conditions

Do not merge or deploy when:

- OCR/finalized transcription creates an observation automatically;
- patient decision is unknown or mismatch;
- source wording/value/unit/range is not preserved;
- unit conversion/canonical mapping is silent;
- exact source manifest is missing or stale;
- confirmed data can be updated in place;
- draft rows are visible to view/analyze;
- analyze can access OCR text;
- app/worker roles have broad mutation privileges;
- duplicate-looking observations are silently merged;
- source deletion leaves unsupported observations;
- medical values appear in logs/audit;
- exact-head negative PostgreSQL tests are absent.

### Slice F — Metric dynamics

Status: `PLANNED AFTER CONFIRMED LABS`.

- compatible numeric series only;
- no silent unit conversion;
- chart and accessible table;
- source-specific ranges;
- provenance links;
- no diagnosis or treatment advice.

### Slice G — Controlled production rollout

Status: `PLANNED AFTER IMPLEMENTATION AND REVIEW`.

Required readiness:

- production encrypted storage and key recovery;
- scanner/renderer/reconciler/OCR OS and DB identities;
- hardened systemd units;
- verified Poppler/ImageMagick/Tesseract and language models;
- ClamAV/FreshClam and healthy signatures;
- reverse-proxy body limit;
- isolated bounded multipart spool;
- measured quotas and disk reserve;
- exact-SHA CI;
- backup-first migrations;
- hostile-file and timeout probes;
- no-sensitive-log verification;
- disposable-document owner smoke;
- canonical production evidence.

## 7. Later phases

### PHASE-04 — Data sources and integrations

- Oura;
- lab CSV expansion;
- Apple Health / Health Connect after ADR;
- idempotent sync and freshness.

### PHASE-05 — Timeline and analytics

- unified timeline;
- trends and personal baseline;
- Attention Inbox;
- search.

### PHASE-06 — Shared access

- invitations;
- permission lifecycle;
- revoke and audit;
- RLS matrix.

### PHASE-07 — Privacy and lifecycle

- consent center;
- export;
- profile/user deletion;
- document source/derived/OCR/confirmed deletion;
- retention;
- external-processing consent.

### PHASE-08 — AI Health Assistant

- retrieval-grounded answers;
- evidence/citations;
- red-flag routing;
- prompt-injection tests;
- no diagnosis or dose calculation.

### PHASE-09 — Product expansion

- family profiles;
- Pet Health;
- clinician/caregiver workflows;
- Offline Emergency Card;
- subscriptions;
- mobile/PWA.

## 8. Immediate plan

1. Merge Slice E architecture/review documentation.
2. Recheck current `main`, open migration PRs and Alembic heads.
3. Resolve exact E1 numeric precision, source-role enum and field limits.
4. Assign the next free migration only after that recheck.
5. Implement E1 draft/source tables with FORCE RLS.
6. Implement restricted draft/source functions and owner/edit-only UI.
7. Require current finalized D2 review, allowed patient decision, active consent and optimistic concurrency.
8. Prove zero confirmed observations before E2.
9. Complete exact-head backend/frontend/migration/PostgreSQL gates and independent E1 review.
10. Keep production document upload disabled and do not create a VPS deployment task.

## 9. Global rollout stop conditions

Stop rollout when:

- target SHA and CI SHA differ;
- backup/restore evidence is absent;
- storage or credentials are publicly accessible;
- worker roles have broad privileges;
- scanner/parser/OCR can fail open;
- plaintext escapes private bounded memory/spool;
- quotas/reconciliation are not operational;
- OCR or medical values appear in logs;
- source-preserving confirmation/deletion contracts are incomplete;
- Alembic has multiple heads;
- security review is incomplete;
- disposable-document smoke is not approved.
