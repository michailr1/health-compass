# HC-017 Slice E2 — Explicit Confirmation and Confirmed Observations

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`  
Created: 2026-07-12  
Implemented: 2026-07-13  
Source PR: `#65`  
Verified head: `55f10d311d1f39262d557fa7b60cc07060ac5590`  
Merge commit: `1d61331194edf0f78b94a304d27ccf31dfa2a755`  
CI: `#491 — passed`  
Repository Alembic head: `0058`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## 1. Implemented outcome

E2 converts one current E1 `ready` Lab draft into one immutable confirmed laboratory observation through a separate, explicit, atomic and idempotent user action.

```text
E1 ready draft
→ confirmation preview
→ explicit acknowledgements
→ atomic current-source validation
→ immutable observation snapshot
→ immutable source snapshots
→ content-free audit
```

E2 does not interpret the result, decide whether it is normal, silently map an analyte, convert a unit, create a diagnosis or produce treatment advice.

## 2. Core invariants

```text
READY DRAFT IS NOT A CONFIRMED OBSERVATION
ONLY OWNER/EDITOR MAY CONFIRM
NO WORKER MAY CONFIRM
ONE DRAFT CREATES AT MOST ONE OBSERVATION
CONFIRMED SOURCE/VALUE FIELDS ARE IMMUTABLE
```

A confirmation succeeds only when all source versions remain current within the same PostgreSQL transaction.

## 3. Data model

Migration `0058_add_confirmed_lab_observations.py` adds:

### `health_compass.lab_observations`

Immutable snapshot fields include:

- profile, document, OCR run, patient decision and source draft IDs;
- source analyte, value, unit, range, date/time, specimen, flag and comment;
- numeric/text/qualitative structured representation;
- exact draft/document/review/patient version timestamps;
- confirmation idempotency key;
- acknowledgement flags;
- confirmer and confirmation time;
- active status.

Constraints enforce:

- one observation per source draft;
- idempotency key uniqueness within a profile;
- `match` or `not_present` patient decision only;
- the extra acknowledgement for `not_present`;
- complete base acknowledgements;
- valid value-kind alternatives;
- explicit unit/range/date presence or absence;
- document/profile referential integrity.

### `health_compass.lab_observation_sources`

One immutable row is copied for each selected OCR candidate and source role:

- observation ID;
- candidate ID and exact candidate version;
- source role;
- profile, document and OCR run;
- page artifact and page number;
- reviewed source text snapshot used at confirmation.

The source snapshot is protected medical data and is excluded from ordinary logs and audit payloads.

### E1 draft consumption

A successful confirmation atomically changes:

```text
ready → confirmed
```

The draft stores:

- `confirmed_at`;
- `confirmed_by_user_id`;
- `confirmed_observation_id`.

A confirmed draft cannot be updated, rejected, remapped or consumed as a second observation.

## 4. Confirmation function

Canonical function:

```text
health_compass.app_confirm_lab_observation(...)
```

Properties:

- `SECURITY DEFINER`;
- owner `health_compass_rls_definer`;
- `search_path=''`;
- `row_security=off`;
- static SQL;
- scalar UUID result;
- PUBLIC EXECUTE revoked;
- execution granted only to `health_compass_app`;
- no scanner, renderer, reconciler or OCR worker execution.

The function validates and locks:

1. current E1 draft exists and is `ready`;
2. caller has owner/edit permission;
3. owner health-data consent is active;
4. source document is current, accepted and not voided/deleting/erased;
5. document points to the current OCR run;
6. OCR succeeded and D2 review is finalized;
7. exact review-finalization timestamp matches;
8. patient decision is current and is `match` or `not_present`;
9. `not_present` includes explicit profile assignment acknowledgement;
10. exact draft timestamp matches;
11. source manifest contains current accepted/edited candidates;
12. every candidate matches its stored version;
13. analyte and value provenance exist;
14. idempotency key does not belong to another draft;
15. the draft is not consumed by a conflicting observation.

Candidate rows are locked in deterministic order before version validation and immutable source-text copying. This closes the review-identified TOCTOU interval.

Any mismatch aborts the complete transaction with no observation, source snapshot, draft transition or audit row.

## 5. Explicit acknowledgements

Every confirmation request explicitly acknowledges:

- displayed analyte and value match the reviewed document source;
- unit and reference-range presence/absence are correct;
- date/time presence/absence is correct;
- the observation belongs to the selected Human profile;
- confirmation creates a structured record, not a medical interpretation.

For patient decision `not_present`, an additional acknowledgement is mandatory:

```text
I explicitly assign this result to the selected profile even though the source does not identify the patient.
```

Patient decisions `unknown` and `mismatch` always block confirmation.

## 6. Idempotency and concurrency

### Same key, same draft and same expectations

Returns the committed observation.

### Same key, different draft

Returns conflict and never reuses the observation.

### Same draft, different key

Returns the committed observation only when source versions and acknowledgement values match the original confirmation. Otherwise it returns conflict.

### Concurrent confirmation

Draft locking and unique constraints permit at most one observation. A losing concurrent request returns the committed observation only when the immutable confirmation expectations match.

## 7. RLS and privilege matrix

Both E2 tables use:

- ENABLE RLS;
- FORCE RLS;
- confirmed-only profile visibility policies;
- no direct app INSERT, UPDATE or DELETE grants;
- no worker table grants.

| Action | owner | edit | view | analyze | outsider | workers |
|---|---:|---:|---:|---:|---:|---:|
| Read E1 drafts | yes | yes | no | no | no | no |
| Confirm ready draft | yes | yes | no | no | no | no |
| Read active confirmed observation | yes | yes | yes | yes | no | no |
| Read confirmed source snapshots | yes | yes | yes | yes | no | no |
| Update/delete confirmed value | no | no | no | no | no | no |

`analyze` receives only confirmed immutable data. It never receives Lab drafts or OCR candidate text.

## 8. API and UI

API:

```text
GET  /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/confirmation
POST /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/confirm
GET  /profiles/{profile_id}/lab-observations
GET  /profiles/{profile_id}/lab-observations/{observation_id}
```

Frontend:

```text
/app/documents/{document_id}/labs/{draft_id}/confirm
```

The separate confirmation screen displays the selected profile, patient decision, source-preserving fields, provenance summary and explicit acknowledgement controls. The action label states that it creates a confirmed medical record and does not imply diagnosis or normality.

## 9. Audit and logging

Audit action:

```text
lab.observation_confirmed
```

Audit contains identifiers and an empty/content-free changed-fields object. It does not contain analyte text, values, units, ranges, patient text or source fragments.

## 10. Immutability and deletion boundary

E2 exposes no UPDATE or DELETE path for confirmed observations.

The following are immutable:

- source analyte/value/unit/range/date/specimen/flag/comment;
- parsed value/date fields;
- patient decision snapshot;
- document/OCR/draft/candidate provenance;
- confirmer, confirmation time and acknowledgements.

Restrictive provenance foreign keys prevent source deletion from silently orphaning confirmed data. Correction, voiding and permanent erasure belong to E3 and require separate restricted transactions.

## 11. Verification

Exact head `55f10d311d1f39262d557fa7b60cc07060ac5590` passed CI `#491`:

- backend compile, Ruff and unit tests;
- frontend lint, typecheck, tests and production build;
- migration boundary tests;
- full isolated `head → base → head` cycle;
- PostgreSQL integration and RLS tests.

Verified PostgreSQL scenarios include:

- a ready draft creates zero confirmed observations;
- owner/editor confirmation;
- view/analyze confirmed-only visibility;
- outsider and no-context zero rows;
- immutable source snapshot copying;
- direct mutation denial;
- PUBLIC and worker denial;
- stale candidate rejection;
- revoked-consent rejection without partial rows;
- mandatory `not_present` acknowledgement;
- same-key and same-draft replay behavior;
- different-draft idempotency conflict;
- two concurrent confirmations producing exactly one observation;
- content-free audit.

Final threat review found no unresolved Critical or High repository finding. Replay semantics and candidate snapshot locking were hardened before merge.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-E2-CONFIRMED-OBSERVATIONS-EVIDENCE-2026-07-13.md
```

## 12. Next stage: E3

E3 remains `NOT IMPLEMENTED` and must add:

- correction through replacement observations and supersession chains;
- explicit voiding with reason;
- owner-only permanent erasure;
- atomic document/source deletion propagation;
- proof that sole-provenance observations cannot be orphaned;
- no in-place mutation of confirmed source/value fields.

## 13. Production boundary

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

E2 is repository-only. No migration, service installation, document upload enablement or VPS rollout is authorized.
