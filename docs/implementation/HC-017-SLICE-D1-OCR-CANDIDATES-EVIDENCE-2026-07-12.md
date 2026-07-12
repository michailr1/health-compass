# HC-017 Slice D1 — Local OCR Candidates Implementation Evidence

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`  
Date: 2026-07-12  
Source PR: `#56`  
Verified implementation head: `dc28e9e220dd51264e6dab1244ce8d8696f501b2`  
Merge commit: `a33c3d515b885c6ea0e8f51291a1d25bed77cd7d`  
CI run: `#442`  
Repository Alembic head: `0054`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## Verdict

```text
MERGED INTO REPOSITORY
NOT DEPLOYED
NOT A CLINICAL FACT PIPELINE
```

D1 converts authenticated C2 safe-page PNG artifacts into encrypted OCR provenance and reviewable text candidates. It does not create Clinical Context, body measurements, laboratory observations, diagnoses, recommendations or medication data.

## Implemented database boundary

Migration `0054` adds:

- `document_ocr_runs`;
- `document_ocr_artifacts`;
- `document_ocr_candidates`;
- OCR status metadata on `profile_documents`;
- RLS and FORCE RLS on every OCR table;
- owner/edit-only candidate-text visibility;
- renderer-only OCR queueing;
- OCR-worker-only claim, heartbeat, completion and failure functions;
- reconciliation support for encrypted OCR artifacts;
- content-free OCR audit actions.

The dedicated PostgreSQL role is:

```text
health_compass_ocr_worker LOGIN NOBYPASSRLS
```

It has no direct SELECT, INSERT, UPDATE or DELETE grants on document, OCR, profile, audit or clinical tables. It receives schema usage and EXECUTE only on constrained SECURITY DEFINER functions.

## Implemented OCR process boundary

- local Tesseract 5-compatible command boundary;
- fixed absolute executable and tessdata paths;
- fixed `--oem 1`;
- bounded page segmentation mode allowlist;
- initial exact language configuration `rus+eng`;
- traineddata files opened without following symlinks;
- traineddata manifest SHA-256 recorded;
- safe-page source fully GCM-verified before OCR;
- PNG structure validated again before Tesseract;
- sealed read-only memfd input;
- bounded memfd output;
- CPU, address-space, file-size, descriptor, process and timeout limits;
- fixed environment and no shell invocation;
- process stderr converted to safe error codes only.

## Strict TSV contract

The parser accepts only the exact Tesseract TSV columns:

```text
level page_num block_num par_num line_num word_num
left top width height conf text
```

It enforces:

- UTF-8;
- exact header and column count;
- bounded total output and row count;
- valid numeric hierarchy and coordinates;
- bounding boxes within the source page;
- confidence range checks;
- bounded text and word counts;
- rejection of control characters;
- deterministic grouping by page/block/paragraph/line;
- preservation of original OCR text without medical correction, translation or unit normalization.

## Encrypted provenance

Per-page TSV is encrypted before persistent storage under opaque keys:

```text
ocr/{document_uuid}/{ocr_run_uuid}/page-{page_number}.tsv.hcenc
```

The database records:

- source safe-page artifact;
- page number;
- engine and version;
- language specification;
- traineddata manifest;
- plaintext and encrypted sizes;
- SHA-256;
- encryption format and key ID.

Storage keys, hashes and TSV contents are not exposed through ordinary user APIs.

## Candidate contract

Every generated candidate starts as:

```text
needs_review
```

Candidate metadata includes:

- source OCR run and safe page;
- page and deterministic candidate index;
- original OCR text;
- minimum and mean confidence;
- bounding box;
- source word count;
- creation/update timestamps.

Candidate text is visible only to owner/edit. View, analyze and outsider roles receive no candidate rows.

There are no candidate mutation, review-finalization or patient-match endpoints in D1.

## API and UI

Implemented API:

```text
GET /profiles/{profile_id}/documents/{document_id}/ocr/status
GET /profiles/{profile_id}/documents/{document_id}/ocr/candidates
```

The document UI shows safe OCR states such as queued, processing, review required and error. It does not expose raw PDF, safe-page images, encrypted-object keys or TSV provenance.

## Verification

Exact reviewed head:

```text
dc28e9e220dd51264e6dab1244ce8d8696f501b2
```

CI run `#442` passed:

- backend compile;
- Ruff;
- backend unit tests;
- frontend lint;
- TypeScript typecheck;
- frontend tests;
- production frontend build;
- migration `0054` boundary;
- isolated full `head → base → head` migration cycle;
- PostgreSQL OCR worker and RLS integration tests.

PostgreSQL tests prove:

- OCR worker cannot query OCR tables directly;
- queue execution belongs only to the renderer role;
- OCR functions belong only to the OCR worker role;
- stale leases are rejected;
- completion is idempotent for the same output;
- owner/edit can read candidate text;
- view/analyze/outsider cannot read candidate text;
- audit payload is content-free;
- OCR creates zero conditions, allergies, medications, supplements or body measurements.

## Findings resolved before merge

- SQL regular expressions were rewritten to avoid invalid Python escape sequences.
- Migration downgrade removes dependent RLS policies before dropping the review helper function.
- Tesseract output is written to bounded memory files instead of an unbounded pipe.
- OCR output and traineddata provenance are strictly bounded and validated.

## Explicitly not implemented

- accept/edit/reject/defer candidate mutations;
- patient matching;
- review finalization;
- safe-page delivery or preview;
- analyte/value/unit extraction;
- Clinical Context or Labs creation;
- production Tesseract/systemd provisioning;
- production document upload;
- production migration or rollout.

## Next stage

```text
HC-017 D2 — Human Review and Patient Matching
```

D2 must add:

- owner/edit candidate actions: accept, edit, reject and defer;
- optimistic concurrency using `expected_updated_at`;
- explicit match, mismatch or not-present patient decision;
- candidate-manifest review finalization;
- content-free audit;
- accessible review UI;
- no Labs or clinical-fact creation.

## Production boundary

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

No VPS rollout task is authorized by D1 merge.