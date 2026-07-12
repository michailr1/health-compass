# Health Compass — текущее состояние

Дата: 2026-07-12  
Основная ветка: `main`  
Repository application baseline: `34425d89fb205a43d8ce543862b2ab8371dabbb4`  
Repository Alembic head: `0055`  
Production URL: `https://health.funti.cc`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Текущий verdict: `SLICE E ARCHITECTURE DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`

## Production boundary

```text
DOCUMENT_UPLOAD_ENABLED=false
```

Repository and production intentionally differ:

```text
repository: 34425d89... / Alembic 0055
production: b8e86882... / Alembic 0049
```

Migrations `0050–0055`, encrypted document storage, scanner, renderer, reconciler and OCR workers, quotas, safe rendering, OCR candidates and human-review flows have not been deployed. Slice E is documentation only and adds no migration or code. No HC-017 VPS rollout task has been issued.

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

### Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #51
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

### Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #53
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
migrations: 0052–0053
```

Provides race-safe quotas, encrypted safe-page artifacts, separate renderer/reconciler roles, GCM-before-parser verification, sealed memory input/output, bounded rendering and storage reconciliation.

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

Status: `D1+D2 IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

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

Provides OCR runs, encrypted provenance, strict bounded Tesseract, deterministic `needs_review` candidates, owner/edit-only text and no automatic clinical facts.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-D1-OCR-CANDIDATES-EVIDENCE-2026-07-12.md
```

### D2 — Human Review and Patient Matching

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #58
verified head: 4ecae1fb0816803b2d858db1f5016bce589544d5
merge: f67a1128e29a1c62e8a3b27dd20c973df82947ad
CI: #454
migration: 0055
```

Provides explicit candidate review, active-consent checks, optimistic concurrency, explicit patient decisions, manifest-bound idempotent finalization, content-free audit and no automatic clinical/Labs facts.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-D2-HUMAN-REVIEW-EVIDENCE-2026-07-12.md
```

## HC-017 Slice E — Confirmed Labs Core

Status: `ARCHITECTURE DEFINED / REVIEWED / NOT IMPLEMENTED / NOT DEPLOYED`.

Canonical contract:

```text
docs/implementation/HC-017-SLICE-E-CONFIRMED-LABS-CORE.md
```

Architecture review:

```text
docs/reviews/HC-017-SLICE-E-ARCHITECTURE-REVIEW-2026-07-12.md
```

Selected architecture:

- finalized D2 transcription is eligible input, not a Lab fact;
- E1 introduces owner/edit-only source-preserving Lab drafts;
- E2 introduces a separate explicit confirmation transaction;
- original analyte, value, unit, range, date/specimen and flag text are preserved;
- parsed numeric/date/range and canonical concept remain separate fields;
- no silent unit conversion, canonical mapping or reference-range interpretation;
- one draft creates at most one immutable confirmed observation;
- exact document/OCR/candidate/patient-decision provenance is required;
- `unknown` and `mismatch` block confirmation;
- `not_present` requires an additional explicit profile-assignment acknowledgement;
- confirmed fields are never updated in place;
- corrections create replacement/supersession chains;
- document erasure removes sole-provenance drafts and observations;
- analyze receives active confirmed observations only, never drafts or OCR text;
- no worker can confirm, correct, void or erase Lab observations.

Architecture verdict:

```text
ARCHITECTURE ACCEPTED FOR FUTURE IMPLEMENTATION
NO SLICE E CODE YET
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

## Next allowed work

```text
HC-017 Slice E1 — Structured Lab Drafts implementation
```

Before implementation:

1. recheck current `main`, open migration PRs and Alembic heads;
2. assign the next free migration only then;
3. settle exact numeric precision, source-role enum and field limits;
4. implement draft/source tables with FORCE RLS;
5. implement restricted draft/source functions;
6. require current finalized D2 review, allowed patient decision, active consent and optimistic concurrency;
7. keep drafts owner/edit-only;
8. prove zero confirmed observations before E2;
9. run exact-head backend/frontend/migration/PostgreSQL gates;
10. keep production upload disabled and issue no VPS task.

## Remaining production blockers

Before any document/Labs rollout:

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

## Stop conditions

Stop merge or rollout when:

- finalized OCR creates a Lab observation automatically;
- patient decision is unknown or mismatch;
- source wording/value/unit/range is not preserved;
- unit conversion or canonical mapping is silent;
- confirmed observation lacks exact document/page/candidate provenance;
- confirmed source/value fields can be edited in place;
- draft rows are visible to view/analyze;
- analyze can access OCR text;
- app or worker roles receive broad mutation privileges;
- duplicate-looking observations are merged silently;
- document erasure leaves unsupported sole-provenance observations;
- audit/logs contain medical text or values;
- Alembic has multiple heads;
- exact-head CI or negative PostgreSQL tests are missing;
- production upload is enabled before controlled rollout approval.
