# Health Compass — текущее состояние

Дата: 2026-07-13  
Основная ветка: `main`  
Repository application baseline: `1d61331194edf0f78b94a304d27ccf31dfa2a755`  
Repository Alembic head: `0058`  
Production URL: `https://health.funti.cc`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## Current verdict

```text
HC-015 DEPLOYED / VERIFIED
HC-016 DEPLOYED / MANUALLY ACCEPTED
HC-017 B+C1+C2+D1+D2+E1+E2 MERGED / CI VERIFIED / NOT DEPLOYED
HC-017 E3 NEXT / NOT IMPLEMENTED
PRODUCTION DOCUMENT UPLOAD DISABLED
```

Repository and production intentionally differ:

```text
repository: 1d613311... / Alembic 0058
production: b8e86882... / Alembic 0049
DOCUMENT_UPLOAD_ENABLED=false
```

No HC-017 VPS rollout has been authorized.

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
- malware scanning or safe rendering;
- OCR or OCR review;
- Lab drafts or confirmed Lab observations;
- metric dynamics.

## HC-017 repository status

### Slice A — Documents/OCR/Labs architecture

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

Provides document metadata, FORCE RLS, bounded PDF/JPEG/PNG intake, opaque quarantine keys, document API/UI and fail-safe production disablement.

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #51
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

Provides authenticated encrypted objects, protected key-file loading, ClamAV scanning, a separate NOBYPASSRLS scanner role and restricted worker functions.

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #53
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
migrations: 0052–0053
```

Provides transaction-safe quotas, encrypted safe-page artifacts, separate renderer/reconciler roles, complete GCM verification, sealed-memory parsing, bounded rendering and storage reconciliation.

Combined C1+C2 review verdict:

```text
ACCEPT FOR REPOSITORY FOUNDATION
NO UNRESOLVED CRITICAL OR HIGH FINDING
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

### Slice D1 — Local OCR Candidate Extraction

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #56
verified head: dc28e9e220dd51264e6dab1244ce8d8696f501b2
merge: a33c3d515b885c6ea0e8f51291a1d25bed77cd7d
CI: #442
migration: 0054
```

Provides bounded local Tesseract, encrypted TSV provenance and owner/edit-only review candidates. OCR creates no clinical or Lab facts.

### Slice D2 — Human OCR Review and Patient Matching

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #58
verified head: 4ecae1fb0816803b2d858db1f5016bce589544d5
merge: f67a1128e29a1c62e8a3b27dd20c973df82947ad
CI: #454
migration: 0055
```

Provides accept/edit/reject/defer review, optimistic concurrency, explicit patient decisions and manifest-bound finalization. Finalized OCR remains source transcription, not a clinical fact.

### Slice E1 — Source-preserving Lab Drafts

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #61
verified head: 419386e909207ab67921c008e210c059aba6658c
merge: 2ad0ca47d994472201c218b3e6af37145cbacdec
CI: #477
migrations: 0056–0057
```

Provides owner/edit-only source-preserving drafts and exact candidate manifests. Drafts preserve source analyte, value, unit, range, date, specimen, flag and comment. They remain invisible to `view`, `analyze`, analytics and AI interpretation.

### Slice E2 — Explicit Confirmation and Confirmed Observations

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #65
verified head: 55f10d311d1f39262d557fa7b60cc07060ac5590
merge: 1d61331194edf0f78b94a304d27ccf31dfa2a755
CI: #491
migration: 0058
```

Implemented:

- separate explicit confirmation action;
- immutable `lab_observations` and `lab_observation_sources`;
- owner/edit-only confirmation;
- owner/edit/view/analyze confirmed-only reads;
- no worker confirmation or direct runtime mutation grants;
- exact draft/document/review/patient/candidate version checks;
- deterministic candidate locking before source snapshot copying;
- active health-data consent recheck;
- mandatory source/profile/structured-record acknowledgements;
- additional assignment acknowledgement for `not_present`;
- one observation per source draft;
- profile-scoped idempotency and concurrent replay handling;
- content-free audit;
- separate confirmation API and UI;
- no automatic mapping, unit conversion or medical interpretation.

Final review verdict:

```text
ACCEPT FOR REPOSITORY FOUNDATION
NO UNRESOLVED CRITICAL OR HIGH FINDING
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-E2-CONFIRMED-OBSERVATIONS-EVIDENCE-2026-07-13.md
```

## Next allowed work

```text
HC-017 Slice E3 — Correction, Void and Owner-only Erasure
```

E3 must preserve confirmed source/value immutability:

- corrections create replacement observations and supersession chains;
- no confirmed value is edited in place;
- voiding is explicit and reasoned;
- owner-only permanent erasure removes observation and immutable sources atomically;
- document erasure cannot leave unsupported sole-provenance observations;
- restricted functions and negative PostgreSQL tests are required before API/UI;
- production remains unchanged.

Metric dynamics remain later than E3 and may use only active confirmed compatible numeric observations. No silent unit conversion is allowed.

## Remaining production blockers

Before any Documents/OCR/Labs rollout:

- production encryption credentials, recovery and rotation;
- private encrypted storage and bounded spool directories;
- dedicated scanner/renderer/reconciler/OCR OS users;
- hardened systemd services;
- verified Poppler, ImageMagick, Tesseract and traineddata versions;
- ClamAV/FreshClam health and current signatures;
- reverse-proxy request-body limit;
- measured profile/global quotas and disk reserve;
- hostile-file, timeout, memory and decompression-bomb probes;
- database plus encrypted-object backup/restore validation;
- no-sensitive-log verification;
- disposable document/OCR/Labs owner smoke;
- explicit controlled rollout approval.

## Stop conditions

Stop merge or rollout when:

- OCR or a ready draft creates a confirmed observation automatically;
- a worker, viewer or analyzer can confirm;
- patient decision `unknown` or `mismatch` is accepted;
- `not_present` lacks explicit profile assignment acknowledgement;
- source wording/value/unit/range or exact provenance is lost;
- stale versions can be confirmed;
- concurrent/idempotent confirmation can create duplicates;
- confirmed source/value fields can be edited in place;
- drafts or raw OCR become visible to `view`/`analyze`;
- direct broad mutation grants exist;
- source erasure can orphan a sole-provenance observation;
- medical text or values enter ordinary audit/logs;
- Alembic has multiple heads;
- exact-head CI or negative PostgreSQL tests are absent;
- production upload is enabled before controlled rollout approval.
