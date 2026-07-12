# Health Compass — канонический план проекта

Версия: 1.8  
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
- Runtime role remains `NOBYPASSRLS`.
- Direct Google OIDC and Email Magic Links for MVP.
- Verified email does not silently merge accounts.
- Medical data requires consent, provenance and audit.
- Free text is not silently rewritten.
- OCR/AI output is not a fact before explicit human confirmation.
- No automatic diagnosis, prescription or dose calculation.
- Human and Pet contours remain separated.
- Production rollout is backup-first and exact-SHA.
- Destructive actions use least privilege and optimistic concurrency.
- Documents are untrusted until quarantine, scanning and safe inspection succeed.
- Raw documents, OCR drafts and confirmed facts have different access boundaries.

## 4. Repository and production state

Repository application baseline:

```text
ccabab77cf929456a74b69c3478c71f92f167f78
Alembic head: 0050
```

Production:

```text
https://health.funti.cc
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
```

Current verdict:

```text
SLICE B REVIEWED
SLICE C ARCHITECTURE DEFINED
PRODUCTION UNCHANGED
```

## 5. Completed foundations

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
- scanner-safe consume;
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

### HC-016 — Clinical-record permanent erasure

Status: `DEPLOYED / MANUALLY ACCEPTED`.

## 6. PHASE-03 — Documents, OCR and Labs

Status: `IN PROGRESS`.

Target flow:

```text
Upload
→ quarantine
→ malware scan
→ safe rendering
→ OCR
→ human review
→ explicit confirmation
→ Labs
→ metric dynamics
```

### Slice A — Architecture

Status: `MERGED` through PR `#47`.

### Slice B — Secure Document Intake Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#48`.

Evidence:

```text
verified head: 46c5ea89d35cc85be0af3b80a9c56f40d5705ac5
merge: ccabab77cf929456a74b69c3478c71f92f167f78
CI: #402
migration: 0050
```

Implemented:

- document metadata and intake jobs;
- FORCE RLS and document-specific read boundary;
- dev/test private quarantine adapter;
- format, size and image-dimension checks;
- pre-parser body limit;
- rollback cleanup;
- API and minimal Documents UI.

Production upload remains disabled.

### Slice B independent security review

Status: `COMPLETE`.

Verdict:

```text
ACCEPT FOR REPOSITORY FOUNDATION
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

Required follow-ups:

- encrypted production storage;
- storage quota/free-space gate;
- orphan reconciliation;
- proxy upload limit;
- malware scanner;
- isolated worker;
- safe parser/rasterizer sandbox.

Canonical review:

```text
docs/reviews/HC-017-SLICE-B-INDEPENDENT-SECURITY-REVIEW-2026-07-12.md
```

### Slice C — Encrypted Storage, Scanner and Safe Rendering

Status: `ARCHITECTURE DEFINED / NEXT IMPLEMENTATION SLICE`.

Canonical design:

```text
docs/implementation/HC-017-SLICE-C-SCANNER-STORAGE-WORKER.md
```

Selected MVP architecture:

- local encrypted object storage on production VPS;
- `/var/lib/health-compass/documents` outside releases/web roots;
- AES-256-GCM versioned object envelope;
- keys delivered via systemd credentials;
- ClamAV `clamd` over Unix socket;
- `freshclam` signature updates;
- scanner fail closed;
- separate worker OS account;
- separate worker PostgreSQL login `NOBYPASSRLS`;
- constrained worker functions only;
- sandboxed PDF/image inspection;
- encrypted safe rasterized derivatives;
- per-profile/global quotas;
- reserved free-space threshold;
- orphan reconciliation;
- atomic accepted promotion;
- no external OCR/LLM.

#### Slice C implementation order

1. Recheck main, open migrations and Alembic heads.
2. Define migration and worker-role prerequisite.
3. Add encryption envelope and key-loading abstraction.
4. Add worker job claim/lease/complete functions.
5. Add ClamAV Unix-socket INSTREAM client.
6. Add signature freshness and fail-closed policy.
7. Add quotas and free-space checks.
8. Add orphan reconciliation.
9. Add bounded PDF/image inspection.
10. Add safe rasterization and encrypted derivatives.
11. Add retry/failure states and UI.
12. Run full independent security review.
13. Keep production disabled until a later rollout approval.

#### Candidate migration

Current head:

```text
0050
```

Candidate:

```text
0051
```

Number is assigned only after checking current heads and open PRs at implementation start.

#### Slice C implementation PR is not a rollout PR

The implementation PR must not:

- enable production upload;
- install host packages;
- provision production secrets;
- alter Apache limits;
- deploy worker/systemd units;
- apply production migration.

### Slice D — OCR candidates and review

Status: `PLANNED`.

- extraction runs;
- protected OCR artifacts;
- candidates `needs_review`;
- page-region review;
- field confidence;
- optimistic concurrency;
- no auto-confirmation.

### Slice E — Confirmed Labs

Status: `PLANNED`.

- explicit atomic confirmation;
- patient matching;
- source-preserving values and units;
- provenance-linked lab observations;
- document-linked deletion lifecycle.

### Slice F — Metric dynamics

Status: `PLANNED`.

- compatible numeric series;
- no silent unit conversion;
- chart and accessible table;
- source-specific ranges;
- provenance links;
- no medical interpretation.

### Slice G — Production rollout

Status: `PLANNED AFTER COMPLETE SECURITY REVIEW`.

- production storage/scanner readiness;
- exact-SHA CI;
- backup-first migration;
- worker privilege probes;
- clean/EICAR/malformed-file tests;
- public HTTPS body-limit test;
- no-sensitive-log verification;
- manual disposable-document smoke;
- canonical production evidence.

## 7. Later phases

### PHASE-04 — Data sources and integrations

- Oura;
- lab CSV/PDF expansion;
- Apple Health / Health Connect after ADR;
- idempotent sync and freshness.

### PHASE-05 — Timeline and analytics

- unified timeline;
- trends and personal baseline;
- Attention Inbox;
- search.

### PHASE-05.5 — Nutrition Photo MVP

Status: after Labs core.

### PHASE-06 — Shared access

- invitations;
- permissions lifecycle;
- revoke and audit;
- RLS matrix.

### PHASE-07 — Privacy and data lifecycle

- consent center;
- export;
- profile/user deletion;
- document raw/derived/confirmed deletion;
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

1. Merge Slice B independent-review and Slice C design docs.
2. Recheck current `main`, migration heads and open PRs.
3. Start Slice C implementation in a dedicated branch.
4. Implement database worker boundary before processing code.
5. Implement encryption and scanner clients with unit/fuzz tests.
6. Implement quota and reconciliation before safe rendering.
7. Add parser/rasterizer sandbox and resource limits.
8. Run exact-head CI and independent security review.
9. Do not create a production deployment task yet.

## 9. Slice C stop conditions

Do not merge or deploy if:

- storage is public or inside web/release paths;
- encryption key is in Git, `.env` or database;
- nonce reuse is possible;
- scanner is absent, stale, stubbed or fail-open;
- worker uses app/migrator credentials;
- worker has broad table access;
- raw PDF reaches browser;
- parser lacks CPU/memory/page/time limits;
- quota or free-space gates are absent;
- orphan reconciliation is absent;
- accepted promotion is not atomic/idempotent;
- filenames, paths, signed URLs or medical content enter ordinary logs;
- cross-profile access is possible;
- migration has multiple heads;
- exact-head CI or negative PostgreSQL tests are missing;
- production upload is enabled before controlled rollout approval.

## 10. Status terminology

`DEFINED`, `IMPLEMENTED`, `MERGED`, `VERIFIED` and `DEPLOYED` are separate states and must never be used interchangeably.
