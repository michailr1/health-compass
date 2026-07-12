# HC-017 Slice E — Confirmed Labs Core

Status: `ARCHITECTURE DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`  
Created: 2026-07-12  
Base main: `34425d89fb205a43d8ce543862b2ab8371dabbb4`  
Repository Alembic head: `0055`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## 1. Goal

Create the first source-preserving confirmed laboratory observations from finalized Slice D transcription.

```text
finalized OCR transcription
→ explicit structured Lab draft
→ source-fragment mapping
→ explicit user confirmation
→ immutable confirmed observation
→ later metric dynamics
```

The Slice E boundary is not an OCR parser and not a medical interpretation engine. It converts explicitly reviewed source text into structured observations only after a second, separate confirmation action.

## 2. Core invariant

```text
FINALIZED OCR TRANSCRIPTION IS ELIGIBLE INPUT, NOT A LAB FACT
```

A lab observation exists only after an owner/editor explicitly confirms:

- the selected source fragments;
- analyte wording;
- value;
- unit or absence of unit;
- reference range or absence of range;
- observation date/time or explicit unknown state;
- patient decision;
- the selected Human profile.

No background worker, parser, dictionary or AI model may create a confirmed observation.

## 3. Slice decomposition

### E1 — Structured Lab Drafts

Status: `PLANNED`.

- create a draft from finalized D2 transcription;
- select one or more reviewed OCR candidates as provenance;
- assign explicit source roles;
- preserve source wording exactly;
- optionally parse numeric/date fields without overwriting source text;
- allow owner/editor correction with optimistic concurrency;
- no confirmed observation yet.

### E2 — Explicit Confirmation and Confirmed Observations

Status: `PLANNED AFTER E1 REVIEW`.

- explicit confirmation request;
- current D2 review and patient decision gate;
- exact draft/source manifest;
- immutable confirmed observation snapshot;
- content-free audit;
- idempotent repeated confirmation;
- no interpretation or automatic normalization.

### E3 — Correction, Void and Erasure

Status: `PLANNED AFTER E2 REVIEW`.

- no in-place mutation of confirmed source/value fields;
- correction creates a new observation that supersedes the prior one;
- void preserves provenance and reason;
- permanent erasure follows owner-only document lifecycle;
- source-document erasure removes sole-provenance confirmed observations.

## 4. Source-preserving data principles

The following source fields are always preserved separately from any structured representation:

- `source_analyte_text`;
- `source_value_text`;
- `source_unit_text`;
- `source_reference_range_text`;
- `source_observed_at_text`;
- `source_specimen_text`;
- `source_flag_text`;
- optional source comment.

Rules:

1. Source text is never overwritten by a canonical concept, parsed decimal or normalized unit.
2. Empty/missing source fields are represented explicitly as unknown or not present.
3. Unit conversion is outside Slice E unless a separate validated conversion contract is approved.
4. Reference-range interpretation is outside Slice E.
5. A source flag such as `H`, `L`, `+` or `negative` is stored as source text; no medical conclusion is inferred.
6. User corrections change the draft and confirmation snapshot, but original OCR text remains available through provenance.
7. Source text and medical values remain forbidden in ordinary logs and audit payloads.

## 5. Value model

A draft and confirmed observation use one explicit value kind:

```text
numeric
text
qualitative
```

### Numeric value

Fields:

- required `source_value_text`;
- optional comparator: `<`, `<=`, `=`, `>=`, `>`;
- parsed `numeric_value` using arbitrary-precision decimal;
- required explicit source unit decision: unit text or `unit_not_present=true`;
- optional source reference range.

The parsed decimal is a convenience representation. The source text remains authoritative provenance.

### Text value

Used when the result is a free-form laboratory result that cannot be represented safely as a decimal or controlled qualitative value.

Fields:

- required `source_value_text`;
- `text_value` equal to an explicit user-reviewed representation;
- unit normally absent unless the source explicitly provides one.

### Qualitative value

Examples may include source wording such as positive/negative/detected/not detected, but Slice E does not impose a universal code system.

Fields:

- required `source_value_text`;
- required explicit `qualitative_value_text`;
- optional future canonical code only after a separate mapping contract.

## 6. Date and time model

Laboratory documents may contain collection date, result date, report date or no date.

Slice E stores:

- required `source_observed_at_text` or explicit `observed_time_unknown=true`;
- optional `observed_date`;
- optional `observed_at` with timezone;
- `observed_precision`:

```text
unknown
date
datetime
```

Rules:

- parsing a date never removes source text;
- timezone is not invented;
- a date-only source remains date precision;
- report/upload time is not silently substituted for specimen/observation time;
- metric dynamics may use only explicitly confirmed compatible time fields.

## 7. Reference range model

The source range is preserved as text:

```text
source_reference_range_text
```

Optional structured fields may include:

- lower bound;
- upper bound;
- lower/upper inclusivity;
- textual reference-range qualifier.

Rules:

- structured bounds are user-confirmed;
- no source range is invented;
- range may differ by document, laboratory, age, sex or method;
- range is stored per observation, not as a global truth;
- no automatic diagnosis or “normal/abnormal” conclusion is created;
- future display may compare a value with its own confirmed range, but that is a separate reviewed product behavior.

## 8. Analyte identity

Required:

```text
source_analyte_text
```

Optional:

- `canonical_concept_id` selected explicitly by the user or a later reviewed mapping flow;
- source code and source code system when the document explicitly provides them.

Rules:

- free text remains valid when no concept exists;
- automatic dictionary match may be suggested but never silently persisted;
- canonical concept domain must be a future dedicated laboratory-analyte domain;
- changing source analyte text must clear or revalidate canonical mapping atomically;
- external code systems such as LOINC are not mandatory for E1/E2 and require a separate mapping decision.

## 9. Provenance model

One structured Lab draft may use multiple finalized OCR candidates from the same current OCR run.

Every selected candidate is assigned one or more source roles:

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

Proposed junction tables:

```text
lab_observation_draft_sources
lab_observation_sources
```

Each source row retains:

- profile ID;
- document ID;
- OCR run ID;
- OCR candidate ID;
- page artifact ID;
- page number;
- source role;
- candidate version timestamp used at confirmation.

A confirmed observation also stores:

- source draft ID;
- patient-decision ID and timestamp;
- D2 review finalization timestamp;
- document version timestamp;
- confirmer user ID and timestamp;
- source manifest hash.

All source candidates must belong to the same current finalized OCR run and same document/profile in the initial Slice E implementation.

## 10. Proposed data model

### `lab_observation_drafts`

Purpose: owner/editor-created structured proposals that are not clinical facts.

Suggested fields:

- `id`;
- `profile_id`;
- `document_id`;
- `ocr_run_id`;
- `patient_decision_id`;
- `status`: `draft`, `ready`, `confirmed`, `rejected`;
- source-preserving text fields;
- `value_kind`;
- optional comparator and parsed decimal;
- optional text/qualitative value;
- optional parsed date/time and precision;
- optional structured range bounds;
- optional explicitly selected canonical concept;
- created/updated user and timestamps;
- confirmed observation ID when applicable.

### `lab_observation_draft_sources`

Purpose: exact OCR candidate provenance for each draft field.

- draft ID;
- candidate ID;
- source role;
- candidate `updated_at` captured by the confirmation manifest;
- unique `(draft_id, candidate_id, source_role)`.

### `lab_observations`

Purpose: immutable confirmed observation snapshot.

Suggested fields:

- `id`;
- `profile_id`;
- `document_id`;
- `ocr_run_id`;
- `source_draft_id`;
- `patient_decision_id`;
- source-preserving text fields;
- confirmed structured representations;
- canonical concept only if explicitly selected;
- source manifest hash;
- confirmed by/time;
- status: `active`, `voided`, `erased`;
- correction/supersession links;
- void/erasure metadata;
- created/updated timestamps.

### `lab_observation_sources`

Purpose: immutable copy of the confirmed source candidate manifest.

- observation ID;
- candidate ID;
- page artifact ID;
- page number;
- source role;
- candidate version at confirmation.

## 11. Access matrix

| Action | owner | edit | view | analyze | outsider |
|---|---:|---:|---:|---:|---:|
| View Lab drafts | yes | yes | no | no | no |
| Create/update/reject drafts | yes | yes | no | no | no |
| Confirm observation | yes | yes | no | no | no |
| View active confirmed observations | yes | yes | yes | yes | no |
| View OCR candidate text from confirmed provenance | yes | yes | no | no | no |
| Void confirmed observation | yes | yes | no | no | no |
| Correct by replacement | yes | yes | no | no | no |
| Permanently erase | owner only | no | no | no | no |

Analyze receives confirmed structured observations only. It never receives raw documents, safe pages, OCR artifacts, OCR draft text or Lab drafts.

## 12. PostgreSQL privilege boundary

All Lab tables require:

```text
ENABLE ROW LEVEL SECURITY
FORCE ROW LEVEL SECURITY
```

Runtime role:

- SELECT through RLS only;
- no direct INSERT/UPDATE/DELETE on confirmed observation tables;
- draft mutation and confirmation through restricted SECURITY DEFINER functions;
- no broad grants to document/OCR tables.

Potential functions:

```text
app_create_lab_observation_draft(...)
app_update_lab_observation_draft(...)
app_set_lab_draft_sources(...)
app_reject_lab_observation_draft(...)
app_confirm_lab_observation(...)
app_void_lab_observation(...)
app_correct_lab_observation(...)
app_erase_lab_observation(...)
```

Function properties:

- owner `health_compass_rls_definer`;
- fixed empty search path;
- `row_security=off` only where required;
- PUBLIC EXECUTE revoked;
- EXECUTE granted only to exact caller role;
- static SQL;
- bounded strings and manifests;
- owner/edit and active consent for creation/confirmation;
- owner-only permanent erasure;
- no returned medical values in error messages.

No background worker receives permission to confirm, correct, void or erase observations.

## 13. Draft contract

A draft may be created only when:

- document is accepted and not voided/deleting/erased;
- OCR run is current, succeeded and D2-finalized;
- patient decision is current and not mismatch;
- profile is Human;
- owner/editor has active health-data consent;
- selected candidate IDs belong to that exact OCR run.

Draft mutations require:

- owner/edit authorization;
- active consent;
- `expected_updated_at` optimistic concurrency;
- exact source candidate version manifest;
- bounded source/value/range/date fields;
- explicit unknown/not-present choices rather than invented defaults.

A draft is not visible to view/analyze and never participates in metric dynamics.

## 14. Explicit confirmation contract

The confirmation request must include:

- draft ID and `expected_updated_at`;
- current document timestamp;
- current D2 finalization timestamp;
- patient-decision ID and timestamp;
- exact draft-source candidate manifest;
- explicit `confirm_values_match_source=true`;
- explicit `confirm_patient=true` when decision is `match`;
- explicit `confirm_not_present_ack=true` when decision is `not_present`;
- idempotency key/request ID.

The confirmation function locks and validates in one transaction:

1. profile/document/OCR run/draft belong together;
2. document and OCR run remain current;
3. D2 review remains finalized;
4. patient decision remains allowed and unchanged;
5. all source candidates remain unchanged;
6. draft remains unchanged and not already rejected;
7. value-kind constraints hold;
8. source unit/range/date decisions are explicit;
9. active consent exists;
10. no conflicting confirmation exists for the same draft/idempotency key.

On success it atomically:

- inserts immutable `lab_observations` snapshot;
- inserts immutable `lab_observation_sources` rows;
- marks draft confirmed;
- records confirmer and timestamps;
- emits content-free audit;
- returns observation ID only.

An identical repeated request returns the existing observation. A conflicting request returns a controlled conflict without partial rows.

## 15. Patient matching gate

- `unknown` blocks draft confirmation.
- `mismatch` blocks draft creation and confirmation for that profile.
- `match` permits confirmation with explicit acknowledgement.
- `not_present` permits confirmation only with an additional explicit acknowledgement that the user assigns the document to the selected profile despite absent patient identity.
- patient decision is never inferred from OCR or analyte/value text.
- stale patient-decision timestamps block confirmation.

## 16. Duplicate and idempotency policy

Duplicate-looking observations are not silently merged.

Rules:

- one draft can produce at most one confirmed observation;
- confirmation uses a unique idempotency key;
- repeated OCR/reprocessing cannot overwrite a confirmed observation;
- same analyte/value/date/unit from another document remains a separate provenance record unless a future explicit duplicate-resolution workflow is approved;
- UI may warn about possible duplicates but confirmation remains explicit;
- deduplication keys never rely solely on medical values.

## 17. Correction and void contract

Confirmed source/value fields are immutable.

### Correction

- creates a new observation snapshot;
- links `corrects_observation_id` and `supersedes_observation_id`;
- requires explicit reason and optimistic concurrency;
- original observation becomes superseded, not rewritten;
- both retain provenance.

### Void

- marks observation voided;
- requires bounded explicit reason;
- preserves original snapshot and provenance;
- excludes it from active metrics;
- uses optimistic concurrency and content-free audit.

### Permanent erasure

- owner only;
- separate irreversible confirmation;
- removes value-bearing observation/source/audit rows according to the approved erasure contract;
- leaves only a content-free technical tombstone if required;
- works after consent withdrawal.

## 18. Document-linked deletion lifecycle

The initial Slice E contract keeps every confirmed observation tied to one source document/current finalized OCR run.

When a document enters `deletion_pending`:

- Lab drafts and confirmed observations from that document become inaccessible immediately;
- new confirmation/correction is blocked;
- asynchronous storage/database erasure proceeds idempotently.

Permanent document erasure removes:

- Lab drafts;
- draft-source links;
- sole-provenance confirmed observations;
- observation-source links;
- value-bearing Lab audit rows.

No observation may survive without valid provenance in the initial implementation.

## 19. Audit and logging

Allowed audit actions may include:

```text
lab.draft_created
lab.draft_updated
lab.draft_rejected
lab.observation_confirmed
lab.observation_voided
lab.observation_corrected
lab.observation_erased
```

Ordinary audit `changed_fields` remains content-free.

Forbidden in logs, metrics labels and error text:

- analyte text;
- value;
- unit;
- reference range;
- source date/specimen;
- OCR candidate text;
- patient identity;
- object/storage paths;
- full source manifests.

Allowed operational metadata:

- request ID;
- opaque draft/observation/document UUID;
- action/result code;
- durations and counts;
- safe conflict/error code.

## 20. API outline

Draft/review APIs may include:

```text
GET    /profiles/{profile_id}/documents/{document_id}/labs/drafts
POST   /profiles/{profile_id}/documents/{document_id}/labs/drafts
PATCH  /profiles/{profile_id}/documents/{document_id}/labs/drafts/{draft_id}
PUT    /profiles/{profile_id}/documents/{document_id}/labs/drafts/{draft_id}/sources
POST   /profiles/{profile_id}/documents/{document_id}/labs/drafts/{draft_id}/reject
POST   /profiles/{profile_id}/documents/{document_id}/labs/drafts/{draft_id}/confirm
```

Confirmed observation APIs may include:

```text
GET  /profiles/{profile_id}/labs/observations
GET  /profiles/{profile_id}/labs/observations/{observation_id}
POST /profiles/{profile_id}/labs/observations/{observation_id}/void
POST /profiles/{profile_id}/labs/observations/{observation_id}/correct
POST /profiles/{profile_id}/labs/observations/{observation_id}/erase
```

No endpoint confirms multiple low-confidence observations through a hidden bulk action.

## 21. UI contract

After D2 finalization the user may choose:

```text
Создать результаты анализов
```

The UI must:

- keep profile and source document context visible;
- let the user select reviewed source fragments for analyte/value/unit/range/date;
- show source text beside structured fields;
- require explicit unit/range/date absence choices;
- display parsed numeric/date fields as editable suggestions;
- never hide low confidence;
- show that a draft is not yet a medical fact;
- use a separate final confirmation screen;
- display patient decision and source provenance;
- warn about possible duplicates without silently merging;
- remain keyboard and screen-reader accessible.

The confirmation copy must state that the user is confirming transcription into structured data, not receiving a diagnosis or medical interpretation.

## 22. Required tests

### RLS and privileges

- owner/editor draft access;
- view/analyze/outsider cannot read drafts;
- owner/edit/view/analyze read active confirmed observations;
- analyze cannot read source OCR text or draft rows;
- app has no direct mutation grants on confirmed observations;
- no-user-context returns zero rows;
- cross-profile IDs fail closed.

### Draft mutations

- source candidates belong to current finalized OCR run;
- candidate roles and manifest are exact;
- stale draft/candidate/document/patient timestamps fail without mutation;
- revoked consent blocks creation/update/confirmation;
- source text and bounds are validated;
- unit/range/date absence is explicit;
- no clinical fact exists before confirmation.

### Confirmation

- match path;
- not-present explicit acknowledgement path;
- unknown/mismatch blocked;
- identical retry idempotent;
- conflicting retry blocked;
- partial failure creates no observation/source rows;
- confirmed observation snapshot equals explicit draft values;
- audit contains no medical text;
- duplicate-looking observations are not auto-merged.

### Corrections/deletion

- no in-place confirmed value update;
- correction creates replacement and supersession chain;
- void excludes active observation;
- owner-only erasure;
- document deletion hides and erases related drafts/observations;
- consent withdrawal does not block erasure.

### Medical safety

- no diagnosis/recommendation/dose fields;
- no silent canonical mapping;
- no silent unit conversion;
- no automatic reference-range interpretation;
- analyze receives only confirmed structured observations.

### CI

- migration full cycle;
- single Alembic head;
- owner/definer/grant assertions;
- exact-head backend/frontend/PostgreSQL gates;
- independent architecture and implementation reviews.

## 23. Proposed implementation sequencing

### E1

- migration for drafts/source links;
- RLS/privilege matrix;
- restricted draft functions;
- source-fragment selection API/UI;
- no confirmed observations.

### E2

- confirmed observation/source tables;
- restricted confirmation function;
- confirmed observation API/UI;
- analyze confirmed-only access;
- idempotency and duplicate warnings.

### E3

- correction/void/erasure functions;
- document deletion propagation;
- lifecycle UI;
- independent security review.

Candidate migration numbers are assigned only after rechecking current `main`, all Alembic heads and open migration PRs at each implementation start.

## 24. Stop conditions

Do not merge or deploy when:

- finalized OCR creates a Lab observation automatically;
- patient decision is unknown or mismatch;
- source wording/value/unit/range is not preserved;
- unit conversion or canonical mapping is silent;
- source candidate manifest is missing or stale;
- a confirmed observation can be updated in place;
- app/worker roles have broad mutation privileges;
- draft rows are visible to view/analyze;
- analyze can access OCR text;
- duplicate-looking values are silently merged;
- document erasure leaves sole-provenance observations;
- medical values appear in logs/audit;
- exact-head CI or negative PostgreSQL tests are absent;
- production upload is enabled before controlled rollout approval.

## 25. Production boundary

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

Slice E architecture does not authorize implementation merge, package installation, migration application, worker provisioning or production rollout.

## 26. Final current status

```text
SLICE_D_D1_D2_MERGED_AND_VERIFIED
SLICE_E_ARCHITECTURE_DEFINED
SLICE_E_NOT_IMPLEMENTED
PRODUCTION_UNCHANGED
```
