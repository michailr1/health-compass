# HC-017 Slice D — OCR Candidates and Human Review

Status: `ARCHITECTURE DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`  
Created: 2026-07-12  
Base main: `ac9e21f3315c4624a845e633c2a90881d348ca30`  
Repository Alembic head: `0053`  
Production: `b8e868825f378195975e2729f3f36c21a1afa2d0 / 0049`

## 1. Goal

Convert encrypted C2 safe-page images into reviewable OCR text candidates without creating medical facts.

```text
encrypted safe_page
→ full GCM verification
→ sealed read-only memory input
→ bounded local OCR
→ encrypted OCR provenance artifact
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

Clinical/Labs facts require a later, separate confirmation transaction.

## 3. OCR engine decision

MVP engine:

```text
local Tesseract 5.x
LSTM engine: --oem 1
output: TSV
```

Rationale:

- no medical document is sent to an external processor;
- TSV provides word confidence and bounding boxes;
- the command-line boundary can be sandboxed similarly to C2 rendering;
- language models can be explicitly provisioned and versioned.

Initial language configuration:

```text
rus+eng
```

Production readiness requires exact installed engine and traineddata versions. Missing language data fails closed; it must not silently fall back to another language.

Official technical references:

- `https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html`;
- `https://tesseract-ocr.github.io/tessdoc/Data-Files.html`;
- `https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html`;
- `https://tesseract-ocr.github.io/tessdoc/Home.html`.

## 4. Slice decomposition

### D1 — OCR extraction foundation

- OCR run and candidate schema;
- dedicated OCR worker role/functions;
- safe-page claim and lease;
- bounded Tesseract execution;
- encrypted TSV provenance artifact;
- strict parser;
- owner/edit-only candidate reads;
- no human mutation endpoints yet.

### D2 — Human review and patient matching

- candidate accept/edit/reject/defer;
- optimistic concurrency;
- page-region review UI;
- explicit patient-match decision;
- atomic review finalization;
- no Labs creation.

## 5. Required PostgreSQL role

```text
health_compass_ocr_worker LOGIN NOBYPASSRLS
```

The role receives:

- CONNECT to the application database;
- schema USAGE;
- EXECUTE only on OCR claim/heartbeat/complete/fail functions;
- no direct SELECT/INSERT/UPDATE/DELETE on documents, artifacts, candidates, profiles, audit or clinical tables;
- no membership in app, migrator, renderer, reconciler or definer roles;
- no BYPASSRLS, SUPERUSER, CREATEDB, CREATEROLE or REPLICATION.

## 6. Proposed schema

Candidate migration after current head:

```text
0054
```

The number must be rechecked against `main` and open migration PRs before implementation.

### `document_ocr_runs`

Purpose: one versioned OCR attempt over one safe-page artifact set.

Suggested columns:

- `id uuid primary key`;
- `document_id uuid`;
- `profile_id uuid`;
- `render_run_id uuid`;
- `status`: queued / leased / succeeded / failed / cancelled;
- `attempt integer`;
- `idempotency_key`;
- `input_artifact_manifest_sha256`;
- `engine_name`;
- `engine_version`;
- `language_spec`;
- `traineddata_manifest_sha256`;
- `psm integer`;
- `lease_owner`;
- `lease_expires_at`;
- `next_attempt_at`;
- `started_at`;
- `completed_at`;
- `safe_error_code`;
- timestamps.

Constraints:

- one active/succeeded run per document/render run/engine/model configuration;
- attempt and lease state consistency;
- safe error-code allowlist;
- status transitions only through restricted functions.

### `document_ocr_artifacts`

Purpose: encrypted machine-output provenance, not user-facing clinical data.

Suggested columns:

- `id uuid primary key`;
- `document_id`, `profile_id`, `ocr_run_id`;
- `page_number`;
- `artifact_type = 'tesseract_tsv'`;
- `storage_backend`;
- opaque `storage_key`;
- `byte_size`, `encrypted_size`, `sha256`;
- `encryption_format`, `encryption_key_id`;
- `engine_name`, `engine_version`;
- `language_spec`;
- status/timestamps/deletion fields.

Storage key:

```text
ocr/{document_uuid}/{ocr_run_uuid}/page-{page_number}.tsv.hcenc
```

The object contains no user filename in its key.

### `document_ocr_candidates`

Purpose: reviewable text blocks derived from TSV words.

Suggested columns:

- `id uuid primary key`;
- `document_id`, `profile_id`, `ocr_run_id`;
- `page_artifact_id`;
- `page_number`;
- `candidate_index`;
- `status`: needs_review / accepted / edited / rejected / deferred;
- `original_text`;
- `reviewed_text` nullable;
- `confidence_min`, `confidence_mean`;
- `left_px`, `top_px`, `width_px`, `height_px`;
- `source_word_count`;
- `reviewed_by_user_id`;
- `reviewed_at`;
- `review_note` optional bounded text;
- `created_at`, `updated_at`.

Candidate text is sensitive medical document text.

## 7. Access matrix

| Action | owner | edit | view | analyze | outsider | OCR worker |
|---|---:|---:|---:|---:|---:|---:|
| View OCR run status | yes | yes | yes | no | no | through function only |
| View candidate text | yes | yes | no | no | no | no direct table access |
| Review/edit candidate | yes | yes | no | no | no | no |
| View encrypted OCR object key | no | no | no | no | no | claim function only |
| Claim/complete OCR run | no | no | no | no | no | yes |
| Create clinical/Labs fact | no in Slice D | no in Slice D | no | no | no | no |

Candidate text requires a narrower helper than normal document metadata:

```text
app_can_review_document_ocr(profile_id)
```

It should allow owner/edit only.

## 8. OCR worker functions

Candidate functions:

```text
app_claim_document_ocr_run(worker_id, lease_seconds, max_attempts)
app_heartbeat_document_ocr_run(run_id, worker_id, expected_lease, lease_seconds)
app_complete_document_ocr_run(run_id, worker_id, expected_lease, provenance, candidates)
app_fail_document_ocr_run(run_id, worker_id, expected_lease, safe_error_code, retryable)
```

Properties:

- `SECURITY DEFINER`;
- owner `health_compass_rls_definer`;
- fixed empty search path;
- PUBLIC EXECUTE revoked;
- app/scanner/renderer/reconciler execution revoked;
- OCR-worker execution only;
- static SQL;
- lease ownership and expiry checked;
- render run, artifact manifest and source hashes checked;
- completion is idempotent for identical run/output manifest;
- different output for a completed run is conflict;
- candidates and provenance inserted atomically;
- candidate payload count and total text bytes are bounded;
- audit contains no OCR text.

## 9. Safe-page input contract

OCR may consume only artifacts satisfying all conditions:

- `artifact_type = safe_page`;
- status `ready`;
- document status `accepted`;
- document render status `ready`;
- artifact belongs to current `render_run_id`;
- encrypted object format `hcenc1`;
- complete GCM verification succeeds;
- PNG structural validation succeeds again before OCR;
- page number is within the accepted document page count.

The source PDF is never passed to OCR.

## 10. Tesseract subprocess boundary

Suggested fixed command shape:

```text
tesseract /proc/self/fd/<sealed_png_fd> stdout \
  --oem 1 \
  --psm <approved_mode> \
  -l rus+eng \
  tsv
```

Implementation rules:

- absolute executable path;
- no shell;
- sealed read-only input memfd;
- bounded output memfd;
- fixed environment and explicit tessdata directory;
- CPU, memory, output, file-descriptor and process limits;
- finite per-page timeout;
- process-group kill on timeout;
- stderr converted to safe codes only;
- no filename, document text or stderr in ordinary logs;
- exact engine and traineddata manifest recorded.

Initial approved page segmentation modes should be a small allowlist. The implementation must not accept arbitrary user-supplied Tesseract options.

## 11. TSV parser contract

Expected columns:

```text
level page_num block_num par_num line_num word_num
left top width height conf text
```

Parser requirements:

- UTF-8 only;
- exact header;
- bounded row count and total bytes;
- fixed column count;
- integer coordinates and hierarchy fields;
- finite confidence in expected range or explicit negative sentinel handling;
- no negative dimensions;
- bounding boxes must fit page dimensions;
- control characters rejected or normalized by a documented rule;
- text length bounded per word and candidate;
- malformed row fails the run safely;
- no formula/CSV interpretation;
- original word order and page provenance retained.

## 12. Candidate aggregation

D1 creates text-line or bounded-block candidates, not analyte/value facts.

Aggregation rules:

- words are grouped by page/block/paragraph/line identifiers;
- empty and negative-confidence rows are skipped under an explicit rule;
- original text is preserved;
- candidate bounding box is the union of source words;
- minimum and mean confidence retained;
- candidate word count retained;
- maximum candidate characters and source words enforced;
- no medical vocabulary correction;
- no automatic translation;
- no unit normalization;
- no dictionary-based rewriting.

## 13. Human review contract

D2 candidate actions:

```text
accept
edit
reject
defer
```

All mutations require:

- owner/edit authorization;
- health-data consent;
- `expected_updated_at` optimistic concurrency;
- bounded review note;
- explicit action enum;
- content-free audit;
- no direct runtime UPDATE grant.

State behavior:

- accept: reviewed text equals original text;
- edit: reviewed text is explicit user-entered replacement;
- reject: candidate excluded from later extraction;
- defer: remains unresolved and blocks review finalization;
- accepted/edited text remains document transcription only.

## 14. Patient matching

Patient matching is separate from candidate review.

Suggested states:

```text
unknown
match
mismatch
not_present
```

Decision includes:

- explicit user action;
- optional bounded explanation;
- reviewer and timestamp;
- optimistic concurrency;
- source/document provenance;
- no storage of unnecessary identifiers in ordinary logs.

Rules:

- `unknown` blocks review finalization;
- `mismatch` blocks later Labs confirmation for the selected profile;
- `not_present` may allow transcription review but requires explicit acknowledgement;
- the system never infers a patient match solely from OCR text.

## 15. Review finalization

Candidate function:

```text
app_finalize_document_ocr_review(
  document_id,
  expected_document_updated_at,
  expected_candidate_manifest,
  patient_match_decision_id
)
```

Finalization requires:

- all candidates are accepted, edited or rejected;
- no deferred/needs_review candidate;
- patient-match decision is explicit and not mismatch;
- candidate manifest has not changed;
- document/render/OCR runs are current;
- owner/edit authorization;
- consent;
- one atomic transaction.

Finalization changes only review state. It creates no Clinical Context or Labs row.

## 16. API outline

D1:

```text
GET /profiles/{profile_id}/documents/{document_id}/ocr/status
GET /profiles/{profile_id}/documents/{document_id}/ocr/candidates
```

D2:

```text
PATCH /profiles/{profile_id}/documents/{document_id}/ocr/candidates/{candidate_id}
PUT   /profiles/{profile_id}/documents/{document_id}/patient-match
POST  /profiles/{profile_id}/documents/{document_id}/ocr/finalize
```

No OCR artifact download route is required.

## 17. UI outline

Review screen:

- selected profile remains visible;
- page number and safe-page thumbnail/region are shown through a later authorized derivative-delivery boundary;
- OCR text and confidence are shown as draft;
- low-confidence candidates are visually marked without medical interpretation;
- actions: Accept, Edit, Reject, Review later;
- patient matching is a separate mandatory section;
- concurrent modification receives a clear reload/compare message;
- finalization explains that confirmed transcription is not yet a health fact.

Slice D must not display raw PDF.

## 18. Logging

Allowed:

- request/run/document/candidate UUIDs;
- page and candidate counts;
- durations;
- engine/model identifiers;
- confidence aggregates without text;
- status transitions;
- safe error codes;
- retry count.

Forbidden:

- OCR text;
- patient names or identifiers;
- filenames;
- source/derived object paths;
- TSV content;
- parser stderr;
- medical values;
- review text or notes.

## 19. Required tests

### Worker and parser

- valid `rus+eng` TSV;
- empty page;
- malformed header/row;
- oversized output/row count/text;
- invalid UTF-8;
- out-of-page bounding box;
- timeout and memory limit;
- missing language data;
- engine nonzero exit;
- corrupted encrypted safe page;
- wrong render run or artifact manifest;
- output encryption and no plaintext artifact.

### PostgreSQL/RLS

- OCR worker has no direct table grants;
- exact execute matrix;
- concurrent claim only once;
- stale lease rejected;
- idempotent completion;
- owner/edit candidate text only;
- view/analyze/outsider get no candidate rows;
- no-user context fails closed;
- candidate completion creates no clinical/measurement/Labs rows;
- full `head → base → head` cycle.

### Human review

- every action and transition;
- stale `expected_updated_at` conflict;
- invalid edit text;
- patient-match unknown/mismatch blocks finalization;
- deferred candidate blocks finalization;
- manifest change blocks finalization;
- duplicate finalization is idempotent;
- content-free audit.

## 20. Production boundary

Slice D implementation PR is not a rollout PR.

It must not:

- enable document upload in production;
- install Tesseract or language data on production;
- create production OS users or credentials;
- apply production migrations;
- expose safe-page or OCR download endpoints;
- create Labs observations.

## 21. Stop conditions

Stop merge or rollout when:

- OCR receives raw PDF or unauthenticated bytes;
- arbitrary OCR command options are accepted;
- output is unbounded;
- OCR text enters logs;
- candidate text is visible to view/analyze;
- worker has direct table access;
- candidate status begins as accepted;
- patient matching is inferred automatically;
- OCR creates clinical/Labs facts;
- optimistic concurrency is absent;
- migration has multiple heads;
- exact-head CI and negative PostgreSQL tests are absent.

## 22. Current status

```text
SLICE_D_ARCHITECTURE_DEFINED
SLICE_D_NOT_IMPLEMENTED
PRODUCTION_UNCHANGED
```