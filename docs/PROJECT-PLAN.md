# Health Compass — канонический план проекта

Версия: 1.7  
Дата: 2026-07-12  
Основная ветка: `main`

Этот документ — живой план проекта. Статусы implementation, merge и production deployment всегда разделяются.

## 1. Цель

Создать защищённый многопользовательский портал персонального здоровья, объединяющий профиль, клинический контекст, лабораторные результаты, документы, носимые устройства и AI-помощника с обязательной опорой на источники и медицинские ограничения.

## 2. Приоритет источников

1. Код, migrations и automated tests.
2. Подтверждённое production state.
3. ADR и `docs/SECURITY-INVARIANTS.md`.
4. Канонические Markdown documents.
5. Исходные PDF/XLSX/PPTX и внешние reviews.

Ключевые implementation documents:

- `docs/implementation/HC-015-CODE-REVIEW-REMEDIATION.md`;
- `docs/implementation/HC-015-PRODUCTION-EVIDENCE-2026-07-11.md`;
- `docs/implementation/HC-016-CLINICAL-RECORD-ERASURE.md`;
- `docs/implementation/HC-016-PRODUCTION-ACCEPTANCE-2026-07-12.md`;
- `docs/implementation/HC-017-DOCUMENTS-OCR-LABS-FOUNDATION.md`;
- `docs/implementation/HC-017-SLICE-B-IMPLEMENTATION-2026-07-12.md`.

## 3. Основные принципы

- Security first.
- PostgreSQL RLS — основная tenant boundary.
- Runtime role остаётся `NOBYPASSRLS`.
- Никакого Authentik, Keycloak или внешнего IAM для MVP.
- Direct Google OIDC и Email Magic Links.
- Verified email не объединяет аккаунты автоматически.
- Медицинские данные требуют consent, provenance и audit.
- Free text не переписывается молча.
- OCR/AI output не становится фактом без human confirmation.
- Никаких автоматических диагнозов, назначений или расчёта доз.
- Human и Pet contours разделены.
- Каждый production rollout — backup-first и exact-SHA.
- Destructive operations используют least privilege, explicit confirmation и optimistic concurrency.
- Documents являются untrusted input и проходят quarantine before processing.
- Raw documents, OCR drafts и confirmed observations имеют разные access boundaries.

## 4. Current repository and production state

Repository:

```text
main: ccabab77cf929456a74b69c3478c71f92f167f78
Alembic head: 0050
```

Production:

```text
URL: https://health.funti.cc
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
```

Current verdict:

```text
HC-017 SLICE B MERGED / NOT DEPLOYED
```

Production document upload remains unavailable and must remain disabled.

## 5. Completed platform phases

### PHASE-01 — Base platform and production

Status: `COMPLETED`.

- FastAPI + React/Vite;
- PostgreSQL + Alembic;
- HTTPS production;
- health checks, systemd and release process;
- exact-SHA deployment and rollback discipline.

### PHASE-02 — Identity, sessions and tenant isolation

Status: `COMPLETED / NON-BLOCKING HARDENING REMAINS`.

- Google OIDC with PKCE, state and nonce;
- scanner-safe Email Magic Link consume;
- PostgreSQL sessions;
- workspace/profile bootstrap;
- FORCE RLS;
- dedicated RLS definer role;
- account linking and duplicate resolution;
- POST logout and origin validation;
- structured logging and query redaction;
- Safari Magic Link hotfix.

### PHASE-02.5 — Progressive Health Intake

Status: `CORE SLICES DEPLOYED`.

Path:

```text
Login
→ minimal onboarding
→ Empty Dashboard
→ voluntary Health Profile
→ Clinical Context
→ contextual prompts
→ confirmed document import
```

Implemented:

- Basic Health Profile;
- weight history;
- consent, provenance and audit;
- Clinical Context;
- review states;
- contextual intake;
- Clinical Dictionaries v2;
- owner-controlled permanent erasure for clinical records.

### PHASE-02.7 — HC-015 remediation

Status: `DEPLOYED / VERIFIED`.

Closed blocking review findings in routing, duplicate resolution, Magic Links, dictionary integrity, concurrency, logging, privileges and CI.

### PHASE-02.8 — HC-016 record erasure

Status: `DEPLOYED / MANUALLY ACCEPTED`.

- owner-only permanent erasure;
- no direct clinical DELETE grant;
- value-bearing audit scrubbing;
- content-free tombstone;
- explicit irreversible confirmation.

## 6. PHASE-03 — Human Documents, OCR and Labs

Status: `IN PROGRESS`.

Target flow:

```text
Upload analysis
→ quarantine
→ malware and format validation
→ safe rendering
→ OCR
→ human review
→ explicit confirmation
→ Lab Results
→ Metric Dynamics
```

### HC-017 Slice A — Architecture and contracts

Status: `MERGED` through PR `#47`.

Defined:

- threat model;
- quarantine and scanner behavior;
- storage boundary;
- access matrix;
- worker boundary;
- proposed schema;
- OCR review contract;
- patient matching;
- provenance;
- deletion lifecycle;
- logging and rollout gates.

### HC-017 Slice B — Secure Document Intake Foundation

Status: `IMPLEMENTED / MERGED / NOT DEPLOYED` through PR `#48`.

Verified head:

```text
46c5ea89d35cc85be0af3b80a9c56f40d5705ac5
```

Merge commit:

```text
ccabab77cf929456a74b69c3478c71f92f167f78
```

CI:

```text
#402 — passed
```

Implemented:

- migration `0050`;
- document metadata and intake-job tables;
- FORCE RLS and permission matrix;
- analyze exclusion from raw-document metadata;
- private development/test quarantine adapter;
- PDF/JPEG/PNG validation;
- pre-parser request limit;
- opaque storage keys;
- rollback cleanup;
- capabilities/upload/list/detail APIs;
- minimal Documents UI;
- migration-cycle and RLS regression tests.

Production restrictions:

- no rollout;
- no production storage;
- no scanner;
- no preview/download;
- no worker;
- no OCR;
- no Labs data;
- `DOCUMENT_UPLOAD_ENABLED=false`;
- production startup rejects enablement.

### HC-017 Slice C — Scanner and Safe Rendering

Status: `NEXT / NOT IMPLEMENTED`.

Prerequisites:

1. independent security review of Slice B;
2. production private-storage decision;
3. malware-scanner decision;
4. worker-role and credential design;
5. bounded PDF inspection and rasterization threat model;
6. current-main and Alembic-head verification.

Planned scope:

- private production object storage;
- malware scanner with fail-closed behavior;
- restricted worker role;
- job leases and retries;
- PDF structure/page validation;
- safe rasterized derivatives;
- accepted-object promotion;
- failure and retry UI;
- no OCR confirmation yet.

### HC-017 Slice D — OCR candidates and review

Status: `PLANNED`.

- extraction runs;
- protected OCR artifacts;
- candidates always `needs_review`;
- page-region review UI;
- confidence and validation;
- optimistic concurrency;
- no automatic confirmation.

### HC-017 Slice E — Confirmed Labs core

Status: `PLANNED`.

- atomic confirmation;
- patient matching;
- source-preserving values and units;
- provenance-linked lab observations;
- document-linked deletion lifecycle.

### HC-017 Slice F — Metric dynamics

Status: `PLANNED`.

- compatible numeric series;
- chart plus table;
- source-specific ranges;
- provenance links;
- no medical interpretation.

### HC-017 Slice G — Production rollout

Status: `PLANNED AFTER SECURITY REVIEW`.

- storage/scanner readiness evidence;
- exact-SHA CI;
- backup-first migration;
- tenant/worker privilege checks;
- disposable-document owner smoke;
- canonical production evidence.

## 7. Later phases

### PHASE-04 — Data sources and integrations

Status: `PLANNED`.

- Oura;
- laboratory CSV/PDF expansion;
- Apple Health / Health Connect after ADR;
- idempotent sync and freshness.

### PHASE-05 — Timeline and analytics

Status: `PLANNED`.

- unified timeline;
- sleep/activity/weight/lab trends;
- personal baseline;
- Attention Inbox;
- search.

### PHASE-05.5 — Nutrition Photo MVP

Status: `PLANNED AFTER LABS CORE`.

### PHASE-06 — Shared access

Status: `PLANNED`.

- invitations;
- owner/edit/view/analyze lifecycle;
- revoke and audit;
- RLS matrix.

### PHASE-07 — Privacy and data lifecycle

Status: `FOUNDATION STARTED`.

Implemented:

- consent;
- provenance/audit;
- clinical void;
- clinical permanent erasure.

Planned:

- document raw/derived/confirmed deletion;
- account export;
- profile/user deletion;
- retention center;
- active sessions;
- external-processing consent.

### PHASE-08 — AI Health Assistant

Status: `PLANNED`.

- retrieval-grounded answers;
- evidence/citations;
- Fact / Interpretation / Recommendation separation;
- red-flag routing;
- no diagnosis or dose calculation;
- prompt-injection tests.

### PHASE-09 — Product expansion

Status: `BACKLOG`.

- family profiles;
- Pet Health contour;
- clinician/caregiver workflows;
- Offline Emergency Card;
- subscriptions;
- mobile/PWA.

## 8. Immediate plan

1. Merge the Slice B status documentation.
2. Perform independent Slice B security review.
3. Compare production storage options and select one.
4. Select and threat-review malware scanner.
5. Define worker provisioning and restricted credentials.
6. Define safe PDF inspection/rasterization resource limits.
7. Recheck `main`, open PRs and Alembic head.
8. Create a separate HC-017 Slice C implementation branch.
9. Keep production unchanged until Slice C and a later controlled rollout are approved.

## 9. Slice C merge and rollout gates

Do not merge or deploy if:

- storage is public or in the web root;
- storage keys include filenames or medical values;
- scanner is missing, stubbed or fail-open;
- scanner outage permits acceptance or OCR;
- worker uses app/migrator credentials;
- worker can enumerate arbitrary profiles;
- raw PDF is embedded directly in the browser;
- page, CPU, memory or timeout limits are absent;
- accepted-object promotion is not atomic and idempotent;
- signed URLs or object keys appear in logs;
- cross-profile access is possible;
- document contents or medical values appear in ordinary logs;
- migration has multiple heads;
- exact-head CI or PostgreSQL negative tests are missing;
- production upload is enabled before the approved rollout slice.

## 10. Documentation rule

After each implementation, review, merge or rollout update:

- `docs/CURRENT-STATE.md`;
- this plan;
- corresponding implementation/evidence document;
- `docs/source-index/SOURCE-REGISTER.md`;
- dated change record;
- security invariants when rules change.

`VERIFIED`, `MERGED` and `DEPLOYED` are separate statuses and must never be used interchangeably.
