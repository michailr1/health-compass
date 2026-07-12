# HC-017 Slice E — Confirmed Labs Core

Status: `E1+E2 IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED; E3 NEXT`  
Created: 2026-07-12  
Updated: 2026-07-13  
Current repository main: `1d61331194edf0f78b94a304d27ccf31dfa2a755`  
Repository Alembic head: `0058`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## 1. Goal

Create source-preserving confirmed laboratory observations from finalized Slice D transcription through two separate user-controlled stages:

```text
finalized OCR transcription
→ E1 source-preserving Lab draft
→ exact source-fragment manifest
→ E2 explicit confirmation
→ immutable confirmed observation
→ later metric dynamics
```

Slice E is not an OCR parser or medical interpretation engine. Reviewed source text is structured in E1 and becomes a clinical observation only through the separate E2 confirmation transaction.

## 2. Core invariants

```text
FINALIZED OCR TRANSCRIPTION IS SOURCE, NOT A LAB FACT
READY LAB DRAFT IS SOURCE-PRESERVING INPUT, NOT A CONFIRMED OBSERVATION
ONLY EXPLICIT OWNER/EDITOR E2 CONFIRMATION CREATES AN OBSERVATION
CONFIRMED SOURCE/VALUE FIELDS ARE IMMUTABLE
```

No background worker, parser, dictionary or AI model may create a confirmed observation.

## 3. Slice decomposition

### E1 — Source-preserving Lab Drafts

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #61
verified head: 419386e909207ab67921c008e210c059aba6658c
merge: 2ad0ca47d994472201c218b3e6af37145cbacdec
CI: #477
migrations: 0056–0057
```

Implemented:

- owner/editor draft creation from current finalized D2 transcription;
- exact OCR candidate source roles and versions;
- source wording preserved separately from parsed values;
- numeric, text and qualitative value kinds;
- explicit unit, range and date absence/unknown states;
- document, OCR review, patient decision and consent checks on every mutation;
- optimistic concurrency;
- FORCE RLS and owner/edit-only draft visibility;
- no automatic confirmed observation.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-E1-LAB-DRAFTS-EVIDENCE-2026-07-12.md
```

### E2 — Explicit Confirmation and Confirmed Observations

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #65
verified head: 55f10d311d1f39262d557fa7b60cc07060ac5590
merge: 1d61331194edf0f78b94a304d27ccf31dfa2a755
CI: #491
migration: 0058
```

Implemented:

- separate confirmation preview and action;
- immutable observation and source-snapshot tables;
- atomic validation of current document, D2 review, patient decision, draft and source manifest;
- owner/edit-only confirmation;
- owner/edit/view/analyze confirmed-only reads;
- mandatory acknowledgements;
- extra profile-assignment acknowledgement for `not_present`;
- profile-scoped idempotency and concurrent replay handling;
- candidate row locking before immutable source copying;
- active consent recheck;
- one observation per source draft;
- content-free audit;
- no automatic interpretation, canonical mapping or unit conversion.

Canonical contract and evidence:

```text
docs/implementation/HC-017-SLICE-E2-CONFIRMED-OBSERVATIONS.md
docs/implementation/HC-017-SLICE-E2-CONFIRMED-OBSERVATIONS-EVIDENCE-2026-07-13.md
```

### E3 — Correction, Void and Erasure

Status: `NEXT / NOT IMPLEMENTED / NOT DEPLOYED`.

Required:

- confirmed source/value fields are never updated in place;
- correction creates a replacement observation and supersession chain;
- void preserves provenance and an explicit reason;
- owner-only permanent erasure removes observation and immutable sources atomically;
- source-document erasure cannot leave an unsupported sole-provenance observation;
- negative PostgreSQL tests precede API/UI.

## 4. Source-preserving data principles

The following source fields remain separate from structured representations:

- `source_analyte_text`;
- `source_value_text`;
- `source_unit_text` or explicit absence;
- `source_reference_range_text` or explicit absence;
- `source_observed_at_text` or explicit unknown;
- optional specimen, flag and comment.

Rules:

1. Source text is never overwritten by a decimal, date, canonical concept or normalized unit.
2. Missing source fields use explicit absence/unknown decisions.
3. Unit conversion requires a separate validated conversion contract.
4. Reference-range interpretation is outside E1 and E2.
5. Source flags remain source text.
6. Medical text and values are forbidden in ordinary logs and audit payloads.

## 5. Value and time model

Each draft and confirmed observation has exactly one value kind:

```text
numeric | text | qualitative
```

- numeric values preserve source value and optional comparator;
- text and qualitative values are not silently converted to numbers;
- source unit and reference range remain explicit;
- source date/time wording is preserved;
- timezone is not invented;
- date-only sources remain date precision;
- upload/report time is not substituted silently.

## 6. Provenance model

Allowed source roles:

```text
analyte
value
unit
reference_range
observed_at
specimen
flag
comment
```

E1 source rows retain profile, document, OCR run, candidate, page artifact, page number, role and candidate version.

E2 copies an immutable reviewed-text snapshot for every selected source row while holding deterministic candidate row locks. Analyte and value provenance are mandatory.

## 7. Database and access boundaries

### E1 tables

```text
health_compass.lab_observation_drafts
health_compass.lab_observation_draft_sources
```

- ENABLE + FORCE RLS;
- owner/edit-only reads;
- no direct app mutation grants;
- restricted definer functions only.

### E2 tables

```text
health_compass.lab_observations
health_compass.lab_observation_sources
```

- ENABLE + FORCE RLS;
- owner/edit/view/analyze confirmed-only reads;
- no direct app INSERT/UPDATE/DELETE;
- no worker table or confirmation-function access;
- restrictive provenance foreign keys until E3.

Access matrix:

| Action | owner | edit | view | analyze | outsider | workers |
|---|---:|---:|---:|---:|---:|---:|
| Read E1 drafts | yes | yes | no | no | no | no |
| Create/update/reject/ready draft | yes | yes | no | no | no | no |
| Confirm ready draft | yes | yes | no | no | no | no |
| Read active confirmed observation | yes | yes | yes | yes | no | no |
| Read confirmed source snapshots | yes | yes | yes | yes | no | no |
| Update/delete confirmed value | no | no | no | no | no | no |

## 8. State model

```text
draft → ready → confirmed
   └────→ rejected
```

`ready` means only eligible for a later explicit E2 confirmation. A successful confirmation atomically stores the observation reference and confirmation metadata on the draft.

## 9. Context and confirmation gates

E1 mutations recheck:

- current accepted document;
- current finalized D2 OCR review;
- patient decision `match` or `not_present`;
- exact document/review/patient/candidate versions;
- active health-data consent;
- owner/edit authorization;
- optimistic draft version.

E2 additionally rechecks all of the above in one transaction, requires explicit acknowledgements and locks source candidate rows before validation and snapshot copying.

Patient decisions:

- `match`: confirmation allowed with base acknowledgements;
- `not_present`: additional profile-assignment acknowledgement required;
- `unknown` or `mismatch`: confirmation blocked.

## 10. API and UI

E1 API:

```text
GET   /profiles/{profile_id}/documents/{document_id}/lab-drafts/context
GET   /profiles/{profile_id}/documents/{document_id}/lab-drafts
GET   /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}
POST  /profiles/{profile_id}/documents/{document_id}/lab-drafts
PATCH /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}
PUT   /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/sources
POST  /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/status
```

E2 API:

```text
GET  /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/confirmation
POST /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/confirm
GET  /profiles/{profile_id}/lab-observations
GET  /profiles/{profile_id}/lab-observations/{observation_id}
```

Frontend:

```text
/app/documents/{document_id}/labs
/app/documents/{document_id}/labs/{draft_id}/confirm
```

## 11. Audit and logging

E1 actions:

```text
lab.draft_created
lab.draft_updated
lab.draft_sources_changed
lab.draft_status_changed
```

E2 action:

```text
lab.observation_confirmed
```

All audit payloads are content-free. Medical text, values and source fragments are not copied into ordinary audit or logs.

## 12. Verification

E1 exact head `419386e9...` passed CI `#477`.

E2 exact head `55f10d31...` passed CI `#491`:

- backend compile, Ruff and unit tests;
- frontend lint, typecheck, tests and build;
- migration boundary tests;
- full `head → base → head` cycle;
- PostgreSQL RLS, immutable provenance, stale-source, consent, idempotency and concurrency tests.

Final E2 threat review found no unresolved Critical or High repository finding. It hardened replay matching and removed a source-snapshot TOCTOU interval before merge.

## 13. Production boundary

Production remains:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

E1 and E2 are repository-only. No production rollout or VPS task is authorized.

## 14. Current status

```text
SLICE_E_ARCHITECTURE_ACCEPTED
SLICE_E1_IMPLEMENTED_MERGED_CI_VERIFIED_NOT_DEPLOYED
SLICE_E2_IMPLEMENTED_MERGED_CI_VERIFIED_NOT_DEPLOYED
SLICE_E3_NOT_IMPLEMENTED
PRODUCTION_UNCHANGED
```
