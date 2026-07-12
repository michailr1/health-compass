# HC-017 Slice D — OCR Candidates and Human Review

Status: `D1+D2 IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`  
Created: 2026-07-12  
Updated: 2026-07-12  
Repository main: `f67a1128e29a1c62e8a3b27dd20c973df82947ad`  
Repository Alembic head: `0055`  
Production: `b8e868825f378195975e2729f3f36c21a1afa2d0 / 0049`

## 1. Goal

Convert encrypted C2 safe-page images into reviewable OCR transcription and explicit human decisions without creating medical facts.

```text
encrypted safe_page
→ full GCM verification
→ sealed read-only memory input
→ bounded local OCR
→ encrypted OCR provenance
→ strict TSV parsing
→ needs_review candidates
→ owner/edit human review
→ explicit patient decision
→ finalized transcription
```

Slice D stops before Labs confirmation.

## 2. Core invariant

```text
REVIEWED OCR IS TRANSCRIPTION, NOT A CLINICAL FACT
```

Even accepted, edited and finalized OCR text is not automatically:

- a diagnosis;
- a condition;
- a medication;
- a body measurement;
- a laboratory observation;
- an AI conclusion.

Clinical or Labs facts require a later independent confirmation transaction.

## 3. Delivery status

### D1 — Local OCR Candidate Extraction

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #56
verified head: dc28e9e220dd51264e6dab1244ce8d8696f501b2
merge: a33c3d515b885c6ea0e8f51291a1d25bed77cd7d
CI: #442
migration: 0054
```

Implemented:

- OCR run, encrypted provenance and candidate schema;
- dedicated OCR worker role and restricted functions;
- safe-page claim, lease, heartbeat and retry;
- bounded local Tesseract execution;
- encrypted TSV provenance;
- strict TSV parser;
- deterministic `needs_review` candidate aggregation;
- owner/edit-only candidate reads;
- OCR status and candidate APIs;
- no automatic Clinical Context, measurement or Labs creation.

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

- accept/edit/reject/defer candidate actions;
- owner/edit authorization and current health-data consent;
- candidate, document and patient-decision optimistic concurrency;
- explicit `unknown`, `match`, `mismatch` and `not_present` decisions;
- exact candidate ID/timestamp manifest;
- atomic review finalization;
- idempotent identical finalization;
- content-free audit;
- accessible review UI;
- revisable decisions before finalization;
- read-only finalized review;
- no Clinical Context, measurement or Labs creation.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-D2-HUMAN-REVIEW-EVIDENCE-2026-07-12.md
```

## 4. D1 OCR engine contract

MVP engine:

```text
local Tesseract 5.x
--oem 1
language: rus+eng
output: TSV
```

Rules:

- no external OCR processor;
- absolute executable and tessdata paths;
- no shell;
- approved PSM allowlist only;
- no arbitrary user-supplied options;
- exact engine, language and traineddata manifest recorded;
- missing or unsafe language files fail closed;
- no silent fallback to another language.

Official references:

- `https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html`;
- `https://tesseract-ocr.github.io/tessdoc/Data-Files.html`;
- `https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html`;
- `https://tesseract-ocr.github.io/tessdoc/Home.html`.

## 5. PostgreSQL role boundary

```text
health_compass_ocr_worker LOGIN NOBYPASSRLS
```

The OCR role receives:

- database CONNECT;
- schema USAGE;
- EXECUTE only on OCR claim, heartbeat, complete and fail functions;
- no direct SELECT, INSERT, UPDATE or DELETE on document, OCR, profile, audit or clinical tables;
- no membership in app, migrator, renderer, reconciler or definer roles;
- no BYPASSRLS, SUPERUSER, CREATEDB, CREATEROLE or REPLICATION.

The runtime app may read owner/edit review data through RLS, but may mutate review state only through restricted SECURITY DEFINER functions. It has no direct INSERT, UPDATE or DELETE grants on OCR review tables.

## 6. D1 schema

Migration `0054` adds:

### `document_ocr_runs`

One versioned OCR attempt over one current render run, including engine, language, traineddata, lease, retry and output-manifest provenance.

### `document_ocr_artifacts`

Encrypted machine-output provenance, not a user-facing clinical record.

```text
ocr/{document_uuid}/{ocr_run_uuid}/page-{page_number}.tsv.hcenc
```

### `document_ocr_candidates`

Reviewable text blocks with OCR run, page, bounding box, confidence, source word count, original text and review metadata.

Every D1 candidate starts as `needs_review`.

## 7. D2 schema

Migration `0055` adds:

### `document_ocr_patient_decisions`

One explicit patient decision per OCR run:

```text
unknown
match
mismatch
not_present
```

The row stores decision, bounded note, reviewer and timestamps. It has RLS and FORCE RLS and is visible only to owner/edit.

### Review provenance on `document_ocr_runs`

- `review_status`;
- finalizer and timestamp;
- source document timestamp;
- exact candidate version manifest;
- patient-decision ID and timestamp.

### Reviewed document state

`profile_documents.ocr_status` gains:

```text
reviewed
```

### Candidate state constraints

- `needs_review`: no reviewer or reviewed text;
- `accepted`: reviewed text equals original text;
- `edited`: explicit replacement differs from original;
- `rejected`/`deferred`: no reviewed text, explicit reviewer/timestamp.

## 8. Access matrix

| Action | owner | edit | view | analyze | outsider | OCR worker |
|---|---:|---:|---:|---:|---:|---:|
| View OCR run status | yes | yes | yes | no | no | function only |
| View candidate text | yes | yes | no | no | no | no direct access |
| Review/edit candidate | yes | yes | no | no | no | no |
| Set patient decision | yes | yes | no | no | no | no |
| Finalize transcription | yes | yes | no | no | no | no |
| View encrypted object key | no | no | no | no | no | claim function only |
| Claim/complete OCR | no | no | no | no | no | yes |
| Create clinical/Labs fact | no | no | no | no | no | no |

Candidate and patient-decision text uses the owner/edit helper:

```text
health_compass.app_can_review_document_ocr(profile_id)
```

## 9. D1 worker functions

```text
app_queue_document_ocr(...)
app_claim_document_ocr_run(...)
app_heartbeat_document_ocr_run(...)
app_complete_document_ocr_run(...)
app_fail_document_ocr_run(...)
```

Properties:

- SECURITY DEFINER;
- owner `health_compass_rls_definer`;
- fixed empty search path and `row_security=off`;
- PUBLIC EXECUTE revoked;
- execution granted only to the intended role;
- lease ownership and expiry checks;
- current render run and artifact-manifest checks;
- idempotent identical completion;
- candidates and encrypted provenance inserted atomically;
- bounded candidate count and text bytes;
- content-free audit.

## 10. D2 review functions

```text
app_review_document_ocr_candidate(...)
app_set_document_ocr_patient_decision(...)
app_finalize_document_ocr_review(...)
```

Properties:

- SECURITY DEFINER owned by `health_compass_rls_definer`;
- empty search path and `row_security=off`;
- PUBLIC EXECUTE revoked;
- EXECUTE granted only to `health_compass_app`;
- caller user obtained only from transaction-local RLS context;
- owner/edit authorization and active owner consent;
- static SQL and bounded values;
- optimistic concurrency;
- content-free audit;
- no direct clinical or Labs mutation.

## 11. Safe-page and process boundary

OCR may consume only current `safe_page` artifacts satisfying:

- ready status;
- accepted document;
- current render run;
- `hcenc1` format;
- complete GCM verification;
- repeated PNG validation;
- valid page number.

The source PDF is never passed to OCR.

Tesseract uses sealed input and bounded output/stderr memory files, fixed command arguments, CPU/address-space/file/descriptor/process limits and finite timeouts.

## 12. Strict TSV parser

Expected columns:

```text
level page_num block_num par_num line_num word_num
left top width height conf text
```

The parser enforces exact UTF-8 schema, bounded bytes/rows/text, valid hierarchy, coordinates inside the page, confidence ranges, no control characters and deterministic grouping. It performs no medical correction, translation or unit normalization.

## 13. D1 API

```text
GET /profiles/{profile_id}/documents/{document_id}/ocr/status
GET /profiles/{profile_id}/documents/{document_id}/ocr/candidates
```

The status endpoint follows document metadata access. Candidate text requires owner/edit.

## 14. D2 API and UI

```text
GET   /profiles/{profile_id}/documents/{document_id}/ocr/review
PATCH /profiles/{profile_id}/documents/{document_id}/ocr/candidates/{candidate_id}
PUT   /profiles/{profile_id}/documents/{document_id}/ocr/patient-match
POST  /profiles/{profile_id}/documents/{document_id}/ocr/finalize
```

UI route:

```text
/app/documents/{document_id}/review
```

The UI shows OCR text, page/confidence metadata, explicit review actions and patient decisions. It delivers no raw PDF, safe-page image, TSV, object key or worker stderr.

## 15. Candidate review contract

Actions:

```text
accept
edit
reject
defer
```

All mutations require:

- owner/edit authorization;
- active owner health-data consent;
- exact `expected_updated_at`;
- bounded optional note;
- explicit action enum;
- content-free audit;
- no direct runtime UPDATE grant.

Decisions may be changed until finalization. Finalized review is read-only.

## 16. Patient matching contract

Rules:

- explicit user action only;
- optional bounded explanation;
- reviewer/timestamp provenance;
- optimistic concurrency for both document and decision;
- `unknown` blocks finalization;
- `mismatch` blocks finalization for the profile;
- `not_present` requires explicit acknowledgement;
- no inference from OCR text alone.

## 17. Finalization contract

Finalization requires:

- current accepted document and current succeeded OCR run;
- all candidates accepted, edited or rejected;
- no deferred or `needs_review` candidate;
- patient decision `match` or `not_present`;
- exact current document timestamp;
- exact candidate ID/timestamp manifest;
- exact patient-decision timestamp;
- owner/edit authorization;
- active consent;
- one atomic transaction.

Identical repeated finalization is idempotent and does not create a second audit event.

Finalization changes review state only. It creates no Clinical Context, measurement or Labs row.

## 18. Verification

### D1

Exact head `dc28e9e...` passed CI `#442`:

- compile/Ruff/unit tests;
- frontend lint/typecheck/tests/build;
- migration `0054` boundary;
- full isolated `head → base → head`;
- OCR role, lease, idempotency and RLS integration.

### D2

Exact head `4ecae1fb...` passed CI `#454`:

- compile/Ruff/unit tests;
- frontend lint/typecheck/tests/build;
- migration `0055` boundary;
- full isolated `head → base → head`;
- owner/editor review and patient-decision flow;
- stale-update and revoked-consent rejection;
- mismatch/deferred blocking;
- idempotent finalization;
- content-free audit;
- zero clinical and Labs facts.

## 19. Downgrade safety

Migration `0055` refuses downgrade while human-review data exists:

- any patient decision;
- non-default run review state;
- candidate state other than `needs_review`.

This prevents silent deletion of reviewed text, patient decisions or finalization provenance.

## 20. Production boundary

Production remains:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

D1/D2 merges do not authorize package installation, worker provisioning, migration application or production upload.

## 21. Next stage

```text
HC-017 Slice E — Confirmed Labs Core architecture
```

Slice E must define a new explicit confirmation boundary. It may consume only current finalized D2 transcription with an allowed patient decision and must preserve original analyte/value/unit/reference-range wording and complete document/page/candidate provenance.

No Slice E code should begin before the architecture/security contract is reviewed and merged.

## 22. Final status

```text
D1_IMPLEMENTED
D1_MERGED
D1_CI_VERIFIED
D2_IMPLEMENTED
D2_MERGED
D2_CI_VERIFIED
SLICE_D_NOT_DEPLOYED
NEXT_SLICE_E_ARCHITECTURE
PRODUCTION_UNCHANGED
```
