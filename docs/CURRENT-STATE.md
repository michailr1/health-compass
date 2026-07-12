# Health Compass — текущее состояние

Дата: 2026-07-12  
Основная ветка: `main`  
Repository application baseline: `a33c3d515b885c6ea0e8f51291a1d25bed77cd7d`  
Repository Alembic head: `0054`  
Production URL: `https://health.funti.cc`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Текущий verdict: `D1 MERGED / CI VERIFIED / NOT DEPLOYED / D2 NEXT`

## Production boundary

```text
DOCUMENT_UPLOAD_ENABLED=false
```

Repository and production intentionally differ:

```text
repository: a33c3d51... / Alembic 0054
production: b8e86882... / Alembic 0049
```

Migrations `0050–0054`, encrypted document storage, scanner, renderer, reconciler and OCR workers, quotas, safe rendering and OCR candidates have not been deployed. No HC-017 VPS rollout task has been issued.

## Production capabilities

Production currently provides:

- Google OIDC and Email Magic Links;
- PostgreSQL sessions;
- workspace/profile permissions and FORCE RLS;
- Basic Health Profile and weight history;
- consent, provenance and audit;
- Clinical Context and review states;
- contextual intake;
- Russian-first Clinical Dictionaries;
- owner-controlled permanent clinical-record erasure.

Production does not provide:

- document upload or document storage;
- malware scanning;
- safe rendering;
- document preview or download;
- OCR;
- OCR review;
- Labs observations;
- metric dynamics.

## HC-017 repository slices

### Slice A — Architecture

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

Provides document metadata, durable jobs, FORCE RLS, bounded PDF/JPEG/PNG intake, pre-parser request limits, rollback cleanup and metadata/status UI.

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #51
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

Provides HCENC1 AES-GCM objects, encrypted quarantine storage, local ClamAV, scanner freshness checks and a dedicated NOBYPASSRLS scanner role with restricted functions.

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #53
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
migrations: 0052–0053
```

Provides:

- race-safe profile/global quotas;
- canonical current source reference;
- encrypted safe-page artifacts;
- dedicated renderer and reconciler NOBYPASSRLS roles;
- full GCM verification before parser access;
- sealed memory input/output;
- fixed bounded rendering commands;
- strict PNG validation;
- atomic accepted promotion;
- orphan and missing-object reconciliation.

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

## HC-017 Slice D — OCR Candidates and Human Review

Status: `D1 IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED; D2 NEXT`.

Canonical contract:

```text
docs/implementation/HC-017-SLICE-D-OCR-CANDIDATES-AND-HUMAN-REVIEW.md
```

### D1 — Local OCR Candidate Extraction

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #56
verified head: dc28e9e220dd51264e6dab1244ce8d8696f501b2
merge: a33c3d515b885c6ea0e8f51291a1d25bed77cd7d
CI: #442
migration: 0054
```

Implemented:

- `document_ocr_runs`, encrypted OCR provenance and review candidates;
- FORCE RLS on every OCR table;
- separate `health_compass_ocr_worker LOGIN NOBYPASSRLS`;
- no direct OCR-worker table grants;
- renderer-only queueing and OCR-worker-only job functions;
- local Tesseract over current C2 safe pages only;
- complete GCM verification and PNG validation before OCR;
- sealed read-only input and bounded output memfds;
- fixed `--oem 1`, approved PSM allowlist and exact `rus+eng` traineddata provenance;
- strict TSV parsing and deterministic candidate aggregation;
- every candidate starts as `needs_review`;
- candidate text visible only to owner/edit;
- OCR status and candidate-read APIs;
- zero automatic Clinical Context, body measurement or Labs creation.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-D1-OCR-CANDIDATES-EVIDENCE-2026-07-12.md
```

### D2 — Human Review and Patient Matching

Status: `NEXT / NOT IMPLEMENTED / NOT DEPLOYED`.

Required scope:

- accept, edit, reject and defer candidate actions;
- owner/edit authorization and health-data consent;
- `expected_updated_at` optimistic concurrency;
- explicit patient match, mismatch and not-present decisions;
- candidate-manifest-bound atomic review finalization;
- content-free audit;
- accessible review UI;
- no Clinical Context, measurement or Labs creation.

## Remaining production blockers

Before any document rollout:

- production encryption credentials, recovery and rotation;
- private storage and bounded temporary-spool directories;
- dedicated scanner/renderer/reconciler/OCR OS users;
- hardened systemd units;
- verified Poppler, ImageMagick, Tesseract and traineddata versions;
- ClamAV/FreshClam health;
- reverse-proxy body limit;
- measured quotas and disk reserve;
- clean, EICAR, malformed, password, timeout and resource probes;
- backup/restore behavior;
- no-sensitive-log verification;
- explicit controlled rollout approval.

## Next allowed work

```text
HC-017 D2 — Human Review and Patient Matching
```

Implementation sequence:

1. recheck `main`, open PRs and Alembic heads;
2. reserve the next free migration;
3. define restricted review and patient-decision functions first;
4. enforce owner/edit, consent and optimistic concurrency;
5. bind finalization to an unchanged candidate manifest;
6. add content-free audit and accessible UI;
7. prove that no clinical or Labs facts are created;
8. run exact-head backend/frontend/migration/PostgreSQL gates;
9. perform an independent D2 review;
10. keep production upload disabled and issue no VPS rollout task.

## Stop conditions

Stop merge or rollout when:

- OCR or review receives raw PDF or unauthenticated bytes;
- arbitrary OCR command options are accepted;
- OCR output is unbounded;
- OCR or reviewed text appears in ordinary logs;
- candidate text is visible to view/analyze;
- any worker has broad table privileges;
- candidates begin accepted;
- optimistic concurrency is absent;
- patient matching is inferred automatically;
- D1/D2 creates clinical or Labs facts;
- Alembic has multiple heads;
- exact-head CI or negative PostgreSQL tests are missing;
- production upload is enabled before controlled rollout approval.
