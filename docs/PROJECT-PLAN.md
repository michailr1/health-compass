# Health Compass — канонический план проекта

Версия: 1.9  
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
- Repository implementation, merge, CI verification and production deployment remain separate states.

## 4. Repository and production state

Repository application baseline:

```text
a0dd405ca3e789cb70e5c4ad94de9a272dff878f
Alembic head: 0051
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
HC-017 C1 MERGED
HC-017 C1 CI VERIFIED
HC-017 C1 NOT DEPLOYED
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
→ encrypted quarantine
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
- bounded format/size/dimension validation;
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

Canonical review:

```text
docs/reviews/HC-017-SLICE-B-INDEPENDENT-SECURITY-REVIEW-2026-07-12.md
```

### Slice C — Encrypted Storage, Scanner and Safe Rendering

Status: `IN PROGRESS`.

Canonical design:

```text
docs/implementation/HC-017-SLICE-C-SCANNER-STORAGE-WORKER.md
```

Selected MVP architecture:

- local encrypted private object storage;
- `/var/lib/health-compass/documents` outside releases/web roots;
- AES-256-GCM versioned object envelope;
- keys delivered through protected service credentials;
- local ClamAV `clamd` over Unix socket;
- FreshClam signature updates;
- separate worker OS account;
- separate worker PostgreSQL login `NOBYPASSRLS`;
- constrained worker functions only;
- bounded safe rendering;
- encrypted safe derivatives;
- quotas and orphan reconciliation;
- no external OCR/LLM.

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED` through PR `#51`.

Evidence:

```text
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-C1-IMPLEMENTATION-2026-07-12.md
```

Implemented:

#### Authenticated object encryption

- `HCENC1` envelope;
- streaming AES-256-GCM;
- random nonce per object;
- AAD binds document UUID and artifact role;
- plaintext SHA-256 calculated during encryption;
- GCM authentication before a scan can complete;
- no application-created plaintext file in persistent document storage.

#### Key and path hardening

- key files opened with `O_NOFOLLOW`;
- regular single-link file requirement;
- unsafe writable modes rejected;
- exact 32-byte key requirement;
- encrypted readers reject symlinks and multiple hard links;
- object publication is exclusive;
- occupied object keys are never overwritten or deleted;
- opaque UUID storage keys only.

#### Scanner metadata and retry state

- encrypted byte size;
- encryption format and key ID metadata;
- scanner state/version/signature metadata;
- scanner completion timestamp;
- retry scheduling metadata;
- initial encrypted intake creates a `scan` job.

#### Restricted worker database boundary

Required role:

```text
health_compass_worker LOGIN NOBYPASSRLS
```

Functions:

```text
app_claim_document_job
app_heartbeat_document_job
app_complete_document_scan
app_fail_document_job
```

Controls:

- definer ownership and fixed settings;
- worker-only execution;
- no direct table grants;
- lease ownership and stale lease checks;
- bounded retries and maximum attempts;
- expired lease reclaim;
- idempotent identical completion;
- content-free audit.

#### Local ClamAV client

- Unix-socket `VERSION` and `INSTREAM`;
- strict response parsing;
- bounded stream;
- signature freshness gate;
- scanner unavailable/stale/protocol failure = fail closed;
- infected document rejected and enters deletion lifecycle;
- terminating INSTREAM frame only after GCM authentication;
- raw scanner output and signature names are not exposed.

#### Safe UI status

The API/UI exposes only:

```text
not_scanned
scanning
clean
infected
error
stale
```

No preview, download, rendering, OCR or Labs feature is added by C1.

#### C1 verification

CI `#414` passed:

- backend compile/Ruff/unit tests;
- frontend lint/typecheck/tests/build;
- migration boundary;
- isolated `head → base → head`;
- PostgreSQL RLS/worker negative and state-transition tests.

Final C1 verdict:

```text
MERGEABLE AND MERGED
NOT DEPLOYABLE
```

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `NEXT / NOT IMPLEMENTED`.

Required scope:

1. per-profile and global quotas;
2. reserved free-space accounting;
3. orphan and missing-object reconciliation;
4. separate render-job authorization boundary;
5. complete encrypted-source verification before parser access;
6. bounded PDF/image inspection;
7. CPU, memory, page, pixel, file-size and timeout limits;
8. encrypted safe page derivatives;
9. atomic and idempotent accepted promotion;
10. retry/failure UI states;
11. no raw PDF browser delivery;
12. no OCR in this slice;
13. independent security review.

C2 must not broaden C1 scanner functions to arbitrary future job types. Render operations require explicitly scoped functions and tests.

### Slice D — OCR candidates and human review

Status: `PLANNED AFTER C2`.

- extraction runs over safe rendered pages only;
- protected OCR artifacts;
- candidates always begin as `needs_review`;
- page-region provenance;
- field confidence;
- optimistic concurrency;
- no automatic clinical confirmation.

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

Required readiness:

- production encrypted storage and key recovery;
- worker OS/DB identities;
- hardened systemd unit;
- ClamAV/FreshClam and fresh signatures;
- reverse-proxy body limit;
- bounded private multipart spool;
- quota/reconciliation readiness;
- safe-renderer package/version evidence;
- exact-SHA CI;
- backup-first migrations;
- worker privilege probes;
- clean/EICAR/malformed-file probes;
- no-sensitive-log verification;
- disposable-document owner smoke;
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

1. Merge C1 status documentation.
2. Recheck current `main`, Alembic heads and open migration PRs.
3. Create a dedicated C2 branch.
4. Implement quota and reconciliation controls before rendering.
5. Define a separate render-worker database boundary.
6. Implement complete authentication before parser access.
7. Add bounded safe rasterization and encrypted derivatives.
8. Run exact-head CI and independent security review.
9. Keep production upload disabled.
10. Do not create a deployment task yet.

## 9. C2 stop conditions

Do not merge or deploy if:

- storage is public or inside web/release paths;
- key or plaintext enters Git, `.env`, database or persistent temp storage;
- renderer can claim scanner or unrelated future jobs;
- worker has broad table access;
- raw PDF reaches the browser;
- parser lacks CPU, memory, page, pixel, file-size or timeout limits;
- quota/free-space gates are absent;
- orphan/missing-object reconciliation is absent;
- derivatives are not encrypted;
- accepted promotion is not atomic/idempotent;
- filenames, paths, scanner/parser output or medical content enter ordinary logs;
- migration has multiple heads;
- exact-head CI or negative PostgreSQL tests are missing;
- production upload is enabled before controlled rollout approval.

## 10. Status terminology

`DEFINED`, `IMPLEMENTED`, `MERGED`, `VERIFIED` and `DEPLOYED` are separate states and must never be used interchangeably.
