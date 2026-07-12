# Health Compass — текущее состояние

Дата: 2026-07-12  
Основная ветка: `main`  
Repository application baseline: `ac9e21f3315c4624a845e633c2a90881d348ca30`  
Repository Alembic head: `0053`  
Production URL: `https://health.funti.cc`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Текущий verdict: `C1+C2 REVIEW COMPLETE / SLICE D ARCHITECTURE DEFINED / NOT DEPLOYED`

## Production boundary

```text
DOCUMENT_UPLOAD_ENABLED=false
```

Repository and production intentionally differ:

```text
repository: ac9e21f3... / Alembic 0053
production: b8e86882... / Alembic 0049
```

Migrations `0050–0053`, encrypted document storage, scanner worker, quota controls, reconciliation and safe rendering have not been deployed. No VPS rollout task has been issued for HC-017.

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

- document upload or storage;
- malware scanning;
- safe rendering;
- document preview/download;
- OCR;
- extraction review;
- Labs observations;
- metric dynamics.

## HC-017 implemented repository slices

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

Implemented:

- document metadata and durable jobs;
- RLS + FORCE RLS;
- owner/edit/view metadata boundary;
- analyze exclusion from raw-document metadata;
- bounded PDF/JPEG/PNG intake;
- pre-parser request limit;
- rollback cleanup;
- content-free audit;
- metadata/status API and UI.

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

- `HCENC1` streaming AES-256-GCM objects;
- strict key-file and object-path handling;
- encrypted quarantine storage;
- local ClamAV Unix-socket client;
- scanner signature freshness gate;
- dedicated scanner NOBYPASSRLS role;
- no direct worker table grants;
- restricted claim/heartbeat/complete/fail functions;
- stale lease, retry and idempotent completion controls;
- infected-document deletion lifecycle;
- safe scanner status API/UI.

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

- profile/global quotas and transaction locks;
- canonical current source reference;
- encrypted safe-page artifacts with FORCE RLS;
- dedicated renderer and reconciler NOBYPASSRLS roles;
- exact worker execute matrices and no direct table grants;
- full GCM verification before parser access;
- sealed read-only memfd input/output;
- fixed commands without shell execution;
- CPU, memory, page, pixel, output and timeout limits;
- PDF password/page checks;
- strict PNG chunk/CRC/dimension validation;
- encrypted accepted source and page derivatives;
- atomic/idempotent accepted promotion;
- orphan and missing-object reconciliation;
- idempotent repeated missing-object handling.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-C2-SAFE-RENDERING-EVIDENCE-2026-07-12.md
```

## Combined C1+C2 security review

Status: `COMPLETE`.

Verdict:

```text
ACCEPT FOR REPOSITORY FOUNDATION
NO UNRESOLVED CRITICAL OR HIGH FINDING
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

Confirmed:

- encryption, scanner, renderer and reconciler roles are separated;
- workers have no broad table privileges;
- scanner/parser inputs fail closed;
- raw PDF is not exposed;
- safe pages are encrypted;
- quotas and reconciliation are transactionally/operationally bounded;
- audit does not contain document content;
- repository tests cover exact privilege and state transitions.

Canonical review:

```text
docs/reviews/HC-017-C1-C2-COMBINED-SECURITY-REVIEW-2026-07-12.md
```

## HC-017 Slice D — OCR Candidates and Human Review

Status: `ARCHITECTURE DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`.

Canonical contract:

```text
docs/implementation/HC-017-SLICE-D-OCR-CANDIDATES-AND-HUMAN-REVIEW.md
```

Selected direction:

- local Tesseract 5.x;
- `--oem 1` LSTM engine;
- `rus+eng` language set;
- TSV output for text, confidence and coordinates;
- OCR consumes only C2 encrypted `safe_page` artifacts;
- source is fully GCM-verified before OCR;
- sealed read-only memfd input;
- bounded OCR output memfd;
- separate `health_compass_ocr_worker LOGIN NOBYPASSRLS` role;
- no direct OCR-worker table grants;
- encrypted TSV provenance artifacts;
- strict TSV parser;
- candidates begin as `needs_review`;
- owner/edit-only candidate text;
- patient matching is a separate explicit decision;
- no automatic Clinical Context, measurement or Labs creation.

### D1 planned scope

- migration candidate `0054` after rechecking current heads;
- OCR runs/artifacts/candidates tables;
- worker claim/heartbeat/complete/fail functions;
- exact engine/language/traineddata provenance;
- bounded local Tesseract subprocess;
- encrypted TSV output;
- strict parser and candidate aggregation;
- candidate read endpoints;
- no human mutation endpoints yet.

### D2 planned scope

- accept/edit/reject/defer candidate actions;
- optimistic concurrency;
- explicit patient-match decision;
- review finalization with manifest checks;
- content-free audit;
- accessible review UI;
- still no Labs fact creation.

## Remaining production blockers

Before any document rollout:

- production encryption credentials and recovery/rotation;
- private storage and bounded temporary-spool directories;
- dedicated scanner/renderer/reconciler/OCR OS users;
- hardened systemd units;
- verified Poppler/ImageMagick/Tesseract and language-model versions;
- ClamAV/FreshClam health;
- reverse-proxy body limit;
- measured quotas and disk reserve;
- clean/EICAR/malformed/password/timeout/resource probes;
- backup/restore behavior;
- no-sensitive-log verification;
- explicit controlled rollout approval.

## Next allowed work

```text
HC-017 D1 — Local OCR Candidate Extraction
```

Before coding:

1. recheck `main`, open PRs and Alembic heads;
2. confirm migration number `0054` is free;
3. create a dedicated implementation branch;
4. implement database/worker boundary before OCR process code;
5. add unit and PostgreSQL negative tests;
6. keep production upload disabled;
7. run independent review before D2.

## Stop conditions

Stop merge or rollout when:

- OCR receives raw PDF or unauthenticated source bytes;
- OCR accepts arbitrary command options;
- OCR output is unbounded;
- OCR text appears in logs;
- candidate text is visible to view/analyze;
- OCR worker has direct table privileges;
- candidates begin as accepted;
- patient matching is inferred automatically;
- OCR creates clinical/Labs facts;
- optimistic concurrency is absent;
- Alembic has multiple heads;
- exact-head CI or negative PostgreSQL tests are missing;
- production upload is enabled before controlled rollout approval.
