# Health Compass — канонический план проекта

Версия: 2.1  
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

## 4. Repository and production state

Repository:

```text
main: ac9e21f3315c4624a845e633c2a90881d348ca30
Alembic head: 0053
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
C1+C2 COMBINED REVIEW COMPLETE
SLICE D ARCHITECTURE DEFINED
SLICE D NOT IMPLEMENTED
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

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#51`.

```text
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

Implemented:

- authenticated encrypted source objects;
- hardened key/path boundary;
- local ClamAV scanner;
- restricted scanner role and lease functions;
- retry/idempotency controls;
- infected-document deletion lifecycle.

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#53`.

```text
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
migrations: 0052–0053
```

Implemented:

- race-safe profile/global quotas;
- canonical current source reference;
- encrypted safe-page artifacts;
- separate renderer and reconciler roles;
- no direct worker table grants;
- full GCM verification before parser access;
- sealed memory-file input/output;
- bounded fixed-command rendering;
- strict PNG validation;
- encrypted accepted source and derivatives;
- atomic/idempotent accepted promotion;
- orphan/missing-object reconciliation;
- idempotent storage-missing audit.

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

Status: `ARCHITECTURE DEFINED / NEXT IMPLEMENTATION STAGE`.

Canonical contract:

```text
docs/implementation/HC-017-SLICE-D-OCR-CANDIDATES-AND-HUMAN-REVIEW.md
```

Selected MVP architecture:

- local Tesseract 5.x;
- LSTM engine `--oem 1`;
- initial language set `rus+eng`;
- TSV output with confidence and word coordinates;
- OCR consumes only current C2 `safe_page` artifacts;
- complete GCM verification before OCR;
- sealed read-only input memfd;
- bounded output memfd;
- fixed command and language/model configuration;
- separate OCR worker OS and PostgreSQL identities;
- no direct OCR-worker table grants;
- encrypted TSV provenance objects;
- strict TSV parser;
- text-block candidates start `needs_review`;
- owner/edit-only candidate text;
- separate explicit patient-match decision;
- no automatic Clinical Context, measurement or Labs creation.

#### D1 — OCR extraction foundation

Status: `NEXT / NOT IMPLEMENTED`.

Candidate migration:

```text
0054
```

Implementation order:

1. recheck current main, open PRs and Alembic heads;
2. create separate D1 branch;
3. define OCR run/artifact/candidate tables and FORCE RLS;
4. provision OCR-worker role prerequisite and restricted functions;
5. implement bounded Tesseract wrapper;
6. implement strict TSV parser and candidate aggregation;
7. encrypt TSV provenance before storage;
8. add owner/edit-only candidate read API;
9. add exact-head unit/PostgreSQL tests;
10. perform independent D1 review before merge.

#### D2 — Human review and patient matching

Status: `PLANNED AFTER D1 REVIEW`.

- candidate accept/edit/reject/defer;
- optimistic concurrency;
- explicit patient match/mismatch/not-present decision;
- review finalization with candidate-manifest checks;
- content-free audit;
- accessible page-region review UI;
- no Labs creation.

#### Slice D stop conditions

Do not merge when:

- OCR receives raw PDF or unauthenticated bytes;
- arbitrary OCR command options are accepted;
- output, memory, CPU or timeout is unbounded;
- OCR text appears in logs;
- view/analyze can read candidate text;
- OCR worker has direct table privileges;
- candidates begin accepted;
- patient matching is inferred automatically;
- OCR creates clinical/Labs facts;
- optimistic concurrency is absent;
- exact-head negative PostgreSQL tests are absent.

### Slice E — Confirmed Labs

Status: `PLANNED AFTER SLICE D`.

- explicit atomic confirmation;
- patient-match prerequisite;
- source-preserving analyte/value/unit/range;
- provenance-linked observations;
- document-linked deletion lifecycle;
- no automatic interpretation.

### Slice F — Metric dynamics

Status: `PLANNED`.

- compatible numeric series;
- no silent unit conversion;
- chart and accessible table;
- source-specific ranges;
- provenance links;
- no diagnosis/treatment advice.

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

1. Merge Slice D design documentation.
2. Recheck current `main`, open PRs and Alembic heads.
3. Create a dedicated D1 implementation branch.
4. Implement the database and worker privilege boundary first.
5. Implement bounded Tesseract and strict TSV parsing.
6. Add encrypted provenance and candidate RLS.
7. Run exact-head backend/frontend/migration/PostgreSQL gates.
8. Perform independent D1 review.
9. Keep production document upload disabled.
10. Do not create a VPS deployment task.

## 9. Global rollout stop conditions

Stop rollout when:

- target SHA and CI SHA differ;
- backup/restore evidence is absent;
- storage or credentials are publicly accessible;
- worker roles have broad privileges;
- scanner/parser/OCR can fail open;
- plaintext escapes private bounded memory/spool;
- quotas/reconciliation are not operational;
- logs expose filenames, paths, OCR text or medical values;
- Alembic has multiple heads;
- security review is incomplete;
- disposable-document smoke is not approved.
