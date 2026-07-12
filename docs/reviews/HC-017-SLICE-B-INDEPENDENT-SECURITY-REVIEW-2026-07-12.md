# HC-017 Slice B — Independent Security Review

Date: 2026-07-12  
Reviewed merge: `ccabab77cf929456a74b69c3478c71f92f167f78`  
Verified implementation head: `46c5ea89d35cc85be0af3b80a9c56f40d5705ac5`  
Source PR: `#48`  
CI: `#402 — passed`

## Verdict

```text
ACCEPT FOR REPOSITORY FOUNDATION
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

No unresolved Critical or High finding was identified in the merged Slice B scope.

The slice correctly remains disabled outside development and does not provide a production storage, scanner, worker, preview, download, OCR or Labs path.

## Reviewed scope

- migration `0050`;
- document and processing-job tables;
- RLS and grants;
- document visibility helper;
- duplicate-account activity wrapper;
- local quarantine adapter;
- request-size middleware;
- transaction rollback cleanup;
- upload/list/detail API;
- profile-aware capabilities;
- Documents UI;
- backend/frontend/PostgreSQL tests;
- CI failure diagnostics.

## Confirmed strengths

### Tenant and privilege boundary

- Both new tables use RLS and FORCE RLS.
- Runtime role has no direct UPDATE or DELETE.
- Owner/edit may insert.
- Owner/edit/view may read document metadata.
- Analyze and outsider cannot read document metadata.
- No-user-context queries return no rows.
- `app_can_view_document(uuid)` has dedicated definer ownership, fixed configuration and revoked PUBLIC EXECUTE.

### Cross-table integrity

- Processing jobs use a composite foreign key to the same `(document_id, profile_id)`.
- Parent document is flushed before the dependent job inside the same request transaction.
- Document rows participate in duplicate-account meaningful-activity assessment.

### Upload boundary

- Format allowlist is limited to PDF, JPEG and PNG.
- Extension, declared MIME and magic bytes must agree.
- File and image-dimension limits are enforced by backend code.
- Complete request bodies are bounded before multipart parsing.
- Chunked requests are counted.
- Storage keys use server-generated UUIDs and not filenames.
- API responses omit hashes and storage keys.

### Artifact consistency

- Quarantine objects use restrictive local permissions in development/test.
- Route, commit and cancellation failures run rollback cleanup.
- Cleanup errors do not reveal paths or filenames.
- PDF remains unparsed and inaccessible in Slice B.

### Product honesty

- No preview or download route exists.
- No OCR functionality is implied by the API.
- UI explicitly states that only quarantine metadata/status is available.
- Production startup rejects upload enablement.

## Findings resolved during implementation review

| Finding | Severity before fix | Resolution |
|---|---:|---|
| Definer helper body validated before ownership transfer under FORCE RLS | High | helper changed to deferred PL/pgSQL compilation and hardened ownership flow |
| Job could lack same-profile proof | High | composite document/profile FK added |
| ORM could emit job before parent document | Medium | explicit parent flush inside same transaction |
| Analyze inherited broad profile-view access | High | document-specific DB helper excludes analyze |
| UI capability depended only on global flag | Medium | profile-aware backend capability endpoint |
| File could survive route/final-commit failure | High | transaction-bound rollback cleanup |
| Request could consume temporary disk before route limit | High | ASGI pre-parser body limiter for normal and chunked requests |
| Ruff failure output was not retained | Low | short-lived non-sensitive diagnostics artifact |

## Remaining findings and required follow-ups

### SR-01 — Process-crash orphan window

Severity: `MEDIUM / SLICE C BLOCKER`

A hard process or host crash can occur after an encrypted/plain development object is atomically renamed but before its database row commits or rollback cleanup executes.

Required Slice C control:

- periodic reconciliation between storage inventory and database rows;
- objects without a committed row move to a restricted orphan area;
- deletion only after a grace period;
- reconciliation logs only internal object IDs and safe result codes;
- reconciliation is idempotent and tenant-neutral.

### SR-02 — Local Slice B objects are not application-encrypted

Severity: `MEDIUM / ACCEPTED FOR DEVELOPMENT ONLY`

The local adapter relies on host filesystem permissions and is explicitly forbidden for production enablement.

Required Slice C control:

- authenticated encryption at rest;
- unique per-object nonce;
- key identifier and rotation strategy;
- key supplied through protected service credentials;
- no plaintext temporary file during scan/render.

### SR-03 — Reverse-proxy body limit must match backend policy

Severity: `MEDIUM / ROLLOUT BLOCKER`

The ASGI limit protects the application process, but Apache or another reverse proxy must also reject excessive request bodies before forwarding.

Required rollout control:

- exact upload-location body limit;
- no broad global increase;
- 413 behavior tested through public HTTPS;
- access logs remain query-safe and content-free.

### SR-04 — Original filename is sensitive metadata

Severity: `LOW / ACCEPTED WITH CONTROLS`

A filename may contain a patient name, test name or date.

Current controls:

- display-only storage;
- no use in object keys;
- no ordinary logging;
- no audit duplication;
- only owner/edit/view metadata access.

Required follow-up:

- include filenames in export/deletion scope;
- avoid filename-based metrics and alerts;
- consider optional user rename after accepted import.

### SR-05 — No storage quota yet

Severity: `MEDIUM / SLICE C BLOCKER`

Per-request limits do not prevent repeated uploads from filling disk.

Required Slice C control:

- per-profile and global quota;
- reserved free-space threshold;
- fail closed before write when threshold is crossed;
- bounded queued-job count;
- quota checks repeated during stream, not only before upload.

### SR-06 — Scanner, parser and renderer are absent

Severity: `EXPECTED / PRODUCTION BLOCKER`

Quarantined files are intentionally unusable. Production enablement remains forbidden until Slice C provides a scanner and sandboxed safe-rendering pipeline.

### SR-07 — Worker role is not provisioned

Severity: `EXPECTED / PRODUCTION BLOCKER`

The application currently creates queued metadata only. No process may claim or mutate jobs until a dedicated worker role and constrained database functions are implemented.

## Production decision

Slice B must not be deployed alone.

The following remain prohibited:

- applying migration `0050` as a production feature rollout;
- setting `DOCUMENT_UPLOAD_ENABLED=true` outside development;
- storing real medical documents through the local development adapter;
- parsing or rendering quarantined files in the web process;
- adding a direct file download endpoint.

## Acceptance criteria for Slice C review

Slice C review must prove:

- encrypted private production storage;
- scanner fail closed;
- current signature database health;
- isolated worker credentials;
- no direct worker table mutation beyond constrained functions;
- resource-bounded PDF/image inspection;
- safe rasterized derivatives only;
- per-profile/global quotas;
- orphan reconciliation;
- atomic promotion and idempotent retries;
- no filenames, storage keys, signed URLs or medical contents in ordinary logs;
- full migration cycle and tenant/worker negative tests.
