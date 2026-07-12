# HC-017 Slice E2 — Explicit Confirmation and Confirmed Observations

Status: `ARCHITECTURE DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`  
Created: 2026-07-12  
Base main: `ab58f40d4d69a122aa5a48046a29bc5134903bdc`  
Repository Alembic head: `0057`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## 1. Goal

Convert one current E1 `ready` Lab draft into one immutable confirmed laboratory observation through a separate, explicit, atomic and idempotent user action.

```text
E1 ready draft
→ confirmation preview
→ explicit acknowledgements
→ atomic current-source validation
→ immutable observation snapshot
→ immutable source snapshot
→ content-free audit
```

E2 does not interpret the result, decide whether it is normal, map the analyte silently, convert the unit or create a diagnosis.

## 2. Core invariants

```text
READY DRAFT IS NOT A CONFIRMED OBSERVATION
ONLY OWNER/EDITOR MAY CONFIRM
NO WORKER MAY CONFIRM
ONE DRAFT CREATES AT MOST ONE OBSERVATION
CONFIRMED SOURCE/VALUE FIELDS ARE IMMUTABLE
```

A confirmation is valid only when all source versions remain current at the instant the transaction commits.

## 3. Required user acknowledgements

Every confirmation request must explicitly acknowledge:

- the displayed analyte and value match the reviewed document source;
- unit and reference-range presence/absence are correct;
- date/time presence/absence is correct;
- the observation belongs to the selected Human profile;
- confirmation creates a structured record, not a medical interpretation.

When patient decision is `not_present`, an additional acknowledgement is required:

```text
I explicitly assign this result to the selected profile even though the source does not identify the patient.
```

`unknown` and `mismatch` patient decisions always block confirmation.

## 4. Proposed data model

### `lab_observations`

Immutable snapshot fields:

- `id`;
- `profile_id`;
- `document_id`;
- `ocr_run_id`;
- `patient_decision_id`;
- `source_draft_id`;
- `status` initially `active`;
- all E1 source-preserving value fields;
- confirmer user and timestamp;
- exact draft/document/review/patient timestamps;
- confirmation idempotency key;
- acknowledgement flags;
- created timestamp.

Constraints:

- one observation per source draft;
- idempotency key unique within the profile;
- value-kind constraints equal or stricter than E1;
- profile/document composite integrity;
- no UPDATE or DELETE grant to runtime or workers.

### `lab_observation_sources`

One row per selected source candidate and role, copying:

- observation ID;
- candidate ID;
- source role;
- candidate version timestamp;
- profile/document/OCR run/page artifact/page number;
- reviewed source-text snapshot used at confirmation.

The source snapshot is protected medical data. It is not copied to ordinary logs or audit payloads.

## 5. Why no manifest hash is required for E2 MVP

E2 integrity is enforced by:

- immutable source rows;
- exact candidate IDs and timestamps;
- unique source draft;
- exact draft/document/review/patient timestamps;
- a single atomic PostgreSQL transaction;
- idempotency constraints.

A database extension is not introduced solely to calculate a hash. A future manifest hash may be added only if it gives a concrete security or interoperability benefit and is computed from a canonical representation.

## 6. Confirmation function

Candidate function:

```text
health_compass.app_confirm_lab_observation(...)
```

Properties:

- `SECURITY DEFINER`;
- owner `health_compass_rls_definer`;
- fixed empty `search_path`;
- `row_security=off`;
- PUBLIC EXECUTE revoked;
- execution granted only to `health_compass_app`;
- static SQL only;
- scalar UUID return;
- no worker execution.

Required inputs include:

- server-generated observation UUID;
- source draft UUID;
- confirmation idempotency key;
- expected draft timestamp;
- expected document timestamp;
- expected D2 review-finalization timestamp;
- expected patient-decision timestamp;
- explicit acknowledgement booleans;
- content-free audit event UUID and request ID.

## 7. Atomic confirmation checks

The transaction must lock and validate:

1. current E1 draft exists and status is `ready`;
2. caller has owner/edit permission;
3. owner health-data consent is active;
4. source document is current, accepted and not voided/deleting/erased;
5. document points to the draft OCR run;
6. OCR run succeeded and D2 review is finalized;
7. review finalization timestamp matches the expected version;
8. patient decision is current and is `match` or `not_present`;
9. `not_present` has the additional profile-assignment acknowledgement;
10. draft timestamp matches;
11. source manifest contains current accepted/edited candidates;
12. every source candidate still matches its stored version;
13. analyte and value provenance both exist;
14. no observation already exists for another draft under the idempotency key;
15. no different observation already consumes the draft.

Any mismatch aborts the complete transaction with no observation, no draft state change and no audit row.

## 8. Idempotency contract

### Same idempotency key, same draft

Return the existing observation when acknowledgements and source versions correspond to the already committed confirmation.

### Same idempotency key, different draft

Return conflict. Never reuse the existing observation.

### Same draft, different idempotency key after successful confirmation

Return the existing observation for that draft. Do not create a duplicate.

### Concurrent confirmation

Row locks and unique constraints allow at most one observation. Losing transactions return the committed observation only when their source expectations match; otherwise they return conflict.

## 9. Draft transition

A successful confirmation atomically changes the E1 draft:

```text
ready → confirmed
```

E2 adds confirmation metadata to the draft:

- `confirmed_at`;
- `confirmed_by_user_id`;
- optional immutable observation reference or an equivalent unique reverse lookup.

A confirmed draft cannot be updated, rejected, remapped or confirmed again as a new observation.

## 10. Observation immutability

E2 exposes no UPDATE or DELETE path for confirmed observations.

The following fields are immutable:

- source analyte/value/unit/range/date/specimen/flag/comment;
- parsed value/date fields;
- patient decision snapshot;
- document/OCR/draft/source provenance;
- confirmer and confirmation time;
- acknowledgements.

Correction, void and permanent erasure belong to E3 and require separate restricted functions.

## 11. Access matrix

| Action | owner | edit | view | analyze | outsider | workers |
|---|---:|---:|---:|---:|---:|---:|
| Read E1 drafts | yes | yes | no | no | no | no |
| Confirm ready draft | yes | yes | no | no | no | no |
| Read active confirmed observation | yes | yes | yes | yes | no | no |
| Read confirmed source snapshots | yes | yes | yes | yes | no | no |
| Update/delete confirmed value | no | no | no | no | no | no |

`analyze` receives only confirmed immutable data. It never receives drafts, OCR candidates or unconfirmed source text.

## 12. RLS and privileges

Both E2 tables must use:

- ENABLE RLS;
- FORCE RLS;
- confirmed-only SELECT policy based on profile visibility;
- no direct app INSERT, UPDATE or DELETE grants;
- no worker table grants.

The confirmation function is the only E2 creation path.

## 13. API contract

Candidate endpoints:

```text
GET  /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/confirmation
POST /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/confirm
GET  /profiles/{profile_id}/lab-observations
GET  /profiles/{profile_id}/lab-observations/{observation_id}
```

The confirmation-preview response contains exactly what the user must acknowledge, plus current version timestamps. It does not include medical interpretation.

## 14. UI contract

A separate confirmation screen must show:

- selected Human profile;
- patient decision and any `not_present` warning;
- source analyte and value;
- unit or explicit absence;
- reference range or explicit absence;
- date/time or explicit unknown;
- specimen, flag and comment when present;
- page/source provenance links or labels;
- explicit acknowledgement controls;
- a single confirmation action.

The action label must state that it creates a confirmed health record. It must not imply diagnosis or normality.

## 15. Audit and logging

New audit action:

```text
lab.observation_confirmed
```

Audit contains only identifiers and content-free metadata already permitted by the audit schema. It does not contain analyte text, values, units, ranges, patient text or source fragments.

Allowed operational metrics:

- confirmation count;
- latency;
- conflict/idempotent-replay count;
- safe failure code.

## 16. Document and source deletion boundary

E2 must not silently orphan confirmed data.

Initial safe rule:

- document/source deletion is blocked while a confirmed observation exists unless the E3 owner-only erasure transaction deletes the observation and all source snapshots atomically.

E2 may therefore use restrictive foreign keys for confirmed provenance. E3 defines the explicit deletion order and tombstone policy.

## 17. Required tests

### Database and privileges

- FORCE RLS on observations and sources;
- owner/edit/view/analyze confirmed reads;
- outsider/no-context zero rows;
- app has no direct INSERT/UPDATE/DELETE;
- workers have no table or function access;
- PUBLIC EXECUTE revoked.

### Confirmation

- owner and editor can confirm;
- view/analyze cannot confirm;
- unknown/mismatch patient decision blocked;
- `not_present` without additional acknowledgement blocked;
- revoked consent blocked;
- stale draft/document/review/patient/candidate version blocked;
- missing analyte/value provenance blocked;
- exact immutable snapshot copied;
- draft becomes confirmed atomically;
- content-free audit created.

### Idempotency and concurrency

- same key/same draft returns existing observation;
- same key/different draft conflicts;
- same draft/different key returns existing observation;
- concurrent confirmation creates one observation;
- failed confirmation creates no partial rows.

### Safety

- E1 drafts remain invisible to view/analyze;
- confirmed observations contain no automatic interpretation;
- no canonical mapping or unit conversion occurs;
- no Clinical Context or medication record is created;
- logs and audit contain no medical text/value.

### Migration cycle

- candidate migration follows the current single head;
- full `head → base → head` passes;
- downgrade refuses destructive loss when observations exist or restores a safe fail-closed boundary.

## 18. Implementation sequencing

1. Recheck current `main`, open PRs and Alembic heads.
2. Assign the next migration number only then.
3. Add immutable observation/source tables and E1 `confirmed` transition.
4. Add the restricted confirmation function and idempotency constraints.
5. Add negative PostgreSQL tests before API/UI.
6. Add confirmation preview and confirmation API.
7. Add separate confirmation UI.
8. Run exact-head backend/frontend/migration/PostgreSQL CI.
9. Perform independent E2 security review.
10. Keep production unchanged.

## 19. Stop conditions

Do not merge when:

- `ready` automatically creates an observation;
- confirmation is available to workers, view or analyze;
- unknown/mismatch patient decision is accepted;
- `not_present` lacks explicit profile acknowledgement;
- source wording or exact provenance is lost;
- stale versions can be confirmed;
- idempotency can create duplicates;
- confirmed fields can be updated in place;
- draft or OCR text becomes visible to analyze;
- direct mutation grants exist;
- document deletion can orphan an observation;
- medical values enter logs/audit;
- migration cycle or negative tests are missing.

## 20. Production boundary

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

E2 architecture does not authorize deployment.
