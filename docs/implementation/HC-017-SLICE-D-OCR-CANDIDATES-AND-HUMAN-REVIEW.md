# HC-017 Slice D — OCR Candidates and Human Review

Status: `D1 IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED; D2 NEXT`  
Created: 2026-07-12  
Updated: 2026-07-12  
Repository main: `a33c3d515b885c6ea0e8f51291a1d25bed77cd7d`  
Repository Alembic head: `0054`  
Production: `b8e868825f378195975e2729f3f36c21a1afa2d0 / 0049`

## 1. Goal

Convert encrypted C2 safe-page images into reviewable OCR transcription without creating medical facts.

```text
encrypted safe_page
→ full GCM verification
→ sealed read-only memory input
→ bounded local OCR
→ encrypted OCR provenance
→ strict TSV parsing
→ needs_review candidates
→ owner/edit human review
→ explicit patient-match decision
```

Slice D stops before Labs confirmation.

## 2. Core invariant

```text
OCR TEXT IS AN UNTRUSTED DRAFT
```

Even accepted or edited OCR text remains document transcription. It is not automatically:

- a diagnosis;
- a condition;
- a medication;
- a body measurement;
- a laboratory observation;
- an AI conclusion.

Clinical or Labs facts require a later independent confirmation transaction.

## 3. Slice decomposition

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
- no human mutation endpoints;
- no automatic Clinical Context, measurement or Labs creation.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-D1-OCR-CANDIDATES-EVIDENCE-2026-07-12.md
```

### D2 — Human Review and Patient Matching

Status: `NEXT / NOT IMPLEMENTED / NOT DEPLOYED`.

Required:

- candidate accept, edit, reject and defer actions;
- optimistic concurrency;
- explicit patient-match decision;
- atomic review finalization;
- content-free audit;
- accessible review UI;
- still no Labs creation.

## 4. OCR engine contract

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

## 6. D1 schema

Migration `0054` adds:

### `document_ocr_runs`

One versioned OCR attempt over one current render run.

Important metadata:

- document, profile and render-run IDs;
- queued/leased/succeeded/failed state;
- attempt and idempotency key;
- input/output manifest hashes;
- engine, version, language and traineddata provenance;
- PSM;
- lease owner/expiry;
- retry and completion timestamps;
- safe error code.

### `document_ocr_artifacts`

Encrypted machine-output provenance, not a user-facing clinical record.

Opaque key:

```text
ocr/{document_uuid}/{ocr_run_uuid}/page-{page_number}.tsv.hcenc
```

Metadata includes safe-page source, page number, sizes, hash, encryption key ID and engine provenance.

### `document_ocr_candidates`

Reviewable text blocks derived from TSV words.

Each row contains:

- OCR run and safe-page provenance;
- page and deterministic candidate index;
- status;
- original OCR text;
- nullable reviewed text;
- minimum and mean confidence;
- bounding box;
- source word count;
- future reviewer metadata;
- timestamps.

Every D1 candidate starts as `needs_review`.

## 7. Access matrix

| Action | owner | edit | view | analyze | outsider | OCR worker |
|---|---:|---:|---:|---:|---:|---:|
| View OCR run status | yes | yes | yes | no | no | function only |
| View candidate text | yes | yes | no | no | no | no direct access |
| Review/edit candidate | D2 | D2 | no | no | no | no |
| View encrypted object key | no | no | no | no | no | claim function only |
| Claim/complete OCR | no | no | no | no | no | yes |
| Create clinical/Labs fact | no | no | no | no | no | no |

Candidate text uses a narrower owner/edit helper:

```text
health_compass.app_can_review_document_ocr(profile_id)
```

## 8. D1 worker functions

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
- static SQL;
- lease ownership and expiry checks;
- current render run and artifact-manifest checks;
- idempotent identical completion;
- conflicting output rejected;
- candidates and encrypted provenance inserted atomically;
- bounded candidate count and text bytes;
- content-free audit.

## 9. Safe-page input contract

OCR may consume only artifacts satisfying all conditions:

- `artifact_type = safe_page`;
- status `ready`;
- document status `accepted`;
- document render status `ready`;
- artifact belongs to current render run;
- object format `hcenc1`;
- complete GCM verification succeeds;
- PNG structural validation succeeds again;
- page number matches accepted document page count.

The source PDF is never passed to OCR.

## 10. Tesseract process boundary

Fixed command shape:

```text
tesseract /proc/self/fd/<sealed_png_fd> stdout \
  --tessdata-dir <fixed_path> \
  --oem 1 \
  --psm <approved_mode> \
  -l rus+eng \
  tsv
```

Controls:

- sealed read-only input memfd;
- bounded output and stderr memfds;
- CPU, address-space, output-size, descriptor and process limits;
- finite per-page timeout;
- process-group kill on timeout;
- fixed minimal environment;
- no filename, document text or stderr in ordinary logs.

## 11. Strict TSV parser

Expected columns:

```text
level page_num block_num par_num line_num word_num
left top width height conf text
```

The parser enforces:

- UTF-8 and exact header;
- bounded total bytes and rows;
- exact column count;
- numeric hierarchy and coordinates;
- confidence range;
- positive dimensions;
- bounding boxes inside the page;
- bounded word and candidate text;
- rejection of control characters;
- deterministic source word ordering;
- no medical correction, translation or unit normalization.

## 12. D1 API

```text
GET /profiles/{profile_id}/documents/{document_id}/ocr/status
GET /profiles/{profile_id}/documents/{document_id}/ocr/candidates
```

The status endpoint follows document metadata access. The candidate endpoint requires owner/edit access.

There is no raw PDF, safe-page or TSV download endpoint.

## 13. D1 verification

Exact head `dc28e9e...` passed CI `#442`:

- Python compile and Ruff;
- backend unit tests;
- frontend lint, typecheck, tests and build;
- migration `0054` boundary;
- full isolated `head → base → head` cycle;
- OCR role, lease, idempotency and RLS integration.

Tests prove:

- OCR worker cannot query OCR tables directly;
- view/analyze/outsider cannot read candidate text;
- stale lease fails;
- identical completion is idempotent;
- audit is content-free;
- OCR creates zero conditions, allergies, medications, supplements and body measurements.

## 14. D2 candidate review contract

Actions:

```text
accept
edit
reject
defer
```

All mutations require:

- owner/edit authorization;
- active health-data consent;
- `expected_updated_at` optimistic concurrency;
- bounded review note;
- explicit action enum;
- content-free audit;
- no direct runtime UPDATE grant.

State behavior:

- accept: reviewed text equals original text;
- edit: reviewed text is explicit user replacement;
- reject: candidate excluded from later extraction;
- defer: unresolved and blocks finalization;
- accepted/edited text remains transcription only.

## 15. D2 patient matching

States:

```text
unknown
match
mismatch
not_present
```

Rules:

- explicit user action only;
- optional bounded explanation;
- reviewer/timestamp/provenance;
- optimistic concurrency;
- `unknown` blocks finalization;
- `mismatch` blocks later Labs confirmation for this profile;
- `not_present` requires explicit acknowledgement;
- no inference solely from OCR text.

## 16. D2 finalization

Finalization must require:

- all candidates accepted, edited or rejected;
- no deferred or `needs_review` candidate;
- explicit patient decision that is not mismatch;
- unchanged candidate manifest;
- current document/render/OCR runs;
- owner/edit authorization;
- active consent;
- one atomic transaction.

Finalization changes review state only. It creates no Clinical Context, measurement or Labs row.

## 17. D2 API outline

```text
PATCH /profiles/{profile_id}/documents/{document_id}/ocr/candidates/{candidate_id}
PUT   /profiles/{profile_id}/documents/{document_id}/ocr/patient-match
POST  /profiles/{profile_id}/documents/{document_id}/ocr/finalize
```

## 18. D2 required tests

- owner/editor successful actions;
- view/analyze/outsider denied;
- missing consent denied;
- stale candidate timestamp rejected without mutation;
- accept/edit/reject/defer semantics;
- reviewed text and notes bounded;
- patient decision optimistic concurrency;
- unknown/mismatch finalization blocked;
- unresolved candidate finalization blocked;
- manifest change blocked;
- current run mismatch blocked;
- repeated finalization idempotent;
- audit contains no OCR or reviewed text;
- no clinical/Labs rows created.

## 19. Production boundary

Production remains:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

D1 merge does not authorize package installation, worker provisioning, migration application or production upload.

## 20. Final status

```text
D1_IMPLEMENTED
D1_MERGED
D1_CI_VERIFIED
D1_NOT_DEPLOYED
D2_NEXT
PRODUCTION_UNCHANGED
```
