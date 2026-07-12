# HC-017 Slice C2 — Quotas, Reconciliation and Safe Rendering Evidence

Status: `MERGED / CI VERIFIED / NOT DEPLOYED`  
Date: 2026-07-12  
Source PR: `#53`  
Verified head: `568eca1ec1c91005b907cc79349036a71d7f6f83`  
Merge commit: `06e4f0a228b4867d9bf7983284bc04f3cb53cd05`  
CI: `#433 — passed`  
Repository Alembic head: `0053`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## Verdict

```text
MERGED INTO REPOSITORY
CI VERIFIED
NOT DEPLOYED
NOT PRODUCTION READY
```

Slice C2 extends the C1 encrypted scanner foundation with quota controls, encrypted-object reconciliation and bounded safe rendering. It does not enable production document upload and does not implement OCR, extraction candidates or Labs observations.

## Database boundary

Migrations:

```text
0052 — quota, reconciliation and safe-rendering foundation
0053 — idempotent missing-object reconciliation
```

Implemented:

- canonical `current_storage_key` on source documents;
- encrypted `document_artifacts` with `FORCE ROW LEVEL SECURITY`;
- profile/global byte quotas;
- document-count and queued-job limits;
- transaction-scoped advisory locks for race-safe upload reservation;
- separate renderer and reconciler PostgreSQL roles;
- no direct renderer/reconciler table grants;
- restricted claim, heartbeat, completion, failure and reconciliation functions;
- exact role-to-function execute matrix;
- idempotent repeated missing-object handling;
- content-free audit events.

Required roles:

```text
health_compass_renderer LOGIN NOBYPASSRLS
health_compass_reconciler LOGIN NOBYPASSRLS
```

## Safe rendering boundary

The renderer receives a source only after complete GCM authentication.

Implemented controls:

- verified plaintext is exposed through a sealed read-only Linux `memfd`;
- no persistent plaintext source file is created;
- subprocesses use fixed executable paths and argument templates;
- shell execution is not used;
- CPU, address-space, output-size, file-descriptor, page, pixel and timeout limits;
- PDF metadata inspection is bounded;
- password-protected and over-limit PDF documents are rejected;
- image/PDF output must be PNG;
- PNG signature, chunk ordering, allowlist, CRC, dimensions and final `IEND` are verified;
- output memfd uses `MFD_ALLOW_SEALING` and becomes read-only;
- accepted source and safe-page derivatives are encrypted before persistent storage;
- renderer heartbeats protect long multi-page work;
- accepted promotion is transactionally guarded and idempotent;
- raw PDF is never exposed through a browser route.

## Storage reconciliation

Implemented namespaces and references:

- authoritative source object through `current_storage_key`;
- safe-page objects through `document_artifacts`;
- opaque orphan isolation and deletion flow;
- missing referenced object detection;
- repeated detection of the same missing object creates only one audit event;
- reconciliation functions reveal opaque object references only to the dedicated reconciler role.

## API and UI boundary

The API/UI may expose safe processing states only:

```text
not_started
queued
rendering
ready
error
```

No source or derivative download route is introduced. Internal paths, object keys, hashes, encryption key IDs, parser stderr and medical content remain hidden.

## Verification

Exact head `568eca1e...` passed CI `#433`:

- Python compile;
- Ruff;
- backend unit tests;
- frontend lint;
- TypeScript typecheck;
- frontend tests;
- production frontend build;
- migration boundary tests;
- isolated full migration cycle `head → base → head`;
- scanner-worker negative privilege tests;
- renderer claim, stale lease, completion and idempotency tests;
- reconciler reference and direct-access tests;
- owner/view/analyze artifact RLS tests;
- sealed-memory and PNG validation tests;
- missing-object idempotency tests.

## Security review findings closed before merge

- CI did not initially provision renderer/reconciler roles;
- renderer output memfd lacked `MFD_ALLOW_SEALING`;
- bounded parser output reads did not prove complete reads;
- old fixtures omitted mandatory `current_storage_key`;
- migration-cycle checks did not initially cover C2 roles/functions/table;
- functional renderer/reconciler integration coverage was absent;
- repeated missing-object passes emitted duplicate audit events.

All were fixed before the exact-head successful run.

## Production boundary

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

No VPS rollout task has been issued for C1 or C2.

Still required before production:

- verified production versions of Poppler and ImageMagick;
- production encryption credentials and recovery process;
- private document directories;
- dedicated OS accounts;
- hardened systemd scanner/renderer/reconciler units;
- ClamAV/FreshClam health and signature checks;
- isolated bounded multipart spool;
- reverse-proxy upload limit;
- measured production quota values and disk reserve;
- EICAR, clean, malformed, timeout and resource-limit probes;
- no-sensitive-log verification;
- independent combined C1+C2 review;
- explicit controlled rollout approval.

## Next stage

```text
HC-017 Slice D — OCR Candidates and Human Review
```

Slice D must consume encrypted safe-page artifacts only. OCR text remains an untrusted draft and cannot create a clinical or laboratory fact without explicit human review and later confirmation.
