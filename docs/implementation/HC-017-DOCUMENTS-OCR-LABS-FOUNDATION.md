# HC-017 — Human Documents, OCR Review and Labs Foundation

Status: `ARCHITECTURE DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`  
Created: 2026-07-12  
Architecture baseline: `d32569f3eabbeeee5f803dde11d9b56ccf291cbe`  
Current production Alembic target: `0049`  
Next migration candidate: `0050`, only after rechecking the actual head when implementation starts

## 1. Goal

Build the first secure Human Health document flow:

```text
Upload analysis
→ quarantine
→ malware and format validation
→ OCR processing
→ human review
→ explicit confirmation
→ confirmed lab observations
→ metric dynamics
→ contextual intake
```

The first useful outcome is not “AI read a PDF”. It is a set of user-confirmed laboratory observations with a complete provenance chain back to the uploaded document.

## 2. Non-goals for HC-017 foundation

The first implementation does not include:

- automatic diagnosis or treatment advice;
- automatic confirmation of OCR values;
- external LLM processing;
- editable doctor reports;
- Oura or other wearable integrations;
- bulk upload;
- Office documents, archives, HTML or SVG;
- automatic unit conversion;
- automatic merging of conflicting observations;
- automatic reassignment of a document to another profile;
- Human/Pet mixed processing;
- public links to original files.

## 3. Product invariants

1. A document is untrusted input until all validation and malware checks succeed.
2. OCR output always starts as `needs_review` and is not a clinical fact.
3. A user must explicitly confirm every value that becomes a lab observation.
4. Original text, OCR text, patient names, values and reference ranges are not written to ordinary application logs.
5. The selected Human profile is visible during upload and review.
6. A Pet profile cannot use this pipeline.
7. Medical interpretation is outside the foundation slice.
8. Free-text source values are preserved; normalization never silently overwrites them.
9. Every confirmed observation retains document, page and extraction provenance.
10. Destructive operations use explicit confirmation, owner checks and optimistic concurrency.

## 4. Initial upload contract

### Supported formats

The first slice accepts only:

- PDF: `application/pdf`;
- JPEG: `image/jpeg`;
- PNG: `image/png`.

The following are rejected:

- ZIP/RAR/7z and other archives;
- DOC/DOCX/XLS/XLSX/PPT/PPTX;
- HTML, XML and SVG;
- executables and scripts;
- password-protected or encrypted PDF files;
- files whose extension, declared MIME type and detected magic bytes disagree.

HEIC may be added later after a deterministic decoder and resource-limit tests are available.

### Initial configurable limits

Default production limits for the first slice:

- one file per upload request;
- maximum file size: `20 MiB`;
- maximum PDF pages: `50`;
- maximum image dimensions: `25 megapixels`;
- maximum processing time and memory per page are enforced by the worker;
- request streaming is mandatory; the whole file must not be loaded into application memory.

The limits are configuration values with fail-safe production validation. Raising them requires performance and decompression/resource-exhaustion tests.

### Filename handling

- The original filename is treated as sensitive user data.
- It may be stored for display but is never used as a filesystem or object-storage key.
- It is never included in ordinary access logs, error logs or metrics labels.
- Storage keys are generated server-side from random identifiers.
- Path separators, control characters and Unicode confusables in filenames do not affect storage paths.

## 5. Quarantine-first pipeline

A successful HTTP upload does not mean the document is accepted.

Canonical state machine:

```text
uploading
→ quarantined
→ scanning
→ accepted
→ ocr_queued
→ processing
→ review_required
→ confirmed
```

Terminal or side states:

```text
rejected
failed
voided
deletion_pending
erased
```

Rules:

- Newly received bytes are written only to a quarantine namespace.
- Quarantine objects are not available for browser preview or download.
- Malware scanning and structural validation fail closed.
- If the scanner is unavailable, the document remains quarantined and no OCR job starts.
- A detected threat moves the record to `rejected`; the object is inaccessible and scheduled for secure deletion.
- OCR runs only on an accepted object or a safe rasterized derivative.
- The frontend may display metadata and processing status but never renders an unaccepted original.
- Retrying processing creates a new idempotent processing attempt; it does not duplicate confirmed facts.

The scanner implementation may be ClamAV or another approved engine. The contract is vendor-neutral; production rollout requires a real scanner and cannot use a stub.

## 6. Storage boundary

### Required properties

Production document storage must be:

- private and outside the public web root;
- inaccessible through guessable URLs;
- encrypted in transit;
- protected by host/provider access controls;
- backed up according to the infrastructure retention policy;
- accessed only through the backend and the restricted processing worker;
- separated into quarantine, accepted-original and derived namespaces;
- capable of deleting all artifacts by document identifier.

An S3-compatible private object store is the target interface. A private local filesystem adapter is allowed only for development and isolated tests unless a separate production storage review explicitly approves it.

### Object identifiers

Storage paths use opaque server-generated identifiers, for example:

```text
quarantine/{document_uuid}/original
accepted/{document_uuid}/original
derived/{document_uuid}/{run_uuid}/page-{page_number}.png
derived/{document_uuid}/{run_uuid}/ocr.json
```

A user-supplied filename, email, profile name or medical value must never appear in the key.

### Download and preview

- Every original-file request is authorized against the database before storage access.
- The first implementation streams the file through the backend or issues a very short-lived single-object signed URL after authorization.
- Signed URLs, if enabled, expire in at most 60 seconds and are never stored in logs or analytics.
- Responses use `Cache-Control: private, no-store`.
- Downloads use safe `Content-Disposition` handling.
- Browser preview uses rasterized safe page images, not embedded execution of the raw PDF.

## 7. Consent and external processing

- Upload, OCR and confirmation require active health-data processing consent.
- Withdrawal of consent blocks new uploads, new OCR runs and confirmation.
- Withdrawal does not block owner-controlled deletion.
- The first HC-017 implementation uses only local or infrastructure-controlled OCR.
- Sending a document or extracted medical data to an external OCR/LLM provider requires a separate provider review, data-processing terms and explicit revocable external-processing consent.
- External AI consent is never inferred from ordinary health-data consent.

## 8. Access matrix

The profile permission matrix is intentionally narrower for raw documents than for confirmed structured data.

| Action | owner | edit | view | analyze | outsider |
|---|---:|---:|---:|---:|---:|
| Upload document | yes | yes | no | no | no |
| View processing status | yes | yes | yes | no | no |
| View/download accepted original | yes | yes | yes | no | no |
| View OCR candidates | yes | yes | yes | no | no |
| Edit OCR candidates | yes | yes | no | no | no |
| Confirm candidates as lab observations | yes | yes | no | no | no |
| View confirmed lab observations | yes | yes | yes | yes | no |
| Void document/results | yes | yes | no | no | no |
| Retry processing | yes | yes | no | no | no |
| Permanently erase document/results | yes | no | no | no | no |

Additional rules:

- Unauthorized and cross-profile access returns the same not-found shape used elsewhere to reduce enumeration.
- `analyze` can access only confirmed normalized observations, never raw files or OCR drafts.
- The selected profile is resolved and authorized before any storage operation.
- Object-storage access never relies on a client-provided profile identifier alone.

## 9. Worker security boundary

Background processing must not run with the application database role or migrator credentials.

Target role:

```text
health_compass_worker LOGIN NOBYPASSRLS
```

The worker:

- has no general interactive access to user/profile/clinical tables;
- claims jobs through narrowly scoped functions or views;
- receives only the identifiers and storage references required for the claimed job;
- cannot enumerate arbitrary profiles or documents;
- writes processing results through constrained completion functions;
- cannot confirm clinical facts;
- cannot grant permissions or alter identities;
- never receives application session cookies;
- uses separate database and storage credentials;
- has bounded concurrency, lease timeouts and retry limits.

Any `SECURITY DEFINER` worker function follows existing invariants:

- owned by `health_compass_rls_definer`;
- fixed empty `search_path`;
- explicit `row_security` behavior;
- no PUBLIC EXECUTE;
- static allowlisted operations;
- negative privilege tests.

## 10. Proposed data model

Names are canonical targets; exact SQL is defined in the implementation PR.

### `profile_documents`

One row per uploaded source document.

Core fields:

- `id uuid primary key`;
- `profile_id uuid not null`;
- `uploaded_by_user_id uuid not null`;
- `status`;
- `original_filename`;
- `declared_media_type`;
- `detected_media_type`;
- `byte_size`;
- `sha256`;
- `storage_backend`;
- `quarantine_storage_key` nullable;
- `accepted_storage_key` nullable;
- `page_count` nullable;
- `scanner_engine` and `scanner_version` nullable;
- `scanned_at` nullable;
- `failure_code` nullable and non-sensitive;
- `created_at`, `updated_at`;
- `voided_at`, `voided_by_user_id` nullable;
- `deletion_requested_at`, `erased_at` nullable.

The table contains no OCR body and no extracted medical values.

### `document_processing_jobs`

Durable queue and retry history.

Core fields:

- `id`;
- `document_id`;
- `job_type`: `scan`, `inspect`, `render`, `ocr`;
- `status`: `queued`, `leased`, `succeeded`, `failed`, `cancelled`;
- `attempt`;
- `idempotency_key`;
- `input_sha256`;
- `engine_name`, `engine_version`;
- `lease_owner`, `lease_expires_at`;
- `started_at`, `completed_at`;
- `error_code` only, with no document content.

Unique idempotency is based on document, job type, input hash and engine version.

### `document_extraction_runs`

One immutable metadata row per OCR execution.

Core fields:

- `id`;
- `document_id`;
- `processing_job_id`;
- `engine_name`, `engine_version`;
- `input_sha256`;
- `output_storage_key` for protected derived data;
- `status`;
- `created_at`, `completed_at`.

Raw OCR output is protected derived data, not an application log.

### `document_observation_candidates`

Editable review candidates. These are not clinical facts.

Core fields:

- `id`;
- `document_id`;
- `extraction_run_id`;
- `page_number`;
- `source_region` or bounding-box coordinates;
- `candidate_type`;
- source-preserving fields such as analyte, value, unit, reference range and observed date;
- optional canonical analyte/code mapping;
- confidence values per field;
- `review_status`: `needs_review`, `confirmed`, `rejected`, `superseded`;
- `reviewed_by_user_id`, `reviewed_at`;
- `created_at`, `updated_at`.

Candidate updates require `expected_updated_at`.

### `lab_observations`

Only user-confirmed facts.

Core fields:

- `id`;
- `profile_id`;
- `source_document_id`;
- `source_candidate_id`;
- `confirmed_by_user_id`;
- source-preserving analyte name;
- optional canonical analyte identifier;
- numeric result and/or text result;
- source unit;
- reference lower/upper/text;
- source-provided abnormal flag, if present;
- collection date/time and its precision;
- laboratory name, if confirmed;
- provenance and confirmation timestamps;
- `created_at`, `updated_at`, void fields.

Rules:

- Numeric and text results are modeled separately and validated.
- Source units are preserved.
- The first slice performs no silent unit conversion.
- Results with incompatible units do not share one metric series.
- Reference ranges belong to the source observation and are not universal norms.
- Abnormal flags are source facts, not diagnoses.

### Audit

Document audit events are content-free and record actions such as:

- uploaded;
- scan accepted/rejected;
- OCR completed/failed;
- review started;
- candidates confirmed/rejected;
- document voided;
- erasure requested/completed.

Ordinary audit payloads do not repeat filenames, OCR text, patient names, analytes, values, units or ranges.

## 11. RLS and database privileges

All new profile-owned tables require:

- `ENABLE ROW LEVEL SECURITY`;
- `FORCE ROW LEVEL SECURITY`;
- explicit application grants;
- owner/edit/view/analyze/outsider PostgreSQL integration tests;
- no access without transaction-local user context.

Privilege principles:

- The application role cannot directly update system-managed processing fields.
- The worker role cannot directly confirm observations.
- Permanent erasure is not implemented as broad table DELETE grants.
- Storage keys are never exposed through unrestricted list APIs.
- Cross-profile hashes cannot be used to reveal that another user uploaded the same file.
- Duplicate-file detection, if added, is scoped only to the same profile.

## 12. Patient matching

Patient matching is a safety gate, not identity proof.

OCR may extract:

- patient name;
- date of birth;
- sex;
- document date;
- laboratory identifiers.

Behavior:

- match: normal review;
- identifiers missing: show a warning and allow explicit confirmation;
- mismatch: block ordinary confirmation until the user reviews/corrects extracted identifiers;
- owner may explicitly acknowledge a remaining mismatch with a dedicated confirmation;
- editor cannot override a remaining mismatch;
- no automatic search across other users or profiles;
- no silent profile reassignment.

The mismatch acknowledgement is content-free in audit and uses an explicit boolean, not a free-text reason.

## 13. OCR review contract

The review screen shows, for each candidate:

- safe source-page preview and highlighted region;
- extracted analyte;
- extracted value;
- unit;
- reference range;
- collection date;
- field-level confidence;
- source document and page;
- validation errors.

Rules:

- Low-confidence values cannot be bulk-confirmed.
- Users may edit fields before confirmation.
- Save-draft does not create lab observations.
- Confirmation is atomic for the selected candidate versions.
- A stale candidate returns a controlled conflict and confirms nothing from that request.
- Partial confirmation is allowed.
- Reprocessing creates a new extraction run and supersedes unconfirmed candidates; it does not overwrite confirmed observations.
- A document instruction such as “ignore previous rules” is treated as document text, never as a system instruction.

## 14. Confirmation transaction

Confirming selected candidates performs one transaction:

1. authorize profile write access;
2. verify active consent;
3. verify document state is `review_required` or partially confirmed;
4. verify all `expected_updated_at` values;
5. validate patient-match gate;
6. create or update confirmed `lab_observations`;
7. mark selected candidates confirmed;
8. write content-free audit events;
9. update document aggregate status.

Any failure rolls back the entire requested confirmation set.

## 15. Metric dynamics

Metric dynamics is enabled only after confirmed data exists.

Initial rules:

- group by canonical analyte when available, otherwise by normalized source analyte within the same profile;
- preserve and display the source wording;
- graph only compatible numeric observations with compatible units;
- do not silently convert units;
- show the source-specific reference range for each point;
- provide a tabular equivalent to every chart;
- link every point to its source document and confirmation provenance;
- do not label a trend as improvement, deterioration or causation without a later evidence-based interpretation layer.

## 16. API target

Exact response schemas are defined during implementation. Planned routes:

```text
POST   /profiles/{profile_id}/documents
GET    /profiles/{profile_id}/documents
GET    /profiles/{profile_id}/documents/{document_id}
GET    /profiles/{profile_id}/documents/{document_id}/download
POST   /profiles/{profile_id}/documents/{document_id}/retry
GET    /profiles/{profile_id}/documents/{document_id}/candidates
PATCH  /profiles/{profile_id}/documents/{document_id}/candidates/{candidate_id}
POST   /profiles/{profile_id}/documents/{document_id}/confirm
POST   /profiles/{profile_id}/documents/{document_id}/void
DELETE /profiles/{profile_id}/documents/{document_id}
GET    /profiles/{profile_id}/lab-observations
GET    /profiles/{profile_id}/lab-metrics/{metric_id}
```

The upload endpoint uses streamed multipart input in the first slice. Direct browser-to-object-store upload is deferred until a separate signed-upload threat review.

## 17. Deletion lifecycle

The first MVP provides two distinct actions.

### Remove from profile

- available to owner and editor;
- hides the document and imported observations from active views;
- retains protected history;
- uses optimistic concurrency.

### Delete permanently

- owner only;
- remains available after consent withdrawal;
- requires explicit irreversible confirmation and `expected_updated_at`;
- immediately denies all user access by moving the record to `deletion_pending`;
- cancels or invalidates queued/leased processing jobs;
- deletes quarantine and accepted originals;
- deletes rendered pages, OCR output and extraction artifacts;
- deletes unconfirmed candidates;
- deletes confirmed lab observations whose sole provenance is that document;
- scrubs value-bearing audit/revision data;
- leaves only a content-free technical tombstone;
- retries storage deletion idempotently until complete.

The first slice does not offer “delete source but keep imported facts”, because that would require a separate provenance-retention contract and distinct user warning.

Backup lifecycle is documented separately and is not added to the destructive UI warning.

## 18. Logging and observability

Allowed operational fields:

- request ID;
- internal document/job/run IDs;
- state transition;
- byte count;
- page count;
- engine and version;
- duration;
- non-sensitive error code;
- retry count.

Forbidden in ordinary logs and metrics labels:

- original filename;
- document text or OCR output;
- patient name/date of birth;
- analyte names and values;
- units and reference ranges;
- storage signed URLs;
- object-store credentials;
- medical values in exception messages.

Metrics are aggregate and low-cardinality. Processing failures use safe codes, while detailed sensitive diagnostics stay in access-controlled derived artifacts when necessary.

## 19. Minimum tests

### Upload and parser safety

- supported PDF/JPEG/PNG accepted;
- extension/MIME/magic-byte mismatch rejected;
- oversize file rejected during streaming;
- PDF page limit enforced;
- oversized image dimensions rejected;
- encrypted PDF rejected;
- path traversal filename cannot affect storage path;
- malformed/decompression-bomb samples fail within resource limits.

### Quarantine and malware

- quarantined document cannot be previewed or downloaded;
- scanner unavailable fails closed;
- infected sample is rejected and never reaches OCR;
- accepted sample moves atomically to accepted storage;
- duplicate retry does not duplicate jobs.

### Tenant and privilege matrix

- owner/edit/view/analyze/outsider matrix for every route;
- `analyze` cannot access original or OCR candidates;
- no user context returns no rows;
- cross-profile document IDs return not found;
- worker cannot enumerate profiles or confirm facts;
- app cannot update worker-managed columns directly.

### OCR and confirmation

- OCR output remains `needs_review`;
- stale candidate update/confirmation conflicts without partial writes;
- low-confidence candidate requires individual action;
- partial confirmation creates only selected observations;
- reprocessing does not overwrite confirmed observations;
- patient mismatch gate and owner-only override work;
- prompt-injection text cannot alter processing rules.

### Deletion

- editor cannot permanently erase;
- owner can erase after consent withdrawal;
- stale erasure request deletes nothing;
- access is denied immediately after `deletion_pending`;
- raw, derived, candidate and sole-provenance lab data are removed;
- repeated deletion jobs are idempotent;
- only a content-free tombstone remains.

### CI and operations

- full migration cycle includes new roles/functions/grants;
- one Alembic head;
- storage adapter contract tests;
- logs contain no filenames, OCR text or medical values;
- exact-SHA CI before deployment;
- backup and restore-listing check before production migration.

## 20. Delivery slices

### Slice A — Architecture and contracts

Status: this document.

- threat model;
- upload limits;
- storage boundary;
- access matrix;
- proposed schema;
- worker boundary;
- OCR confirmation and deletion contracts.

No product code and no migration.

### Slice B — Secure document intake foundation

First implementation PR:

- migration for `profile_documents`, processing jobs and content-free audit;
- RLS and privilege matrix;
- storage adapter interface;
- streamed upload to quarantine;
- format/size/magic-byte validation;
- document list/detail/status UI;
- no OCR and no real lab observations yet;
- demo/test files only.

### Slice C — Scanner and safe rendering

- production malware scanner;
- accepted-object promotion;
- safe page rasterization;
- retry and failure UI;
- restricted worker role and job leasing.

### Slice D — OCR candidates and human review

- extraction runs;
- candidate schema;
- page-region review UI;
- confidence and validation;
- autosave with optimistic concurrency;
- no automatic confirmation.

### Slice E — Confirmed Labs core

- atomic confirmation;
- lab observations and provenance;
- patient matching gate;
- list/detail UI;
- document-linked deletion lifecycle.

### Slice F — Metric dynamics

- compatible series grouping;
- chart and table;
- source-specific reference bands;
- document/provenance links;
- no medical interpretation.

### Slice G — Production rollout

- independent security review;
- exact-SHA CI;
- storage/scanner readiness evidence;
- backup-first migration;
- cross-user production-safe probes;
- manual owner smoke with disposable documents;
- canonical evidence update.

## 21. Implementation stop conditions

Do not merge or deploy when any of the following is true:

- upload size/type limits are absent or client-only;
- files bypass quarantine;
- scanner failure permits OCR;
- raw document is publicly addressable;
- object access is not authorized through the profile boundary;
- `analyze` can access raw documents or OCR drafts;
- OCR candidate becomes a fact without explicit confirmation;
- original text is silently replaced by normalization;
- provenance is lost;
- worker uses migrator or application credentials;
- worker has broad profile-table access;
- document contents or medical values appear in logs;
- permanent deletion leaves accessible raw/derived artifacts;
- deletion can be performed by editor/view/analyze;
- migration introduces multiple heads;
- PostgreSQL tenant tests or migration cycle are missing;
- production storage/scanner uses a stub;
- external OCR/LLM receives data without separate consent and provider approval.

## 22. Next action

After this architecture document is reviewed and merged, create Slice B from the then-current `main`.

Before assigning migration `0050`, recheck:

- current main SHA;
- current Alembic heads;
- open PRs that may own a migration number;
- production code and Alembic state;
- availability of an approved private storage backend for later production rollout.
