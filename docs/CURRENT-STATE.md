# Health Compass — текущее состояние

Дата: 2026-07-12  
Основная ветка: `main`  
Application-code baseline: `a0dd405ca3e789cb70e5c4ad94de9a272dff878f`  
Production URL: `https://health.funti.cc`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Repository Alembic head: `0051`  
Текущий verdict: `HC-017 C1 MERGED / CI VERIFIED / NOT DEPLOYED`

## Production boundary

Production document upload is not available.

```text
DOCUMENT_UPLOAD_ENABLED=false
```

The production application remains on `b8e868...` and Alembic `0049`. Repository migrations `0050–0051`, document UI/API, encrypted storage and scanner worker have not been deployed.

No VPS deployment task has been issued for HC-017 C1.

## Production capabilities

Production currently provides:

- Google OIDC and Email Magic Links;
- PostgreSQL sessions;
- tenant isolation with FORCE RLS;
- workspaces, profiles and permissions;
- Basic Health Profile and weight history;
- consent, provenance and audit;
- Clinical Context and review states;
- contextual intake;
- Russian-first Clinical Dictionaries;
- owner-controlled permanent clinical-record erasure.

Production does not provide:

- document upload;
- document storage;
- malware scanning;
- preview or download;
- safe document rendering;
- OCR;
- Labs observations;
- metric dynamics.

## HC-017 Slice A

Status: `ARCHITECTURE MERGED` through PR `#47`.

Canonical document:

```text
docs/implementation/HC-017-DOCUMENTS-OCR-LABS-FOUNDATION.md
```

## HC-017 Slice B

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

Evidence:

```text
PR: #48
verified head: 46c5ea89d35cc85be0af3b80a9c56f40d5705ac5
merge: ccabab77cf929456a74b69c3478c71f92f167f78
CI: #402
migration: 0050
```

Implemented in repository:

- document metadata and durable jobs;
- RLS + FORCE RLS;
- document-specific owner/edit/view boundary;
- analyze exclusion from raw-document metadata;
- bounded PDF/JPEG/PNG intake;
- pre-parser request body limit;
- opaque storage keys;
- transaction rollback cleanup;
- content-free audit;
- duplicate-account activity protection;
- capabilities/upload/list/detail API;
- `/app/documents` metadata/status UI.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-B-IMPLEMENTATION-2026-07-12.md
```

## Independent Slice B review

Status: `COMPLETE`.

Verdict:

```text
ACCEPT FOR REPOSITORY FOUNDATION
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

Canonical review:

```text
docs/reviews/HC-017-SLICE-B-INDEPENDENT-SECURITY-REVIEW-2026-07-12.md
```

## HC-017 Slice C architecture

Status: `DEFINED`.

Canonical design:

```text
docs/implementation/HC-017-SLICE-C-SCANNER-STORAGE-WORKER.md
```

Selected direction:

- local encrypted private object storage;
- authenticated object encryption;
- systemd-delivered keys;
- local ClamAV Unix socket;
- FreshClam signature updates;
- isolated worker OS and PostgreSQL identities;
- safe rasterized derivatives;
- quotas and orphan reconciliation;
- no external OCR/LLM.

## HC-017 Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

Evidence:

```text
PR: #51
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

### Authenticated encrypted objects

Implemented:

- `HCENC1` versioned envelope;
- streaming AES-256-GCM;
- unique random nonce per object;
- AAD binding document UUID and artifact role;
- plaintext SHA-256 calculated during encryption;
- GCM tag verification before a scanner result can finish;
- exclusive encrypted object publication;
- occupied object keys are never overwritten or deleted;
- final symlink, non-regular file and multiple hard links are rejected;
- no application-created plaintext file in persistent document storage.

### Key boundary

Implemented:

- strict key ID allowlist;
- key file opened with `O_NOFOLLOW`;
- regular single-link file requirement;
- group/world-writable files rejected;
- exact 32-byte key requirement;
- symlink and hard-link regression tests;
- key material remains outside Git, environment values and database rows.

### Scanner metadata and jobs

Migration `0051` adds:

- encrypted size;
- encryption format and key ID metadata;
- scanner status and version metadata;
- signature version/timestamp;
- scanner completion timestamp;
- retry scheduling metadata.

New encrypted intake creates:

```text
storage_backend = local_encrypted
encryption_format = hcenc1
scanner_status = not_scanned
job_type = scan
```

### Restricted worker boundary

Required database role:

```text
health_compass_worker LOGIN NOBYPASSRLS
```

Implemented restricted functions:

```text
app_claim_document_job
app_heartbeat_document_job
app_complete_document_scan
app_fail_document_job
```

Security properties:

- dedicated definer ownership;
- fixed empty search path;
- no PUBLIC or application-role execution;
- worker-only execution;
- no direct worker table privileges;
- stale lease protection;
- bounded retries and attempts;
- idempotent identical completion;
- content-free scan audit.

### ClamAV client

Implemented:

- local Unix-socket `VERSION` and `INSTREAM` client;
- bounded plaintext stream;
- signature freshness check;
- strict result parsing;
- scanner unavailable/stale/protocol error fails closed;
- infected object is rejected and enters deletion lifecycle;
- GCM finalization occurs before the terminating INSTREAM frame;
- corrupted ciphertext cannot receive a clean result;
- malware signature names and raw scanner output are not exposed.

### User-facing status

API/UI exposes only safe scanner states:

```text
not_scanned
scanning
clean
infected
error
stale
```

Internal paths, hashes, encryption key IDs and scanner response text remain hidden.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-C1-IMPLEMENTATION-2026-07-12.md
```

## C1 verification

CI `#414` passed on exact head `c32e420b...`:

- Python compile;
- Ruff;
- backend unit tests;
- frontend lint/typecheck/tests/build;
- migration boundary tests;
- full isolated `head → base → head`;
- PostgreSQL RLS and worker privilege integration tests.

No unresolved Critical or High finding remains in the C1 repository scope.

## Remaining production blockers

C1 is not production-ready by itself.

Required before any rollout:

- production encryption-key provisioning and recovery procedure;
- private production storage directories;
- dedicated worker operating-system account;
- hardened systemd worker unit;
- ClamAV/FreshClam installation and signature-health checks;
- scanner Unix-socket permission verification;
- matching reverse-proxy request limit;
- isolated and bounded multipart temporary spool;
- per-profile and global storage quotas;
- reserved free-space accounting;
- orphan and missing-object reconciliation;
- safe PDF/image inspection and rasterization;
- encrypted page derivatives;
- atomic accepted promotion;
- EICAR/clean/malformed-file deployment probes;
- no-sensitive-log verification.

## Next allowed work

```text
HC-017 Slice C2 — Quotas, Reconciliation and Safe Rendering
```

C2 must:

1. preserve separation between scanner and renderer job permissions;
2. add quotas and reserved-free-space accounting;
3. add orphan and missing-object reconciliation;
4. verify the complete encrypted source before parser access;
5. run PDF/image processing under CPU, memory, page, pixel, file-size and timeout limits;
6. persist only encrypted safe derivatives;
7. never expose the raw PDF to the browser;
8. keep OCR out of this slice;
9. pass independent security review before any rollout decision.

## Stop conditions

Stop merge or rollout when:

- storage is public or inside web/release paths;
- encryption key is stored in Git, `.env` or database;
- scanner is absent, stale, stubbed or fail-open;
- worker uses application or migrator credentials;
- worker has broad table access;
- raw PDF reaches the browser;
- parser lacks CPU, memory, page, pixel or timeout limits;
- quota/free-space gates are absent;
- reconciliation is absent;
- accepted promotion is not atomic/idempotent;
- filenames, paths, scanner output or medical content enter ordinary logs;
- migration has multiple heads;
- exact-head CI or negative PostgreSQL tests are missing;
- production upload is enabled before controlled rollout approval.
