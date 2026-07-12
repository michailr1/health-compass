# Health Compass — канонический план проекта

Версия: 2.0  
Дата: 2026-07-12  
Основная ветка: `main`

## 1. Product goal

Create a secure multi-user personal-health portal that combines profile data, clinical context, documents, laboratory results, wearable sources and an evidence-grounded AI assistant.

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
- No automatic diagnosis, prescription or dose calculation.
- Human and Pet contours remain separated.
- Production rollout is backup-first and exact-SHA.
- Destructive actions use least privilege and optimistic concurrency.
- Documents are untrusted until quarantine, malware scanning and safe rendering succeed.
- Raw documents, OCR drafts and confirmed facts have different access boundaries.
- `DEFINED`, `IMPLEMENTED`, `MERGED`, `CI VERIFIED` and `DEPLOYED` are separate states.

## 4. Current repository and production state

Repository:

```text
main: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
Alembic head: 0053
```

Production:

```text
URL: https://health.funti.cc
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

Current verdict:

```text
HC-017 C2 MERGED
HC-017 C2 CI VERIFIED
HC-017 NOT DEPLOYED
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
- structured logging and token/query redaction.

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

Target flow:

```text
Upload
→ encrypted quarantine
→ malware scan
→ safe rendering
→ OCR candidates
→ human review
→ patient matching
→ explicit confirmation
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

Implemented:

- document metadata and intake jobs;
- FORCE RLS and document-specific read boundary;
- bounded upload validation;
- pre-parser request limit;
- rollback cleanup;
- metadata/status API and UI.

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#51`.

```text
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

Implemented:

- streaming AES-256-GCM `HCENC1` objects;
- credential-file hardening;
- encrypted quarantine storage;
- local ClamAV Unix-socket client;
- scanner signature freshness gate;
- restricted scanner worker role/functions;
- retry, lease and idempotency controls;
- infected-document deletion lifecycle;
- safe scanner UI states.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-C1-IMPLEMENTATION-2026-07-12.md
```

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#53`.

```text
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
migrations: 0052–0053
```

Implemented:

#### Quotas and accounting

- profile/global byte quotas;
- active-document and queued-job limits;
- transaction advisory locks;
- reserved free-space configuration;
- canonical `current_storage_key`.

#### Restricted renderer

```text
health_compass_renderer LOGIN NOBYPASSRLS
```

- renderer-only claim/heartbeat/complete/fail functions;
- no direct table grants;
- complete GCM authentication before parser access;
- sealed read-only Linux memfd source and output;
- fixed executable paths and arguments;
- CPU, memory, output, page, pixel and timeout limits;
- strict PNG validation;
- encrypted accepted source and safe-page artifacts;
- atomic/idempotent accepted promotion;
- no raw PDF browser route.

#### Restricted reconciler

```text
health_compass_reconciler LOGIN NOBYPASSRLS
```

- opaque source/artifact reference inventory;
- orphan isolation and deletion;
- missing referenced-object handling;
- idempotent repeated reconciliation;
- no direct table grants.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-C2-SAFE-RENDERING-EVIDENCE-2026-07-12.md
```

### Slice D — OCR Candidates and Human Review

Status: `NEXT / NOT IMPLEMENTED`.

#### D1 — Local OCR candidate extraction

Planned:

- local OCR over C2 safe-page PNG artifacts only;
- separate `health_compass_ocr_worker LOGIN NOBYPASSRLS` role;
- bounded Tesseract subprocess;
- encrypted OCR provenance artifacts;
- strict TSV parser;
- candidate text, confidence and page bounding boxes;
- candidates always start `needs_review`;
- owner/edit-only candidate access;
- no automatic Clinical Context or Labs record.

#### D2 — Human review and patient matching

Planned:

- accept, edit, reject and defer candidate actions;
- explicit patient-match state: unknown/match/mismatch;
- optimistic concurrency with expected timestamps;
- atomic review transitions;
- no confirmation when patient match is unknown or mismatch;
- content-free audit;
- accessible review UI linked to safe-page provenance.

#### Slice D stop conditions

Do not merge when:

- OCR receives raw or unauthenticated documents;
- OCR output is stored as a clinical fact;
- view/analyze can read OCR text;
- patient mismatch can be bypassed;
- candidate edits lack optimistic concurrency;
- OCR text or patient identifiers enter ordinary logs;
- worker has direct table grants;
- subprocess limits are absent;
- exact-head PostgreSQL negative tests are absent.

### Slice E — Confirmed Labs

Status: `PLANNED AFTER SLICE D`.

- explicit atomic confirmation;
- source-preserving analyte/value/unit/range;
- patient-match prerequisite;
- provenance-linked lab observations;
- document-linked deletion lifecycle;
- no automatic medical interpretation.

### Slice F — Metric dynamics

Status: `PLANNED`.

- compatible numeric series;
- no silent unit conversion;
- chart plus accessible table;
- source-specific ranges;
- provenance links;
- no diagnosis or treatment advice.

### Slice G — Controlled production rollout

Status: `PLANNED AFTER IMPLEMENTATION AND SECURITY REVIEW`.

Required readiness:

- production encrypted storage and key recovery;
- scanner/renderer/reconciler OS and DB identities;
- hardened systemd units;
- verified Poppler/ImageMagick/Tesseract versions;
- ClamAV/FreshClam and fresh signatures;
- reverse-proxy body limit;
- isolated bounded multipart spool;
- measured quotas and disk reserve;
- exact-SHA CI;
- backup-first migrations;
- clean/EICAR/malformed/password/timeout probes;
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

### PHASE-07 — Privacy and data lifecycle

- consent center;
- export;
- profile/user deletion;
- document raw/derived/OCR/confirmed deletion;
- retention;
- external-processing consent.

### PHASE-08 — AI Health Assistant

- retrieval-grounded answers;
- evidence and citations;
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

1. Merge C2 evidence documentation.
2. Perform independent combined C1+C2 security review.
3. Recheck current `main`, open PRs and Alembic heads.
4. Define Slice D data and authorization contracts.
5. Implement D1 in a dedicated branch and PR.
6. Keep production document upload disabled.
7. Run full exact-head backend/frontend/migration/PostgreSQL gates.
8. Implement D2 only after D1 review.
9. Do not create a production deployment task until Slice G readiness gates pass.

## 9. Global rollout stop conditions

Stop rollout when:

- repository and target SHA are not exact;
- backup/restore evidence is absent;
- storage or credentials are publicly accessible;
- worker roles have broad privileges;
- scanner/parser/OCR can fail open;
- plaintext files escape bounded private temporary storage;
- quotas and reconciliation are not operational;
- logs expose filenames, paths, OCR text or medical values;
- Alembic has multiple heads;
- independent security review is incomplete;
- manual disposable-document smoke is not approved.
