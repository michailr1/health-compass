# Health Compass — Current Context Handoff

Date: 2026-07-12  
Repository: `michailr1/health-compass`  
Production: `https://health.funti.cc`  
Git main HEAD: `ab58f40d4d69a122aa5a48046a29bc5134903bdc`  
Repository application baseline: `2ad0ca47d994472201c218b3e6af37145cbacdec`  
Repository Alembic head: `0057`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Production document upload: `DOCUMENT_UPLOAD_ENABLED=false`

## 1. Purpose of this document

This file is the current handoff context for continuing Health Compass without relying on chat history.

Source-of-truth order:

1. code, migrations and automated tests;
2. confirmed production state;
3. canonical repository documentation;
4. this handoff context;
5. chat messages and external recommendations.

When this file conflicts with code or current production evidence, code and production evidence win.

## 2. Current factual verdict

```text
HC-015 DEPLOYED / VERIFIED
HC-016 DEPLOYED / MANUALLY ACCEPTED
HC-017 B+C1+C2+D1+D2+E1 MERGED / CI VERIFIED / NOT DEPLOYED
HC-017 E2 NOT IMPLEMENTED
NO CONFIRMED LAB OBSERVATIONS
PRODUCTION UNCHANGED SINCE HC-016
```

Repository and production intentionally differ:

```text
repository application baseline: 2ad0ca47... / Alembic 0057
production application:          b8e86882... / Alembic 0049
```

No HC-017 VPS rollout task has been authorized.

## 3. Production capabilities

Production currently provides:

- Google OIDC and Email Magic Links;
- PostgreSQL sessions;
- workspaces, profiles, permissions and FORCE RLS;
- Basic Health Profile and weight history;
- consent, provenance and audit;
- Clinical Context and review states;
- contextual intake;
- Russian-first Clinical Dictionaries;
- owner-controlled permanent clinical-record erasure.

Production does not provide:

- document upload or document storage;
- malware scanning or safe rendering;
- OCR or human OCR review;
- Lab drafts or confirmed Lab observations;
- metric dynamics.

## 4. Completed repository slices

### HC-017 Slice A — Architecture

Status: `MERGED` through PR `#47`.

### Slice B — Secure Document Intake Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #48
verified head: 46c5ea89d35cc85be0af3b80a9c56f40d5705ac5
merge: ccabab77cf929456a74b69c3478c71f92f167f78
CI: #402
migration: 0050
```

Implemented:

- document metadata and durable jobs;
- RLS + FORCE RLS;
- owner/edit insert and owner/edit/view metadata visibility;
- analyze excluded from raw document metadata;
- no direct runtime UPDATE or DELETE;
- PDF/JPEG/PNG validation and bounded upload;
- opaque storage keys;
- minimal documents API and UI;
- production upload remains disabled.

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #51
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

Implemented:

- streaming AES-256-GCM encrypted objects;
- protected credential-file loading;
- local ClamAV Unix-socket scanner client;
- separate scanner worker role `NOBYPASSRLS`;
- restricted claim/heartbeat/complete/fail functions;
- scanner fail-closed behavior;
- infected/invalid object deletion lifecycle.

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #53
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
migrations: 0052–0053
```

Implemented:

- transaction-serialized upload quotas;
- encrypted safe-page artifacts;
- separate renderer and reconciler roles;
- full GCM verification before parser access;
- sealed memory input/output;
- fixed-command bounded PDF/image rendering;
- strict PNG validation;
- encrypted accepted source and safe-page artifacts;
- orphan isolation and missing-reference reconciliation;
- idempotent render completion and missing-object audit.

### Slice D1 — Local OCR Candidates

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #56
verified head: dc28e9e220dd51264e6dab1244ce8d8696f501b2
merge: a33c3d515b885c6ea0e8f51291a1d25bed77cd7d
CI: #442
migration: 0054
```

Implemented:

- local bounded Tesseract over C2 safe-page artifacts;
- encrypted TSV provenance;
- strict TSV parsing and traineddata provenance;
- separate OCR worker role;
- owner/edit-only `needs_review` candidates;
- no Clinical Context, measurement or Lab facts created.

### Slice D2 — Human OCR Review and Patient Matching

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #58
verified head: 4ecae1fb0816803b2d858db1f5016bce589544d5
merge: f67a1128e29a1c62e8a3b27dd20c973df82947ad
CI: #454
migration: 0055
```

Implemented:

- owner/edit candidate actions: accept, edit, reject and defer;
- optimistic concurrency;
- explicit patient decisions: unknown, match, mismatch and not_present;
- manifest-bound finalization;
- content-free audit;
- no direct runtime mutation grants;
- finalized transcription remains source text, not a clinical fact.

### Slice E1 — Source-preserving Lab Drafts

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #61
verified head: 419386e909207ab67921c008e210c059aba6658c
merge: 2ad0ca47d994472201c218b3e6af37145cbacdec
CI: #477
migrations: 0056–0057
```

Implemented:

- `lab_observation_drafts` and exact source-manifest rows;
- owner/edit-only access with FORCE RLS;
- no direct app or worker mutation grants;
- numeric, text and qualitative value kinds;
- source analyte/value/unit/range/date/specimen/flag/comment preservation;
- explicit absence and unknown decisions;
- exact OCR candidate/source-role provenance;
- current document, D2 review, patient decision and consent gates;
- post-creation consent revocation protection;
- optimistic concurrency and content-free audit;
- API and minimal UI at `/app/documents/{document_id}/labs`.

Important invariant:

```text
A ready E1 draft is non-clinical.
It is not visible to view/analyze, analytics, AI interpretation or metric dynamics.
```

## 5. Current unfinished stage

### HC-017 Slice E2 — Explicit Confirmation and Confirmed Observations

Status:

```text
NEXT / NOT IMPLEMENTED / NOT DEPLOYED
```

E2 must introduce a separate confirmation path. It must not reuse an E1 draft mutation endpoint as implicit confirmation.

Required E2 outcome:

```text
ready source-preserving draft
→ explicit user confirmation
→ immutable confirmed observation
→ immutable source snapshot
```

Required E2 properties:

- separate immutable observation and source-snapshot tables;
- owner/edit confirmation only;
- owner/edit/view/analyze confirmed-only reads;
- workers cannot confirm observations;
- draft must be `ready`;
- current document, D2 review and patient decision must still match;
- exact draft timestamp and source manifest must still match;
- active health-data consent must still exist;
- explicit profile acknowledgement;
- explicit source/value/unit/range/date acknowledgement;
- extra profile-assignment acknowledgement for patient decision `not_present`;
- unique idempotency key and safe duplicate-submit behavior;
- one observation at most from one consumed draft;
- source wording and raw value remain immutable;
- no automatic analyte normalization or unit conversion;
- no interpretation, diagnosis, recommendation or dose calculation;
- content-free audit and no medical values in ordinary logs.

## 6. Mandatory work order for E2

Do not begin with UI or a broad observation model.

1. Independently review the exact E1 diff and migrations `0056–0057`.
2. Freeze the immutable confirmed observation/source-snapshot schema.
3. Define confirmation request acknowledgements and idempotency contract.
4. Define confirmed-only RLS and permission matrix.
5. Define correction/void/erasure boundaries without in-place mutation.
6. Recheck current `main`, Alembic heads and open migration PRs.
7. Allocate the next migration only after the recheck.
8. Create a separate E2 implementation branch.
9. Implement database tables, constraints, RLS and restricted confirmation function first.
10. Add negative PostgreSQL tests before API/UI.
11. Add API and accessible explicit-confirmation UI.
12. Run exact-head backend/frontend/full migration-cycle/PostgreSQL CI.
13. Perform an independent E2 security review before merge.
14. Keep production unchanged.

## 7. E2 stop conditions

Stop implementation or merge when:

- `ready` automatically creates an observation;
- a worker can confirm an observation;
- patient decision `unknown` or `mismatch` is accepted;
- `not_present` lacks an explicit profile-assignment acknowledgement;
- source analyte/value/unit/range/date wording is lost;
- unit conversion or canonical mapping is silent;
- stale draft/document/OCR/patient/candidate/source versions can be consumed;
- confirmation is not atomic and idempotent;
- confirmed source or value fields can be edited in place;
- view/analyze can read drafts or OCR text;
- duplicate-looking observations are silently merged;
- source-document erasure can leave an unsupported sole-provenance observation;
- app or worker roles receive broad mutation privileges;
- medical values appear in audit or ordinary logs;
- Alembic has multiple heads;
- exact-head negative PostgreSQL tests are absent.

## 8. Planned later stages

### E3 — Correction, Void and Erasure

Planned only after independent E2 review:

- correction creates a replacement observation and supersession chain;
- confirmed values are never updated in place;
- explicit void reason;
- owner-only permanent erasure;
- source-document deletion propagation;
- no orphaned sole-provenance observation.

### Slice F — Metric Dynamics

Only after confirmed observations exist:

- compatible numeric series only;
- no silent unit conversion;
- chart and accessible table;
- source-specific ranges and provenance links;
- no diagnosis or treatment advice.

### Slice G — Controlled Production Rollout

Only after all implementation and security review gates pass.

## 9. Remaining production blockers

Before any document/Labs rollout:

- production encryption credentials, recovery and rotation;
- private storage and bounded temporary-spool directories;
- dedicated scanner/renderer/reconciler/OCR OS users;
- hardened systemd units;
- verified Poppler, ImageMagick, Tesseract and traineddata versions;
- ClamAV/FreshClam health and signatures;
- reverse-proxy request-body limit;
- measured profile/global quotas and disk reserve;
- hostile-file, timeout, memory and decompression-bomb probes;
- backup and restore behavior for database plus encrypted objects;
- no-sensitive-log verification;
- explicit controlled rollout approval;
- disposable-document owner smoke.

## 10. Open pull requests requiring caution

Two old PRs remain open and are not valid current baselines:

### PR #25 — HC-013 session management

- based on a much older `main`;
- uses migration `0046`, which is already superseded by repository migrations through `0057`;
- currently not mergeable;
- do not merge as-is;
- reimplement or rebase from current `main` in a separate future task.

### PR #17 — frontend serving-path documentation

- based on a much older `main`;
- currently not mergeable;
- its operational lesson may still be valid, but the PR must not be merged as-is;
- verify current deployment documentation before closing or recreating it.

## 11. Canonical files to read first

```text
docs/CURRENT-STATE.md
docs/PROJECT-PLAN.md
docs/SECURITY-INVARIANTS.md
docs/implementation/HC-017-SLICE-E-CONFIRMED-LABS-CORE.md
docs/implementation/HC-017-SLICE-E1-LAB-DRAFTS-EVIDENCE-2026-07-12.md
docs/source-index/SOURCE-REGISTER.md
```

For previous slices:

```text
docs/implementation/HC-017-DOCUMENTS-OCR-LABS-FOUNDATION.md
docs/implementation/HC-017-SLICE-C-SCANNER-STORAGE-WORKER.md
docs/implementation/HC-017-SLICE-C2-SAFE-RENDERING-EVIDENCE-2026-07-12.md
docs/implementation/HC-017-SLICE-D-OCR-CANDIDATES-AND-HUMAN-REVIEW.md
```

## 12. First action in the next context window

```text
Perform an independent E1 diff/security review against current main.
Do not start E2 code until the immutable observation/source snapshot contract,
acknowledgements, idempotency and confirmed-only access matrix are frozen.
```

Recommended branch sequence:

```text
docs/hc-017-e1-independent-review-and-e2-contract
→ review/contract PR
→ feat/hc-017-confirmed-lab-observations
→ E2 implementation PR
→ independent E2 security review
```

## 13. Non-negotiable project rules

- Security first.
- PostgreSQL RLS is the tenant boundary.
- Runtime and worker roles remain `NOBYPASSRLS`.
- Medical data requires consent, provenance and audit.
- OCR output is not a fact.
- Reviewed transcription is not a fact.
- A ready Lab draft is not a fact.
- Only explicit E2 confirmation may create a confirmed observation.
- Confirmed source/value fields are immutable.
- Corrections create replacement records.
- No automatic diagnosis, treatment recommendation or dose calculation.
- Production rollout is backup-first and exact-SHA.
- `DEFINED`, `IMPLEMENTED`, `MERGED`, `CI VERIFIED` and `DEPLOYED` are separate states.
