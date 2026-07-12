# Health Compass — Current HC-017 Context Handoff

Date: 2026-07-13  
Repository: `michailr1/health-compass`  
Production: `https://health.funti.cc`  
Git main application baseline: `1d61331194edf0f78b94a304d27ccf31dfa2a755`  
Repository Alembic head: `0058`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Production document upload: `DOCUMENT_UPLOAD_ENABLED=false`

## 1. Source-of-truth order

1. code, migrations and automated tests;
2. confirmed production state;
3. canonical repository documentation;
4. this handoff context;
5. chat messages and external recommendations.

When this file conflicts with current code or production evidence, code and production evidence win.

## 2. Current factual verdict

```text
HC-015 DEPLOYED / VERIFIED
HC-016 DEPLOYED / MANUALLY ACCEPTED
HC-017 B+C1+C2+D1+D2+E1+E2 MERGED / CI VERIFIED / NOT DEPLOYED
HC-017 E3 NEXT / NOT IMPLEMENTED
PRODUCTION UNCHANGED SINCE HC-016
```

Repository and production intentionally differ:

```text
repository application: 1d613311... / Alembic 0058
production application: b8e86882... / Alembic 0049
DOCUMENT_UPLOAD_ENABLED=false
```

No HC-017 VPS rollout is authorized.

## 3. Completed repository slices

| Slice | PR | Verified head | Merge | CI | Migration(s) | Status |
|---|---:|---|---|---:|---|---|
| B secure intake | #48 | `46c5ea89...` | `ccabab77...` | #402 | 0050 | merged, not deployed |
| C1 encrypted scanner | #51 | `c32e420b...` | `a0dd405c...` | #414 | 0051 | merged, not deployed |
| C2 quota/render/reconcile | #53 | `568eca1e...` | `06e4f0a2...` | #433 | 0052–0053 | merged, not deployed |
| D1 OCR candidates | #56 | `dc28e9e2...` | `a33c3d51...` | #442 | 0054 | merged, not deployed |
| D2 human review | #58 | `4ecae1fb...` | `f67a1128...` | #454 | 0055 | merged, not deployed |
| E1 Lab drafts | #61 | `419386e9...` | `2ad0ca47...` | #477 | 0056–0057 | merged, not deployed |
| E2 confirmed observations | #65 | `55f10d31...` | `1d613311...` | #491 | 0058 | merged, not deployed |

## 4. E2 implemented boundary

E2 introduces a separate explicit confirmation action:

```text
ready E1 draft
→ confirmation preview
→ mandatory acknowledgements
→ atomic source/version/consent validation
→ immutable observation
→ immutable source snapshots
→ content-free audit
```

Implemented controls:

- `lab_observations` and `lab_observation_sources`;
- ENABLE + FORCE RLS;
- owner/edit-only confirmation;
- owner/edit/view/analyze confirmed-only reads;
- no direct app mutation grants;
- no scanner/renderer/reconciler/OCR worker confirmation access;
- exact draft/document/review/patient/candidate versions;
- deterministic candidate row locks before immutable source copying;
- active consent recheck;
- base acknowledgements plus extra `not_present` assignment acknowledgement;
- profile-scoped idempotency;
- one observation per source draft;
- concurrent confirmation produces at most one observation;
- no interpretation, normalization or silent unit conversion.

Exact head `55f10d311d1f39262d557fa7b60cc07060ac5590` passed CI `#491` including backend, frontend, migration boundary, full `head → base → head`, PostgreSQL RLS, provenance, stale-source, consent, idempotency and concurrency tests.

## 5. Current unfinished stage

### HC-017 Slice E3 — Correction, Void and Owner-only Erasure

Status:

```text
NEXT / NOT IMPLEMENTED / NOT DEPLOYED
```

Required E3 outcome:

- correction creates a new immutable replacement observation;
- supersession chain preserves the prior record and provenance;
- voiding is explicit, reasoned and does not rewrite source/value fields;
- owner-only permanent erasure removes observation and source snapshots atomically;
- source-document erasure cannot leave a sole-provenance observation;
- view/analyze access to voided/superseded records follows an explicit contract;
- audit remains content-free.

## 6. Mandatory work order for E3

1. Recheck current `main`, Alembic heads and open migration PRs.
2. Independently review migration `0058` and the E2 confirmation function.
3. Freeze correction/supersession/void/erasure state model.
4. Define exact RLS and permission matrix.
5. Define document deletion propagation and transaction order.
6. Allocate the next migration only after the recheck.
7. Create a separate E3 implementation branch from current `main`.
8. Implement database constraints and restricted functions first.
9. Add negative PostgreSQL tests before API/UI.
10. Add correction/void/erasure API and accessible UI.
11. Run exact-head backend/frontend/full migration/PostgreSQL CI.
12. Perform independent E3 threat review.
13. Keep production unchanged.

## 7. E3 stop conditions

Stop implementation or merge when:

- a confirmed source/value field is updated in place;
- correction loses the prior observation or exact provenance;
- supersession can form an invalid or cyclic chain;
- non-owner permanent erasure is possible;
- void/erasure is not atomic;
- document deletion can orphan an observation;
- a worker receives mutation access;
- view/analyze can read states contrary to the approved matrix;
- medical values appear in audit or ordinary logs;
- Alembic has multiple heads;
- exact-head negative PostgreSQL tests are absent.

## 8. Later stages

### Slice F — Metric Dynamics

Only after E3 review:

- active confirmed numeric observations only;
- compatible units only;
- no silent conversion;
- accessible table and chart;
- source-specific ranges and provenance links;
- no diagnosis or treatment advice.

### Slice G — Controlled Production Rollout

Only after all repository, security, host, backup/restore and hostile-file gates pass.

## 9. Remaining production blockers

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
- no-sensitive-log verification;
- disposable document/OCR/Labs owner smoke;
- explicit controlled rollout approval.

## 10. Open PRs requiring caution

Two old PRs remain invalid current baselines:

- PR `#25` — HC-013 session management, based on obsolete migration `0046`; do not merge as-is.
- PR `#17` — old frontend serving-path documentation; verify and recreate from current main if still needed.

## 11. Canonical files to read first

```text
docs/CURRENT-STATE.md
docs/PROJECT-PLAN.md
docs/SECURITY-INVARIANTS.md
docs/implementation/HC-017-SLICE-E-CONFIRMED-LABS-CORE.md
docs/implementation/HC-017-SLICE-E2-CONFIRMED-OBSERVATIONS.md
docs/implementation/HC-017-SLICE-E2-CONFIRMED-OBSERVATIONS-EVIDENCE-2026-07-13.md
docs/source-index/SOURCE-REGISTER.md
```

## 12. Exact first action in the next context

```text
Fetch current main and open PRs.
Verify Alembic has one head at 0058.
Review migration 0058 and app_confirm_lab_observation.
Start E3 database contract from current main.
Do not deploy.
```
