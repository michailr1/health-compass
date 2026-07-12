# HC-017 Slice C1 — Encrypted Scanner Worker Implementation Evidence

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`  
Date: 2026-07-12  
Source PR: `#51`  
Verified implementation head: `c32e420b59d950aad48366c79010f5ac9fecb43b`  
Merge commit: `a0dd405ca3e789cb70e5c4ad94de9a272dff878f`  
CI run: `#414 — passed`  
Repository Alembic head: `0051`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## Verdict

```text
MERGED INTO REPOSITORY
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

C1 establishes authenticated encrypted quarantine storage and a restricted malware-scanner worker boundary. It does not install or start production services and it does not enable document upload outside development.

## Implemented scope

### Authenticated encrypted objects

- versioned `HCENC1` envelope;
- AES-256-GCM streaming encryption;
- random 96-bit nonce per object;
- associated authenticated data binds:
  - format header;
  - document UUID;
  - artifact role;
  - key ID contained in the authenticated header;
- SHA-256 is calculated over plaintext during encryption;
- ciphertext authentication is verified before a scan can finish successfully;
- plaintext source is not written by the application to persistent document storage;
- ciphertext corruption, wrong document UUID or wrong artifact role fails authentication.

### Encryption-key boundary

Keys are loaded only from a configured credential directory.

Controls:

- key IDs use a strict allowlist;
- key file is opened with `O_NOFOLLOW`;
- key must be a regular file;
- key must have exactly one hard link;
- group/world-writable key files are rejected;
- key material must contain exactly 32 bytes;
- symlink aliases, including aliases inside the credential directory, are rejected;
- keys are not stored in Git, environment values, database rows or object paths.

Production credential provisioning through systemd remains a later rollout task.

### Encrypted filesystem boundary

Quarantine key:

```text
quarantine/{document_uuid}/original.hcenc
```

Controls:

- user filename never becomes a storage path;
- intermediate path traversal is rejected;
- final path component remains unresolved so `O_NOFOLLOW` stays effective;
- encrypted object is written through an exclusive temporary ciphertext file;
- file data is flushed before publication;
- publication is exclusive and cannot overwrite an occupied object key;
- an existing object is never deleted during a failed collision attempt;
- encrypted readers reject symlinks, non-regular files and multiple hard links;
- directories and files use restrictive development/test permissions;
- reserved free-space floor is checked during encrypted writes.

### Document metadata

Migration `0051` adds:

- encrypted byte size;
- encryption format;
- encryption key ID;
- scanner status;
- scanner engine/version metadata;
- signature version and timestamp;
- scanner completion timestamp;
- next retry time for processing jobs.

New documents use:

```text
storage_backend = local_encrypted
encryption_format = hcenc1
scanner_status = not_scanned
job_type = scan
```

Internal key IDs, hashes and object keys remain absent from user API responses.

## Restricted scanner worker

### PostgreSQL identity

Migration `0051` requires the role to exist before upgrade:

```text
health_compass_worker
LOGIN
NOBYPASSRLS
NOSUPERUSER
NOCREATEDB
NOCREATEROLE
NOREPLICATION
```

The worker receives:

- database connection;
- schema usage;
- execute permission on four restricted functions.

The worker receives no direct table `SELECT`, `INSERT`, `UPDATE` or `DELETE` grants.

### Restricted functions

```text
app_claim_document_job(...)
app_heartbeat_document_job(...)
app_complete_document_scan(...)
app_fail_document_job(...)
```

Properties:

- owner `health_compass_rls_definer`;
- `SECURITY DEFINER`;
- fixed empty `search_path`;
- `row_security=off` where needed;
- PUBLIC execute revoked;
- application-role execute revoked;
- worker-only execute;
- caller verified with `SESSION_USER`;
- bounded worker ID, lease, attempt and retry values;
- `FOR UPDATE SKIP LOCKED` claim;
- stale lease cannot mutate a job;
- expired leases may be reclaimed;
- exhausted attempts become terminal failures;
- identical completion retries are idempotent.

### Scan transitions

Clean:

```text
scan job → succeeded
scanner_status → clean
render job → queued
content-free audit → document.scan_clean
```

Infected:

```text
scan job → succeeded
document → rejected
scanner_status → infected
failure_code → malware_detected
deletion_requested_at → set
no render job
content-free audit → document.scan_rejected
```

Retryable scanner failure:

```text
job → queued
next_attempt_at → set
document remains quarantined
```

Non-retryable invalid encrypted object or unsupported storage format enters a terminal failure/deletion lifecycle.

## ClamAV client

C1 implements a strict local `clamd` Unix-socket client.

Controls:

- no public scanner network endpoint;
- `VERSION` response parsed by a strict contract;
- signature timestamp age checked before streaming the document;
- stale signatures fail closed;
- `INSTREAM` uses bounded chunks and a maximum byte count;
- unexpected response, socket error, timeout or protocol error fails closed;
- malware signature names are not exposed through application objects or UI;
- the terminating zero-length INSTREAM frame is sent only after GCM authentication completes;
- a corrupted encrypted object therefore cannot receive a clean result.

ClamAV and FreshClam are not installed or configured by this implementation PR.

## API and UI

Document responses gain a safe scanner status:

```text
not_scanned
scanning
clean
infected
error
stale
```

The UI displays Russian user-facing states such as:

- «Ожидает проверки»;
- «Проверяется»;
- «Проверка пройдена»;
- «Отклонён как небезопасный»;
- «Проверка временно не завершена».

The UI does not expose:

- ClamAV response text;
- malware signature name;
- scanner socket path;
- object key/path;
- encryption key ID;
- file hash;
- source document contents.

No preview, download, safe rendering, OCR or Labs route is added in C1.

## Verification evidence

Exact reviewed head:

```text
c32e420b59d950aad48366c79010f5ac9fecb43b
```

CI:

```text
#414 — success
```

Passed:

- Python compile;
- Ruff;
- backend unit tests;
- frontend full lint;
- TypeScript typecheck;
- frontend tests;
- production frontend build;
- migration boundary tests;
- isolated full migration cycle `head → base → head`;
- PostgreSQL RLS and worker privilege integration tests.

Coverage includes:

- encrypted round-trip;
- unique ciphertext/nonces for repeated plaintext;
- ciphertext/AAD tamper rejection;
- key symlink, hard-link and unsafe-mode rejection;
- occupied destination preservation;
- encrypted-object symlink rejection;
- strict ClamAV clean/infected/stale/tampered flows;
- worker no-direct-table-access checks;
- stale lease conflict;
- clean/infected/retry state transitions;
- idempotent scan completion;
- content-free audits;
- migration downgrade/upgrade cycle.

## Production boundary

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

No VPS rollout task has been issued for C1.

The following are still absent from production and from this slice:

- encryption-key provisioning;
- production document directories;
- worker OS account/service;
- ClamAV/FreshClam installation;
- scanner Unix-socket permissions;
- reverse-proxy upload limit;
- isolated multipart temporary spool;
- per-profile/global quotas;
- orphan reconciliation;
- safe parser/rasterizer;
- encrypted page derivatives;
- OCR and human review;
- confirmed Labs observations.

## Next stage

```text
HC-017 Slice C2 — Quotas, Orphan Reconciliation and Safe Rendering
```

C2 must preserve separation between scan and render job permissions. Before implementation it must decide whether renderer operations use separate functions or a separate worker identity rather than broadening C1 scanner functions.

Required C2 controls:

- per-profile/global quotas and reserved free-space accounting;
- orphan and missing-object reconciliation;
- full GCM verification before parser access;
- bounded parser/rasterizer subprocesses;
- page, pixel, CPU, memory, file-size and timeout limits;
- encrypted safe page derivatives;
- atomic and idempotent accepted promotion;
- no raw PDF delivery;
- no OCR yet;
- full independent security review before any rollout decision.

## Final status

```text
HC017_C1_MERGED
HC017_C1_CI_VERIFIED
HC017_C1_NOT_DEPLOYED
PRODUCTION_DOCUMENT_UPLOAD_DISABLED
NEXT: HC017_C2
```
