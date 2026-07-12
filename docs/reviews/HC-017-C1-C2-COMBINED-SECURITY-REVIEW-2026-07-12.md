# HC-017 C1+C2 — Combined Security Review

Date: 2026-07-12  
C1 merge: `a0dd405ca3e789cb70e5c4ad94de9a272dff878f`  
C2 merge: `06e4f0a228b4867d9bf7983284bc04f3cb53cd05`  
Repository baseline: `ac9e21f3315c4624a845e633c2a90881d348ca30`  
Repository Alembic head: `0053`  
Production: `b8e868825f378195975e2729f3f36c21a1afa2d0 / 0049`

## Verdict

```text
ACCEPT FOR REPOSITORY FOUNDATION
NO UNRESOLVED CRITICAL OR HIGH FINDING
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

C1 and C2 establish a defensible repository boundary for encrypted intake, malware scanning, quota accounting, safe rendering and storage reconciliation. They do not establish a production-ready document service.

## Reviewed scope

- `HCENC1` authenticated encryption;
- credential-file and object-path handling;
- encrypted quarantine upload;
- ClamAV Unix-socket protocol;
- scanner role and functions;
- quota reservation;
- canonical source references;
- safe-page artifacts;
- renderer role and functions;
- full GCM authentication before parser access;
- sealed memfd source/output;
- subprocess resource limits;
- PNG structural validation;
- reconciler role and inventory;
- orphan/missing-object lifecycle;
- API/UI status exposure;
- migration and RLS tests.

## Confirmed security properties

### Encryption and storage

- plaintext is not persisted by the application document adapters;
- AES-256-GCM uses random nonces and authenticated metadata;
- document UUID and artifact role are included in AAD;
- key material is read from protected files, not Git/database/application environment values;
- key files and encrypted objects reject symlinks and unsafe link modes;
- object publication is exclusive and does not overwrite an occupied key;
- API responses do not expose storage keys, hashes or key IDs.

### Scanner

- ClamAV is local and accessed through a Unix socket;
- scanner output is parsed from a strict allowlist;
- stale signatures, unavailable socket, timeout and malformed response fail closed;
- encrypted-object authentication finishes before a clean result can be accepted;
- infected documents do not reach rendering and enter deletion lifecycle;
- scanner worker has no direct document-table privileges.

### Quota and concurrency

- upload reservation is serialized with transaction advisory locks;
- profile/global byte limits and document/job-count limits are checked in PostgreSQL;
- a request keeps quota locks through object write and metadata insertion;
- reserved free-space checking remains an independent filesystem gate.

### Renderer

- renderer has a separate NOBYPASSRLS identity;
- renderer has no direct table privileges;
- source plaintext is available only after full GCM verification;
- parser source is a sealed read-only memfd;
- renderer subprocess commands are fixed and do not use a shell;
- CPU, memory, output, page, pixel, file-descriptor and timeout limits are applied;
- safe-page PNG output is checked for signature, chunk types/order, CRC, dimensions and final IEND;
- accepted source and safe pages are encrypted before persistent storage;
- accepted promotion is guarded by lease, source hash and document state;
- repeated identical completion is idempotent;
- raw PDF is not exposed through a browser route.

### Reconciliation

- reconciler has a separate NOBYPASSRLS identity;
- reconciler has no direct table privileges;
- inventory exposes opaque references only;
- unknown objects move to orphan handling after a grace period;
- missing referenced objects move documents to a safe failed state;
- repeated missing-object detection is idempotent and does not create duplicate audits.

## Findings closed during C1/C2 review

| Finding | Initial severity | Resolution |
|---|---:|---|
| scanner helper/role compilation and ownership ordering | High | hardened definer ownership and migration-cycle checks |
| scanner worker direct table exposure | High | no direct grants; restricted functions only |
| external-object orphan after database failure | High | transaction rollback cleanup and later reconciliation |
| upload body exhaustion before multipart parsing | High | pre-parser ASGI body limit |
| encrypted object path/symlink races | High | O_NOFOLLOW, regular-file and link-count checks |
| occupied object key overwrite/delete risk | High | exclusive publication and collision failure |
| parser access before GCM authentication | High | full verification into sealed memfd before subprocess start |
| renderer/reconciler privilege overlap | High | separate roles and execute matrices |
| renderer output memfd could not be sealed | High | MFD_ALLOW_SEALING and regression test |
| incomplete parser metadata read | Medium | bounded complete-read loop |
| C2 roles absent in CI provisioning | Medium | explicit role creation and DSNs |
| new table/functions absent from migration-cycle assertions | Medium | FORCE RLS, owner, PUBLIC and role matrix assertions |
| missing functional renderer/reconciler flow | Medium | PostgreSQL end-to-end integration tests |
| repeated missing-object audit spam | Medium | migration 0053 and idempotency regression |

## Accepted repository limitations

### Host compromise boundary

Application-level encryption protects copied object files, offline snapshots and backups when key material is separate. It does not protect against a live host compromise that can read service credentials and process memory.

### Temporary multipart spool

Starlette may spool multipart input before the application encrypts it. Production rollout therefore requires a private, bounded and lifecycle-controlled temporary directory for the web process.

### Renderer package trust

The repository defines fixed paths and limits, but production versions of Poppler and ImageMagick have not been installed, pinned or independently probed on the VPS.

### Crash and retry windows

A host crash may leave unreferenced encrypted objects. Reconciliation handles them after a grace period. Deterministic accepted-source keys may delay retry until the stale object is isolated; this is acceptable for the current foundation but must be measured operationally.

### No source/preview delivery

C2 intentionally provides no user download or preview endpoint. A later review UI may expose only safe-page derivatives through a separately authorized, short-lived delivery boundary.

## Production blockers

Before any production upload enablement:

- provision production encryption credentials and recovery/rotation process;
- create private storage and temporary-spool directories;
- create scanner/renderer/reconciler OS accounts;
- install hardened systemd units;
- install and verify Poppler/ImageMagick versions;
- install ClamAV/FreshClam and verify signature freshness;
- configure reverse-proxy body limits;
- choose measured profile/global quotas and disk reserve;
- run clean, EICAR, malformed, password-protected, timeout and resource probes;
- verify backup inclusion/exclusion and restore behavior;
- verify no filenames, paths, OCR text or medical values in logs;
- complete controlled exact-SHA rollout review.

## Slice D prerequisites

Slice D may begin in the repository only when it preserves all C1+C2 boundaries:

1. OCR consumes only `safe_page` artifacts whose encryption/authentication succeeds.
2. A separate OCR worker role is used.
3. OCR worker receives no direct profile/document/candidate table grants.
4. OCR subprocess has fixed commands and CPU/memory/output/time limits.
5. OCR output is encrypted before persistent storage.
6. Candidate text is owner/edit-only and excluded from analyze/view.
7. Candidate text begins as `needs_review`.
8. Page number, bounding box, engine/model and confidence provenance are retained.
9. Patient matching is a separate explicit decision.
10. No OCR candidate automatically becomes Clinical Context, measurement or Labs data.

## Final status

```text
C1_C2_COMBINED_REVIEW_COMPLETE
SLICE_D_REPOSITORY_WORK_ALLOWED
PRODUCTION_ROLLOUT_NOT_APPROVED
```