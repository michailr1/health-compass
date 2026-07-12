# HC-017 Slice E — Confirmed Labs Core

Status: `E1 IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED; E2 NOT IMPLEMENTED`  
Created: 2026-07-12  
Current main: `2ad0ca47d994472201c218b3e6af37145cbacdec`  
Repository Alembic head: `0057`  
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

Slice E is not an OCR parser and not a medical interpretation engine. It structures reviewed source text and creates a confirmed observation only after a separate explicit confirmation transaction.

## 2. Core invariant

```text
FINALIZED OCR TRANSCRIPTION IS ELIGIBLE INPUT, NOT A LAB FACT
READY LAB DRAFT IS ELIGIBLE INPUT, NOT A CONFIRMED OBSERVATION
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

- owner/editor creates a draft from the current finalized D2 transcription;
- reviewed OCR candidates are assigned exact source roles;
- source wording is preserved separately from parsed values;
- numeric, text and qualitative value kinds are explicit;
- unit, range and date absence/unknown states are explicit;
- document, OCR review, patient decision and consent are checked on every mutation;
- optimistic concurrency protects draft and source versions;
- FORCE RLS keeps drafts owner/edit-only;
- no confirmed observation exists in E1.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-E1-LAB-DRAFTS-EVIDENCE-2026-07-12.md
```

### E2 — Explicit Confirmation and Confirmed Observations

Status: `NEXT / NOT IMPLEMENTED / NOT DEPLOYED`.

Required scope:

- a separate explicit confirmation request;
- immutable confirmed observation and source snapshot tables;
- current document, finalized D2 review, patient decision, ready draft and exact source manifest;
- explicit user acknowledgements;
- additional profile-assignment acknowledgement when patient decision is `not_present`;
- idempotent atomic confirmation;
- owner/edit confirmation;
- owner/edit/view/analyze confirmed-only reads;
- no interpretation, diagnosis or automatic normalization.

### E3 — Correction, Void and Erasure

Status: `PLANNED AFTER E2 REVIEW`.

- confirmed source/value fields are never updated in place;
- correction creates a new observation that supersedes the prior one;
- void preserves provenance and explicit reason;
- owner-only permanent erasure follows the document lifecycle;
- source-document erasure removes sole-provenance confirmed observations.

## 4. E1 source-preserving data principles

The following source fields are stored separately from structured representations:

- `source_analyte_text`;
- `source_value_text`;
- `source_unit_text` or `unit_not_present=true`;
- `source_reference_range_text` or `reference_range_not_present=true`;
- `source_observed_at_text` or `observed_time_unknown=true`;
- optional `source_specimen_text`;
- optional `source_flag_text`;
- optional source comment.

Rules:

1. Source text is never overwritten by a parsed decimal, date, canonical concept or normalized unit.
2. Missing source fields use explicit absence/unknown decisions.
3. Unit conversion is outside E1 and E2 unless a separate validated conversion contract is approved.
4. Reference-range interpretation is outside E1 and E2.
5. Source flags such as `H`, `L`, `+`, `positive` or `negative` remain source text.
6. Original OCR text remains available through provenance even when a user edits the structured draft.
7. Source text and medical values are forbidden in ordinary logs and audit payloads.

## 5. Value model

Each draft uses exactly one value kind:

```text
numeric
text
qualitative
```

### Numeric

- required source value text;
- optional comparator: `<`, `<=`, `=`, `>=`, `>`;
- arbitrary-precision decimal representation;
- explicit source-unit decision;
- optional source reference range.

The source text remains authoritative provenance.

### Text

- required source value text;
- explicit reviewed text representation;
- no comparator;
- no automatic numeric conversion.

### Qualitative

- required source value text;
- explicit qualitative text representation;
- no universal automatic coding;
- no comparator.

## 6. Date and time model

E1 stores:

- source date/time wording or explicit unknown;
- optional parsed date;
- optional parsed timestamp with timezone;
- precision: `unknown`, `date` or `datetime`.

Rules:

- parsing never removes source wording;
- timezone is not invented;
- a date-only source remains date precision;
- report/upload time is not substituted silently;
- metric dynamics may use only later confirmed compatible time fields.

## 7. Reference range and analyte identity

Source range is preserved as text. Structured bounds, reference-range interpretation and normal/abnormal classification are outside E1.

Required analyte field:

```text
source_analyte_text
```

Canonical analyte mapping is optional future work and may never overwrite source wording. Free text remains valid when no concept exists.

## 8. E1 provenance model

A draft may use multiple accepted/edited OCR candidates from the same current finalized OCR run.

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

Each source row retains:

- profile ID;
- document ID;
- OCR run ID;
- OCR candidate ID;
- page artifact ID;
- page number;
- source role;
- exact candidate version timestamp.

A draft may become `ready` only when current analyte and value provenance exist.

## 9. E1 database boundary

Tables:

```text
health_compass.lab_observation_drafts
health_compass.lab_observation_draft_sources
```

Both tables have:

- ENABLE RLS;
- FORCE RLS;
- owner/edit-only SELECT policies;
- no direct app INSERT, UPDATE or DELETE grants.

Mutation functions are `SECURITY DEFINER`, owned by the dedicated RLS definer role, use fixed empty `search_path`, set `row_security=off`, revoke PUBLIC EXECUTE and grant execution only to the runtime app.

Worker roles have no E1 mutation access.

## 10. E1 state model

```text
draft
→ ready
```

Alternative terminal state:

```text
draft
→ rejected
```

`ready` means only “eligible for a later E2 confirmation”. It does not mean confirmed, interpreted or available to analytics.

## 11. E1 context gates

Every relevant mutation rechecks:

- current accepted document;
- current OCR run;
- succeeded and finalized D2 review;
- patient decision `match` or `not_present`;
- exact document timestamp;
- exact review-finalization timestamp;
- exact patient-decision timestamp;
- exact candidate timestamps;
- active health-data consent;
- owner/edit authorization;
- optimistic draft timestamp.

Consent revocation after draft creation blocks source replacement and status transitions.

## 12. Access matrix

| Action | owner | edit | view | analyze | outsider |
|---|---:|---:|---:|---:|---:|
| Read E1 drafts | yes | yes | no | no | no |
| Create/update draft | yes | yes | no | no | no |
| Replace provenance manifest | yes | yes | no | no | no |
| Mark ready/rejected | yes | yes | no | no | no |
| Confirm observation | not implemented | not implemented | no | no | no |

## 13. E1 API and UI

API:

```text
GET   /profiles/{profile_id}/documents/{document_id}/lab-drafts/context
GET   /profiles/{profile_id}/documents/{document_id}/lab-drafts
GET   /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}
POST  /profiles/{profile_id}/documents/{document_id}/lab-drafts
PATCH /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}
PUT   /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/sources
POST  /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/status
```

Frontend:

```text
/app/documents/{document_id}/labs
```

The UI supports draft creation, source-fragment selection and `ready` transition. It contains no observation-confirmation action.

## 14. E1 audit and logging

Audit actions:

```text
lab.draft_created
lab.draft_updated
lab.draft_sources_changed
lab.draft_status_changed
```

Audit payloads are content-free. Medical text, values, source fragments and parsed fields are not copied into ordinary audit or logs.

## 15. E1 verification

Exact head `419386e9...` passed CI `#477`:

- backend compile, Ruff and unit tests;
- frontend lint, typecheck, tests and build;
- migration boundary tests;
- full `head → base → head` cycle;
- PostgreSQL RLS, privilege and provenance tests;
- stale document/review/patient/candidate protections;
- post-creation consent-revocation tests;
- proof that no confirmed observation table or rows exist.

## 16. E2 confirmation requirements

E2 must never reuse an E1 mutation endpoint for confirmation.

The confirmation transaction must atomically validate:

- draft status is `ready`;
- exact draft timestamp and source manifest;
- current document and OCR review;
- current patient decision;
- active consent;
- explicit profile acknowledgement;
- explicit source/value/unit/range/date acknowledgement;
- unique idempotency key;
- no existing observation from the same draft.

A successful transaction creates an immutable observation and immutable source snapshot, marks the draft consumed and writes content-free audit.

## 17. E2 stop conditions

Do not merge E2 when:

- a worker can confirm observations;
- `ready` automatically creates a fact;
- unknown/mismatch patient decisions are accepted;
- `not_present` lacks explicit profile assignment acknowledgement;
- source wording is lost or overwritten;
- silent unit conversion or canonical mapping occurs;
- stale draft/document/OCR/patient/candidate versions can be consumed;
- confirmation is not idempotent;
- confirmed source/value fields can be updated in place;
- drafts become visible to view/analyze;
- medical values appear in audit/logs;
- negative PostgreSQL tests are absent.

## 18. Production boundary

Production remains:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

E1 is repository-only. No production rollout or VPS task is authorized.

## 19. Final current status

```text
SLICE_E_ARCHITECTURE_ACCEPTED
SLICE_E1_IMPLEMENTED_MERGED_CI_VERIFIED
SLICE_E1_NOT_DEPLOYED
SLICE_E2_NOT_IMPLEMENTED
NO_CONFIRMED_LAB_OBSERVATIONS
PRODUCTION_UNCHANGED
```
