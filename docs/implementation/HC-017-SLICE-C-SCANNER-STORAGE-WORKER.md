# HC-017 Slice C — Encrypted Storage, Malware Scanner and Safe Rendering

Status: `ARCHITECTURE DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`  
Created: 2026-07-12  
Base main: `3b29d4e9e389080c0c40c2508bbd7bc1d2eea910`  
Repository Alembic head: `0050`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## 1. Goal

Promote a Slice B document from inaccessible quarantine to a scanner-approved, safely rendered source without introducing OCR or confirmed clinical facts.

```text
quarantined encrypted object
→ restricted job claim
→ decrypt as stream
→ local malware scan
→ bounded structural inspection
→ safe rasterized derivatives
→ encrypted accepted/derived objects
→ atomic accepted promotion
```

## 2. Architecture decision

For MVP, use a local private encrypted object store on the existing production VPS instead of sending medical documents to an external storage or scanning provider.

Selected components:

- filesystem-backed encrypted object adapter;
- storage root outside releases and public web paths;
- per-object authenticated encryption;
- key material loaded through systemd credentials;
- local ClamAV `clamd` over a Unix socket;
- `freshclam` for signature database updates;
- separate `health_compass_worker` operating-system user;
- separate `health_compass_worker` PostgreSQL login role with `NOBYPASSRLS`;
- constrained `SECURITY DEFINER` job-claim and completion functions;
- sandboxed PDF/image inspection and rasterization subprocesses;
- encrypted safe page derivatives;
- no external OCR/LLM in Slice C.

Rationale:

- no new third-party processor receives medical files;
- simpler data-residency and deletion boundary for MVP;
- encrypted backups can include opaque objects;
- local Unix-socket scanning avoids public scanner endpoints;
- the existing storage adapter interface remains reusable for a later S3-compatible backend.

Trade-off:

- application-level encryption does not protect against a full live-host compromise that also exposes service credentials;
- it does protect offline disk snapshots, copied object files and encrypted backups when key material is stored separately;
- host hardening, key isolation and least privilege remain mandatory.

## 3. Production storage layout

Target root:

```text
/var/lib/health-compass/documents
```

Namespaces:

```text
quarantine/{document_uuid}/original.hcenc
accepted/{document_uuid}/original.hcenc
derived/{document_uuid}/{run_uuid}/page-{page_number}.png.hcenc
orphan/{object_uuid}.hcenc
trash/{object_uuid}.hcenc
```

Rules:

- root is outside `/opt/health-compass/releases` and Apache document roots;
- keys contain only opaque IDs;
- filename, email, profile name and medical values never appear in paths;
- same-filesystem atomic rename is required for state transitions;
- directory permissions default to `0700` or group-restricted equivalent;
- files default to `0600`;
- no direct Apache/Nginx alias or static-file mapping;
- no user-generated symbolic links are followed;
- object writes use `O_NOFOLLOW`, exclusive temporary names, `fsync`, then atomic rename;
- accepted and derived objects are never created from an unscanned source.

## 4. Encryption format

Use versioned authenticated encryption for every source and derived object.

Algorithm target:

```text
AES-256-GCM
```

Requirements:

- random 256-bit key from protected service credentials;
- unique random 96-bit nonce for every encrypted object;
- nonce must never be reused with the same key;
- associated authenticated data includes format version, document UUID, artifact role and key ID;
- streaming encryption/decryption uses the low-level GCM cipher API;
- authentication tag is verified before plaintext is accepted as valid;
- no plaintext temporary file is written during normal scanning/rendering;
- output is never exposed before successful finalization and tag verification.

Proposed envelope:

```text
magic: HCENC1
version: 1
key_id length + key_id
nonce length + nonce
artifact role
ciphertext stream
tag
```

The exact binary format must have parser fuzz tests and strict length bounds.

### Key provisioning

- key is not stored in Git, `.env`, database or object header;
- key is delivered with systemd `LoadCredential=` or encrypted credentials;
- backend and worker receive only the credential required for their role;
- credential file is visible only inside the service credential namespace;
- database stores only non-secret `encryption_key_id`;
- active and previous key IDs may coexist for rotation;
- unknown key IDs fail closed.

### Rotation

Initial rotation model:

1. install a new active key credential;
2. new objects use the new key ID;
3. old keys remain decrypt-only;
4. background re-encryption creates a new object atomically;
5. database reference changes only after verification;
6. old object is deleted after a grace period;
7. old key is retired only after inventory proves zero references.

## 5. Malware scanning

Selected engine:

```text
ClamAV clamd
```

Connection:

```text
local Unix socket
INSTREAM protocol
```

The worker decrypts the object and streams plaintext to `clamd`. ClamAV does not need read access to the document storage tree.

Required configuration:

- Unix socket only; no public TCP listener;
- socket ownership/group permits only the worker;
- `StreamMaxLength` exceeds the maximum accepted plaintext object plus protocol overhead;
- command and scan timeouts are finite;
- scanner response is parsed from a strict allowlist;
- unexpected response, timeout, socket failure or protocol error = fail closed;
- official signature database is maintained by `freshclam`;
- scanner engine version and signature timestamp are recorded as non-sensitive metadata;
- stale signature database blocks promotion;
- EICAR acceptance test is run in isolated test/deployment verification without storing the test payload in Git.

Result mapping:

| Scanner result | Document transition |
|---|---|
| clean | continue to structural inspection |
| infected | `rejected`, inaccessible, deletion scheduled |
| scanner unavailable | remain quarantined, retry later |
| signature database stale | remain quarantined, block promotion |
| malformed/unexpected response | fail closed, safe error code |

Policy threshold:

- production readiness requires an explicit signature-freshness limit;
- initial target: block promotion when database age exceeds 48 hours;
- the threshold is configuration with safe upper validation, not a UI option.

ClamAV is a malware-risk reduction layer, not proof that a file is harmless. Parser sandboxing and human confirmation remain necessary.

## 6. Worker identity and database boundary

### Operating-system identity

Target static service account:

```text
health-compass-worker
```

It is not the backend service account, `root`, `clamav`, or the deployment user.

### PostgreSQL role

```text
health_compass_worker LOGIN NOBYPASSRLS
```

The worker role receives:

- CONNECT to the application database;
- USAGE on the application schema only as required;
- EXECUTE on narrow job claim/heartbeat/complete/fail functions;
- no direct SELECT/INSERT/UPDATE/DELETE on profile, document, clinical or identity tables;
- no membership in migrator or RLS-definer roles;
- no CREATEDB, CREATEROLE, REPLICATION or BYPASSRLS.

### Required database functions

Candidate functions:

```text
app_claim_document_job(worker_id, lease_seconds)
app_heartbeat_document_job(job_id, worker_id, expected_lease)
app_complete_document_inspection(job_id, worker_id, result_payload)
app_fail_document_job(job_id, worker_id, safe_error_code, retryable)
app_reconcile_document_objects(...)
```

Function invariants:

- owner `health_compass_rls_definer`;
- fixed empty `search_path`;
- explicit `row_security=off` only when required;
- PUBLIC EXECUTE revoked;
- execution granted only to the worker role;
- static SQL and strict enum/allowlist validation;
- no arbitrary table or storage key input;
- claim uses `FOR UPDATE SKIP LOCKED`;
- lease expiry and worker ownership checked on every mutation;
- result payload contains metadata only, never OCR/document body;
- duplicate completion is idempotent;
- stale lease cannot overwrite a newer attempt.

## 7. Job model and state transitions

Slice B already has durable jobs. Slice C adds constrained mutations and attempts.

Suggested lifecycle:

```text
queued
→ leased
→ succeeded
```

Retry path:

```text
leased
→ failed retryable
→ queued with incremented attempt
```

Terminal path:

```text
leased
→ failed non-retryable
```

Controls:

- one active inspection attempt per document/input hash/engine version;
- lease target: 5 minutes;
- heartbeat interval shorter than one-third of lease;
- bounded maximum attempts;
- exponential retry delay with maximum cap;
- scanner-unavailable retries do not promote state;
- cancellation checked between stages;
- accepted promotion requires the current input SHA-256 and current attempt;
- replaced or voided source invalidates old jobs.

## 8. Systemd sandbox

Worker service target hardening:

```text
User=health-compass-worker
Group=health-compass-worker
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
MemoryDenyWriteExecute=true
CapabilityBoundingSet=
AmbientCapabilities=
ReadOnlyPaths=/var/lib/health-compass/documents/quarantine
ReadWritePaths=/var/lib/health-compass/documents/accepted
ReadWritePaths=/var/lib/health-compass/documents/derived
ReadWritePaths=/var/lib/health-compass/documents/orphan
ReadWritePaths=/var/lib/health-compass/documents/trash
LoadCredential=documents-key:/etc/health-compass/credentials/documents-key
```

Additional limits:

- `MemoryMax=`;
- `CPUQuota=`;
- `TasksMax=`;
- finite service/job timeouts;
- restricted address families;
- network access limited to localhost database and Unix scanner socket;
- no outbound internet access for the worker;
- FreshClam updates run under the scanner/update service, not the document worker.

Exact unit directives must be tested on the production systemd version with `systemd-analyze security` and functional smoke tests.

## 9. Scanner service boundary

`clamd` runs as its own unprivileged scanner user.

Rules:

- no direct access to encrypted object storage is necessary;
- only local Unix socket is enabled;
- socket directory is not writable by the worker;
- worker may connect but cannot replace the socket;
- signature database directory is writable only by the update service/ClamAV owner;
- scanner logs contain engine health and signature metadata, not filenames or medical content;
- scanner service restart/reload must not silently mark documents clean;
- scanner outage leaves jobs retryable and documents quarantined.

## 10. Structural inspection and safe rendering

Malware-clean does not equal parser-safe.

### PDF

The worker processes decrypted plaintext through a sandboxed subprocess pipeline.

Target stages:

1. validate PDF header and encrypted/password-protected state;
2. obtain page count under timeout and memory limits;
3. reject more than 50 pages;
4. reject malformed or password-protected documents;
5. render pages one at a time to a safe raster format;
6. enforce per-page pixel limit;
7. strip metadata from derivatives;
8. encrypt each derivative before persistent storage;
9. delete all plaintext pipes/temp artifacts;
10. accept only after every required page succeeds.

The raw PDF is never embedded in the browser.

### JPEG and PNG

- decode only inside the sandboxed worker;
- enforce dimensions before full decode and again after decode;
- reject decompression bombs and malformed structures;
- apply EXIF orientation deliberately;
- strip EXIF, comments, ICC metadata unless separately required;
- re-encode to safe PNG derivative;
- encrypt derivative before storage.

### Subprocess controls

- no shell invocation;
- fixed executable paths;
- fixed argument templates;
- no user filename in arguments;
- stdin/stdout pipes or worker-private temporary directory;
- timeout per document and per page;
- process-group kill on timeout;
- inherited environment minimized;
- resource limits and worker cgroup enforced;
- stderr is converted to safe error codes, not copied to user or ordinary logs.

Tool selection and exact package versions must be verified on the target Ubuntu release before implementation merge.

## 11. Promotion transaction

Promotion to `accepted` is allowed only after:

- encrypted object decrypts and authenticates;
- scanner returns clean;
- signature freshness passes;
- structural inspection succeeds;
- page and resource limits pass;
- all required derivatives are encrypted and stored;
- current document SHA-256 and job lease still match;
- document remains in a promotable state.

Atomic sequence:

1. write and verify encrypted accepted/derived objects;
2. call restricted completion function;
3. database records accepted keys, scanner metadata and page count;
4. database changes document status to `accepted`;
5. after commit, quarantine object moves to deletion/trash workflow;
6. repeated completion returns the existing accepted result.

If the database transaction fails, newly created accepted/derived objects are removed or later reconciled as orphans.

## 12. Storage quotas and free-space gate

Required before production:

- maximum active bytes per profile;
- maximum quarantined bytes per profile;
- maximum active documents per profile;
- maximum queued jobs per profile;
- global storage quota;
- reserved free-space threshold;
- upload denied before and during stream when quota is exceeded;
- worker checks available space before rendering derivatives;
- safe 507-style error contract without disk paths;
- quotas count quarantine, accepted, derived, orphan and trash states appropriately.

Initial values are configuration and must be chosen from measured production disk capacity, not guessed in code.

## 13. Orphan reconciliation

Required because a process/host crash can interrupt the database/object two-phase boundary.

Reconciler behavior:

- enumerate opaque storage objects without exposing filenames;
- compare object references against committed database rows;
- move unknown objects to `orphan` namespace;
- retain a grace period to avoid racing active transactions;
- delete expired orphans idempotently;
- detect database references whose object is missing;
- mark affected document/job with a safe failure code;
- never cross-link identical hashes across profiles;
- log only internal IDs, counts and safe result codes.

Reconciliation uses a separate constrained worker function and cannot mutate identity or clinical tables.

## 14. API and UI impact

Slice C may add:

```text
POST /profiles/{profile_id}/documents/{document_id}/retry
```

Existing metadata response may gain:

- scanner status;
- safe failure code;
- page count;
- processing timestamps;
- retry availability.

Slice C does not add raw download or OCR confirmation.

UI states:

- In quarantine;
- Waiting for scanner;
- Checking file;
- Preparing safe preview;
- Ready for later recognition;
- Rejected as unsafe;
- Processing failed with retry;
- Scanner temporarily unavailable.

Messages must not disclose scanner internals, filesystem paths or parser stderr.

## 15. Logging and metrics

Allowed:

- request ID;
- document/job/run UUID;
- state transition;
- byte/page counts;
- scanner engine and signature age;
- duration;
- retry count;
- safe failure code;
- aggregate quota usage.

Forbidden:

- original filename;
- document body;
- decrypted bytes;
- patient identifiers;
- analytes or medical values;
- encryption keys/nonces/tags;
- object paths and signed URLs;
- raw scanner/parser output.

## 16. Required tests

### Encryption

- round-trip for source and derivative objects;
- wrong key, nonce, tag or AAD fails closed;
- truncated/corrupted envelope rejected;
- no plaintext file remains;
- key ID selection and rotation;
- unique nonce assertion in stress tests.

### Scanner

- clean fixture;
- EICAR detection in isolated test;
- socket unavailable;
- timeout;
- stale signature database;
- malformed response;
- StreamMaxLength mismatch;
- infected file never reaches parser/rendering.

### Worker and database

- worker role cannot query arbitrary tables;
- worker can execute only allowed functions;
- concurrent workers claim one job once;
- stale lease rejected;
- retry and max-attempt behavior;
- idempotent completion;
- cross-profile keys rejected;
- accepted transition requires current hash and state.

### Parser/rendering

- valid PDF within page limit;
- password-protected PDF rejected;
- malformed PDF rejected;
- page limit enforced;
- timeout and memory exhaustion contained;
- oversized image/decompression bomb rejected;
- metadata stripped from derivatives;
- no raw PDF browser delivery.

### Storage operations

- quota and free-space gate;
- atomic rename;
- crash/orphan reconciliation;
- missing-object reconciliation;
- rollback cleanup;
- object permissions and symlink resistance.

### CI and operations

- migration `0051` full cycle if no competing migration owns the number;
- worker/systemd unit validation;
- ClamAV health/signature checks;
- no sensitive log values;
- exact-head CI;
- no production rollout in the implementation PR.

## 17. Migration sequencing

Current repository head:

```text
0050
```

Candidate Slice C migration:

```text
0051
```

Before assigning `0051`, recheck:

- current main;
- all Alembic heads;
- open PRs with migrations;
- production application and Alembic state.

Likely migration scope:

- worker PostgreSQL role prerequisite check;
- scanner/inspection metadata columns;
- object metadata and encryption key ID;
- job lease/retry indexes and constraints;
- restricted worker functions and grants;
- quota/accounting metadata;
- audit action additions;
- migration-cycle assertions.

## 18. Production rollout prerequisites

Slice C implementation merge does not automatically authorize deployment.

Before any rollout:

- install and verify production storage directories;
- provision encryption key credential and backup escrow;
- install/configure ClamAV and FreshClam;
- verify current signatures;
- provision worker OS and DB identities;
- install hardened systemd unit;
- configure reverse-proxy body limit;
- perform backup and restore-listing checks;
- run disposable clean/EICAR/malformed-file probes;
- verify no document values in logs;
- keep document upload disabled until all gates pass;
- enable only after explicit rollout approval.

## 19. External technical references

- ClamAV clamd protocol: `https://docs.clamav.net/manual/Usage/Scanning.html#clamd-protocol`
- ClamAV signature management: `https://docs.clamav.net/manual/Usage/SignatureManagement.html`
- ClamAV configuration: `https://docs.clamav.net/manual/Usage/Configuration.html`
- cryptography GCM modes: `https://cryptography.io/en/stable/hazmat/primitives/symmetric-encryption.html`
- systemd service credentials: `https://systemd.io/CREDENTIALS/`
- systemd temporary-directory isolation: `https://systemd.io/TEMPORARY_DIRECTORIES/`

## 20. Final current status

```text
SLICE_B_INDEPENDENT_REVIEW_COMPLETE
SLICE_C_ARCHITECTURE_DEFINED
SLICE_C_NOT_IMPLEMENTED
PRODUCTION_UNCHANGED
```
