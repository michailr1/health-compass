# Health Compass — текущее состояние

Дата: 2026-07-12  
Основная ветка: `main`  
Repository application baseline: `2ad0ca47d994472201c218b3e6af37145cbacdec`  
Repository Alembic head: `0057`  
Production URL: `https://health.funti.cc`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Текущий verdict: `SLICE E1 MERGED / CI VERIFIED / NOT DEPLOYED; E2 NOT IMPLEMENTED`

## Production boundary

```text
DOCUMENT_UPLOAD_ENABLED=false
```

Repository and production intentionally differ:

```text
repository: 2ad0ca47... / Alembic 0057
production: b8e86882... / Alembic 0049
```

Migrations `0050–0057`, encrypted document storage, scanner, renderer, reconciler and OCR workers, quotas, safe rendering, OCR review and source-preserving Lab drafts have not been deployed. Confirmed Lab observations do not exist. No HC-017 VPS rollout task has been issued.

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

```text
PR: #56
verified head: dc28e9e220dd51264e6dab1244ce8d8696f501b2
merge: a33c3d515b885c6ea0e8f51291a1d25bed77cd7d
CI: #442
migration: 0054
```

Provides local bounded Tesseract, encrypted OCR provenance and owner/edit-only `needs_review` candidates. It creates no clinical or Lab facts.

### D2 — Human Review and Patient Matching

```text
PR: #58
verified head: 4ecae1fb0816803b2d858db1f5016bce589544d5
merge: f67a1128e29a1c62e8a3b27dd20c973df82947ad
CI: #454
migration: 0055
```

Provides explicit candidate review, optimistic concurrency, patient decisions and manifest-bound finalization. Finalized transcription remains source text, not a clinical fact.

## HC-017 Slice E — Confirmed Labs Core

Canonical contract:

```text
docs/implementation/HC-017-SLICE-E-CONFIRMED-LABS-CORE.md
```

Architecture review:

```text
docs/reviews/HC-017-SLICE-E-ARCHITECTURE-REVIEW-2026-07-12.md
```

### E1 — Source-preserving Lab drafts

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #61
verified head: 419386e909207ab67921c008e210c059aba6658c
merge: 2ad0ca47d994472201c218b3e6af37145cbacdec
CI: #477
migrations: 0056–0057
```

Implemented:

- owner/edit-only Lab drafts and exact OCR-candidate source manifests;
- FORCE RLS and no direct runtime mutation grants;
- explicit numeric, text and qualitative value kinds;
- source analyte, value, unit, range, date, specimen, flag and comment preservation;
- explicit unknown/not-present decisions;
- current document, finalized OCR review and patient-decision timestamps on every mutation;
- active health-data consent rechecked on create, update, source replacement and status transitions;
- optimistic concurrency and content-free audit;
- minimal Lab draft API and UI;
- no confirmed observations, normalization, interpretation or metric dynamics.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-E1-LAB-DRAFTS-EVIDENCE-2026-07-12.md
```

### E2 — Explicit confirmation

Status: `NEXT / NOT IMPLEMENTED / NOT DEPLOYED`.

E2 must introduce a separate atomic and idempotent confirmation transaction and immutable confirmed observations. An E1 draft in `ready` state remains non-clinical and invisible to `view`, `analyze`, analytics and AI interpretation.

## Next allowed work

```text
HC-017 Slice E2 — Confirmed observations implementation contract and security review
```

Before E2 code:

1. independently review the exact E1 diff and migrations `0056–0057`;
2. freeze immutable observation/source snapshot fields;
3. define explicit confirmation acknowledgements, including `not_present` profile assignment;
4. define idempotency and duplicate-submission behavior;
5. define owner/edit confirmation and confirmed-only read matrix;
6. define correction, void and erasure without in-place value mutation;
7. keep every worker unable to confirm observations;
8. prove E2 cannot consume stale draft/document/OCR/patient/source versions;
9. keep production upload disabled and issue no VPS task.

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
- hostile-file and resource-limit probes;
- backup/restore behavior;
- no-sensitive-log verification;
- explicit controlled rollout approval.

## Stop conditions

Stop merge or rollout when:

- OCR or a ready draft creates a confirmed observation automatically;
- patient decision is unknown or mismatch;
- source wording/value/unit/range is not preserved;
- unit conversion or canonical mapping is silent;
- confirmed observation lacks exact document/page/candidate provenance;
- confirmed source/value fields can be edited in place;
- drafts are visible to view/analyze;
- analyze can access OCR text;
- app or worker roles receive broad mutation privileges;
- duplicate-looking observations are silently merged;
- source erasure leaves unsupported sole-provenance observations;
- audit/logs contain medical text or values;
- Alembic has multiple heads;
- exact-head CI or negative PostgreSQL tests are missing;
- production upload is enabled before controlled rollout approval.
