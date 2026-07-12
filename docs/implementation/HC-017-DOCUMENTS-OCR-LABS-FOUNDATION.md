# HC-017 — Human Documents, OCR Review and Labs Foundation

Status: `SLICE B MERGED / NOT DEPLOYED / PRODUCTION UPLOAD DISABLED`  
Created: 2026-07-12  
Architecture PR: `#47`  
Slice B implementation PR: `#48`  
Slice B merge commit: `ccabab77cf929456a74b69c3478c71f92f167f78`  
Verified implementation head: `46c5ea89d35cc85be0af3b80a9c56f40d5705ac5`  
CI: `#402 — passed`  
Repository Alembic head: `0050`  
Production application target: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

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

The first useful medical result is not “AI read a PDF”. It is a set of user-confirmed laboratory observations with a complete provenance chain back to the source document.

## 2. Current delivery status

### Slice A — Architecture and contracts

Status: `MERGED` through PR `#47`.

Defined:

- upload threat model;
- quarantine-first processing;
- private storage boundary;
- owner/edit/view/analyze/outsider matrix;
- separate restricted worker role;
- OCR human-review contract;
- patient-matching gate;
- provenance requirements;
- Labs and metric-dynamics principles;
- raw/derived/confirmed deletion lifecycle;
- logging restrictions and rollout stop conditions.

### Slice B — Secure Document Intake Foundation

Status: `IMPLEMENTED / MERGED / NOT DEPLOYED` through PR `#48`.

Implemented:

- migration `0049 → 0050`;
- `profile_documents` metadata table;
- `document_processing_jobs` durable intake queue;
- `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`;
- document-specific visibility helper excluding `analyze`;
- no direct runtime UPDATE or DELETE on document tables;
- streamed quarantine upload for development and isolated tests;
- PDF, JPEG and PNG validation;
- server-side request and file-size limits;
- opaque UUID-based storage keys;
- private local development/test storage adapter;
- rollback cleanup for route failure, commit failure and request cancellation;
- content-free document audit;
- document-aware duplicate-account activity assessment;
- capabilities, upload, list and detail APIs;
- minimal `/app/documents` UI;
- full backend, frontend, migration-cycle and PostgreSQL RLS tests.

Explicitly not implemented:

- production document storage;
- malware scanner;
- preview or download;
- PDF parsing in the web process;
- safe rasterization;
- processing worker;
- OCR;
- extraction candidates;
- patient matching;
- confirmed laboratory observations;
- metric dynamics;
- document void or permanent-erasure endpoints;
- production rollout.

## 3. Production safety gate

Slice B is intentionally fail-safe:

```text
DOCUMENT_UPLOAD_ENABLED=false
```

Outside development, application configuration rejects `DOCUMENT_UPLOAD_ENABLED=true` during startup validation.

Therefore merging migration `0050` and the UI into the repository does not authorize production deployment or production upload enablement.

Production remains:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
```

No VPS deployment task has been issued for Slice B.

## 4. Product invariants

1. A document is untrusted input until structural validation and malware scanning succeed.
2. OCR output always begins as `needs_review` and is not a clinical fact.
3. Every value becoming a lab observation requires explicit human confirmation.
4. Original text, OCR text, patient identifiers and medical values are forbidden in ordinary logs.
5. The selected Human profile remains visible during upload and review.
6. Pet profiles cannot use the Human document pipeline.
7. Medical interpretation is outside the foundation slices.
8. Source wording and units are preserved; normalization never silently overwrites them.
9. Every confirmed observation retains document, page and extraction provenance.
10. Destructive actions require explicit confirmation, owner checks and optimistic concurrency.

## 5. Slice B upload contract

Supported formats:

- PDF: `application/pdf`;
- JPEG: `image/jpeg`;
- PNG: `image/png`.

Rejected:

- archives;
- Office documents;
- HTML, XML and SVG;
- executables and scripts;
- unsupported signatures;
- extension, declared MIME and magic-byte mismatch.

Current limits:

- one file per request;
- maximum source file size: `20 MiB`;
- maximum complete multipart request: source limit plus bounded multipart overhead;
- maximum image dimensions: `25 megapixels`;
- PDF page counting is deferred to the restricted inspection worker in Slice C;
- PDF remains in quarantine and is not parsed by the web process.

Request safety:

- oversized `Content-Length` is rejected before multipart parsing;
- chunked uploads are counted and stopped when the body limit is exceeded;
- unrelated API routes are not affected by the document-body middleware;
- the full source file is not loaded into application memory;
- temporary and final quarantine artifacts are removed on failure.

## 6. Filename and storage rules

- Original filename is display-only sensitive metadata.
- It never becomes a filesystem or object-storage path.
- Path separators, control characters and traversal sequences are neutralized.
- Storage key is generated only from a server-side UUID:

```text
quarantine/{document_uuid}/original
```

- Development/test local directories use mode `0700`.
- Development/test quarantine objects use mode `0600`.
- Storage keys, SHA-256 hashes and internal paths are absent from API responses.
- Ordinary audit payloads do not repeat filenames, file contents or medical values.

The local adapter is not approved as the final production storage architecture. Slice C must choose and review the production private-storage boundary.

## 7. Quarantine-first state model

Target lifecycle:

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

Side or terminal states:

```text
rejected
failed
voided
deletion_pending
erased
```

Slice B creates only `quarantined` metadata plus an idempotent `inspect` job. It does not promote a document to `accepted`.

Quarantined objects:

- cannot be previewed;
- cannot be downloaded;
- cannot start OCR;
- remain inaccessible to the `analyze` role;
- require Slice C scanner and safe-inspection implementation before promotion.

## 8. Access matrix

| Action | owner | edit | view | analyze | outsider |
|---|---:|---:|---:|---:|---:|
| Upload in enabled development/test environment | yes | yes | no | no | no |
| View Slice B document metadata/status | yes | yes | yes | no | no |
| View or download original | not implemented | not implemented | not implemented | no | no |
| View OCR candidates | not implemented | not implemented | not implemented | no | no |
| Confirm lab observations | not implemented | not implemented | no | no | no |
| Permanently erase document/results | not implemented | no | no | no | no |

Database enforcement:

```text
health_compass.app_can_view_document(profile_id)
```

Properties:

- `SECURITY DEFINER`;
- owner `health_compass_rls_definer`;
- fixed empty `search_path`;
- `row_security=off`;
- PUBLIC EXECUTE revoked;
- execution granted only to the runtime application role;
- permissions restricted to owner/edit/view.

Unauthorized or cross-profile access uses a controlled not-found shape.

## 9. Slice B data model

### `profile_documents`

Stores metadata only:

- document and profile identifiers;
- uploader;
- lifecycle status;
- display filename;
- declared and detected media type;
- byte count and SHA-256;
- storage backend and opaque keys;
- page count when later available;
- non-sensitive failure code;
- timestamps and future void/erasure fields.

It stores no OCR text and no extracted medical values.

### `document_processing_jobs`

Stores durable job metadata:

- document and profile identifiers;
- job type;
- state and attempt count;
- idempotency key;
- input hash;
- future engine/version and lease metadata;
- non-sensitive error code;
- timestamps.

A composite foreign key binds `(document_id, profile_id)` to the same document row, preventing a job from being associated with another profile.

## 10. Database privileges and account lifecycle

Both Slice B tables have RLS and FORCE RLS.

Runtime role:

- may SELECT only through document visibility RLS;
- may INSERT only through edit authorization;
- has no direct UPDATE;
- has no direct DELETE.

`profile_documents` is included in duplicate-account meaningful-activity assessment. A profile containing a document can no longer be incorrectly classified as empty during duplicate-account absorption.

The existing HC-015 assessment function is preserved under an internal pre-document name and wrapped by the new head implementation. Both sensitive functions retain definer ownership, fixed settings and revoked PUBLIC EXECUTE.

## 11. Transaction and artifact consistency

The source object is external to PostgreSQL, so Slice B adds transaction-bound cleanup hooks.

A quarantine object is deleted when:

- validation or route execution fails;
- the final request database commit fails;
- the client/request task is cancelled.

Cleanup failures:

- do not expose filename or path;
- emit only the safe event `request_rollback_cleanup_failed`;
- do not replace the original database/request error.

The parent document row is explicitly flushed before the dependent processing job while remaining inside one request transaction.

## 12. API implemented in Slice B

```text
GET  /profiles/{profile_id}/document-intake/capabilities
POST /profiles/{profile_id}/documents
GET  /profiles/{profile_id}/documents
GET  /profiles/{profile_id}/documents/{document_id}
```

Capabilities are profile-aware:

- owner/edit may receive `upload_enabled=true` only when development configuration explicitly enables it;
- view/analyze receive `upload_enabled=false`;
- outsider receives not found.

There is no download, preview, retry, OCR, confirmation, void or deletion route in Slice B.

## 13. UI implemented in Slice B

Route:

```text
/app/documents
```

The UI provides:

- navigation item “Документы”;
- explicit PDF/JPEG/PNG and size guidance;
- profile-aware upload control;
- quarantine status list;
- clear message that preview and OCR are unavailable.

The UI does not pretend that an unavailable feature is complete. In production, the upload control remains disabled by backend capabilities.

## 14. Verification evidence

Exact reviewed implementation head:

```text
46c5ea89d35cc85be0af3b80a9c56f40d5705ac5
```

CI run:

```text
#402 — success
```

Passed:

- Python compile;
- Ruff full backend source;
- backend unit tests;
- frontend full lint;
- TypeScript typecheck;
- frontend tests;
- production frontend build;
- migration boundary tests;
- isolated full migration cycle `head → base → head`;
- all PostgreSQL integration and RLS tests.

Coverage includes:

- supported file validation;
- magic-byte and extension mismatch;
- oversized body before multipart parsing;
- chunked body limit;
- private file modes and opaque keys;
- owner/edit/view/analyze/outsider matrix;
- no direct document UPDATE/DELETE;
- no-user-context fail closed;
- hardened function ownership and grants;
- duplicate-account activity regression;
- request rollback cleanup;
- profile-aware UI capabilities.

Canonical implementation evidence:

`docs/implementation/HC-017-SLICE-B-IMPLEMENTATION-2026-07-12.md`

## 15. Next stage — Slice C

Slice C remains `NOT IMPLEMENTED`.

Required scope:

- approved production private storage adapter;
- real malware scanner;
- scanner unavailable = fail closed;
- restricted worker role and credentials;
- safe structural PDF inspection;
- PDF page limit enforcement;
- safe rasterized page derivatives;
- job claiming, leases, retries and bounded resource usage;
- accepted-object promotion only after all checks pass;
- failure and retry UI;
- no OCR confirmation yet.

Before coding Slice C:

1. perform an independent review of Slice B diff and security boundaries;
2. choose the production storage model;
3. choose and threat-review the scanner;
4. define worker provisioning and credential isolation;
5. verify current main and Alembic head;
6. create a new implementation branch from current `main`.

## 16. Slice C stop conditions

Do not merge or deploy when:

- production storage is public or inside the web root;
- scanner is a stub or can fail open;
- scanner outage permits promotion or OCR;
- worker uses application or migrator credentials;
- worker can enumerate arbitrary profiles;
- raw PDF is embedded directly in the browser;
- PDF page, CPU, memory or timeout limits are absent;
- accepted promotion is not atomic and idempotent;
- signed URLs or object keys appear in logs;
- cross-profile storage access is possible;
- document contents or medical values appear in ordinary logs;
- migration creates multiple heads;
- exact-head CI or PostgreSQL negative tests are missing.

## 17. Later slices

### Slice D — OCR candidates and human review

- extraction runs;
- protected OCR artifacts;
- `needs_review` candidates;
- page-region review UI;
- field-level confidence;
- optimistic concurrency;
- no automatic confirmation.

### Slice E — Confirmed Labs core

- atomic explicit confirmation;
- patient matching gate;
- source-preserving analyte, value, unit and range;
- provenance-linked `lab_observations`;
- document-linked deletion lifecycle.

### Slice F — Metric dynamics

- compatible numeric series only;
- no silent unit conversion;
- chart plus accessible table;
- source-specific reference ranges;
- provenance links;
- no medical interpretation.

### Slice G — Production rollout

- independent security review;
- production storage and scanner readiness evidence;
- exact-SHA CI;
- backup-first migration;
- controlled tenant and worker privilege probes;
- manual owner smoke with disposable documents;
- canonical production evidence.

## 18. Final current verdict

```text
HC017_SLICE_B_MERGED
HC017_NOT_DEPLOYED
PRODUCTION_DOCUMENT_UPLOAD_DISABLED
NEXT: INDEPENDENT_REVIEW_THEN_SLICE_C
```
