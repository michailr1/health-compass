# Health Compass — текущее состояние

Дата: 2026-07-12  
Основная ветка: `main`  
Repository application baseline: `f67a1128e29a1c62e8a3b27dd20c973df82947ad`  
Repository Alembic head: `0055`  
Production URL: `https://health.funti.cc`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Текущий verdict: `D2 MERGED / CI VERIFIED / NOT DEPLOYED / SLICE E NEXT`

## Production boundary

```text
DOCUMENT_UPLOAD_ENABLED=false
```

Repository and production intentionally differ:

```text
repository: f67a1128... / Alembic 0055
production: b8e86882... / Alembic 0049
```

Migrations `0050–0055`, encrypted document storage, scanner, renderer, reconciler and OCR workers, quotas, safe rendering, OCR candidates and human-review flows have not been deployed. No HC-017 VPS rollout task has been issued.

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

Provides:

- OCR runs, encrypted provenance and candidates;
- separate OCR worker without direct table grants;
- authenticated safe-page input and bounded local Tesseract;
- strict TSV parsing;
- owner/edit-only candidate text;
- every candidate starts as `needs_review`;
- no automatic clinical or Labs facts.

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

Implemented:

- accept, edit, reject and defer candidate actions;
- owner/edit authorization and active health-data consent;
- candidate, document and patient-decision optimistic concurrency;
- explicit `match`, `mismatch`, `not_present` and `unknown` decisions;
- exact candidate-manifest finalization;
- mismatch, unresolved and deferred blocking;
- idempotent repeated finalization;
- content-free audit;
- revisable decisions until finalization;
- accessible review UI;
- zero Clinical Context, measurement or Labs creation.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-D2-HUMAN-REVIEW-EVIDENCE-2026-07-12.md
```

## Next stage — HC-017 Slice E

Status: `NEXT / ARCHITECTURE NOT YET DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`.

```text
Confirmed Labs Core
```

Required architecture decisions before implementation:

1. define a separate explicit confirmation transaction after finalized D2 transcription;
2. preserve original analyte wording, value, unit and reference range;
3. link every observation to document, OCR run, candidate/page provenance and confirmer;
4. prohibit silent unit conversion, terminology normalization or interpretation;
5. reject patient mismatch and stale D2 review manifests;
6. define duplicate/import idempotency and correction lifecycle;
7. define owner/edit/view/analyze access matrix for confirmed Labs;
8. add deletion propagation from source document to confirmed observations;
9. create no diagnosis, recommendation or dose calculation;
10. complete an architecture/security review before code.

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
HC-017 Slice E — Confirmed Labs Core architecture
```

No Slice E code or production deployment should begin before its data, privilege, provenance, confirmation, correction and deletion contracts are reviewed and merged.

## Stop conditions

Stop merge or rollout when:

- reviewed OCR is treated as a clinical fact automatically;
- patient matching is inferred rather than explicit;
- original wording/value/unit/range is overwritten silently;
- confirmed observation lacks source/page/candidate provenance;
- app or worker roles receive broad table privileges;
- optimistic concurrency or idempotency is absent;
- audit contains document or medical text;
- deletion does not cover source, derivatives, OCR and confirmed observations;
- Alembic has multiple heads;
- exact-head CI or negative PostgreSQL tests are missing;
- production upload is enabled before controlled rollout approval.
