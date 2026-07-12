# Health Compass — текущее состояние

Дата: 2026-07-12  
Основная ветка: `main`  
Application-code baseline: `ccabab77cf929456a74b69c3478c71f92f167f78`  
Production URL: `https://health.funti.cc`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Repository Alembic head: `0050`  
Текущий verdict: `SLICE B REVIEWED / SLICE C ARCHITECTURE DEFINED / NOT DEPLOYED`

## Production boundary

Production document upload is not available.

```text
DOCUMENT_UPLOAD_ENABLED=false
```

The production application remains on `b8e868...` and Alembic `0049`. Repository migration `0050` and the Slice B UI/API have not been deployed.

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
- preview/download;
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

- `profile_documents`;
- `document_processing_jobs`;
- RLS + FORCE RLS;
- owner/edit insert;
- owner/edit/view metadata visibility;
- analyze exclusion from raw-document metadata;
- no direct runtime UPDATE/DELETE;
- development/test-only private quarantine adapter;
- PDF/JPEG/PNG checks;
- 20 MiB source-file limit;
- bounded multipart and chunked request body;
- 25 MP image limit;
- opaque UUID keys;
- rollback cleanup for route, commit and cancellation failures;
- content-free audit;
- duplicate-account activity protection;
- capabilities/upload/list/detail API;
- `/app/documents` metadata/status UI.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-B-IMPLEMENTATION-2026-07-12.md
```

## Independent Slice B security review

Status: `COMPLETE`.

Verdict:

```text
ACCEPT FOR REPOSITORY FOUNDATION
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

No unresolved Critical or High finding remains in Slice B scope.

Required Slice C controls:

- encrypted production storage;
- storage quota and reserved-free-space gate;
- orphan-object reconciliation;
- reverse-proxy body limit matching backend policy;
- malware scanner with fail-closed behavior;
- isolated worker OS and PostgreSQL identities;
- bounded parser/rasterizer sandbox;
- atomic accepted promotion;
- no medical values or storage paths in ordinary logs.

Canonical review:

```text
docs/reviews/HC-017-SLICE-B-INDEPENDENT-SECURITY-REVIEW-2026-07-12.md
```

## HC-017 Slice C

Status: `ARCHITECTURE DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`.

Selected architecture:

- local encrypted object storage on the production VPS for MVP;
- root outside releases and public web roots;
- versioned AES-256-GCM object envelope;
- key supplied through systemd credentials;
- local ClamAV `clamd` over Unix socket;
- worker streams decrypted plaintext through ClamAV `INSTREAM`;
- `freshclam` maintains official signatures;
- separate `health_compass_worker` OS account;
- separate `health_compass_worker LOGIN NOBYPASSRLS` database role;
- worker uses only restricted job functions;
- sandboxed PDF/image inspection;
- rasterized encrypted derivatives;
- no external OCR/LLM;
- no production enablement in the implementation PR.

Canonical design:

```text
docs/implementation/HC-017-SLICE-C-SCANNER-STORAGE-WORKER.md
```

## Slice C planned controls

### Encrypted object storage

Target root:

```text
/var/lib/health-compass/documents
```

Namespaces:

- quarantine;
- accepted;
- derived;
- orphan;
- trash.

Object keys use only internal UUIDs. Filenames, emails and medical values never appear in paths.

### Malware scanner

- ClamAV daemon on local Unix socket;
- scanner has no direct document-storage access;
- worker decrypts and streams plaintext;
- scanner timeout/outage/stale signatures fail closed;
- infected files never reach parser/rendering;
- signature freshness becomes a rollout gate.

### Restricted worker

- separate OS identity;
- separate NOBYPASSRLS database login;
- no direct document/profile table grants;
- constrained claim/heartbeat/complete/fail functions;
- lease ownership and stale-attempt checks;
- hardened systemd sandbox and resource limits.

### Safe inspection/rendering

- scanner runs before parser;
- password-protected or malformed PDF rejected;
- page limit enforced;
- pages rendered individually under timeout/memory limits;
- browser never embeds raw PDF;
- image metadata stripped;
- derivatives encrypted before persistent storage.

### Operational safety

- per-profile/global quotas;
- reserved free-space threshold;
- orphan reconciliation;
- atomic accepted promotion;
- reverse-proxy request limit;
- non-sensitive logs and metrics only.

## Next allowed work

```text
HC-017 Slice C implementation
```

Before implementation:

1. recheck current `main` and all Alembic heads;
2. verify no open PR owns candidate migration `0051`;
3. define exact storage envelope and parser tests;
4. implement worker role/functions first;
5. implement encryption and scanner clients;
6. implement quota and reconciliation controls;
7. implement safe rendering;
8. run independent review before any deployment decision.

## Stop conditions

Stop merge or rollout when:

- storage is public or under the web root;
- encryption key is stored in Git, `.env` or database;
- nonce reuse is possible;
- scanner is absent, stubbed, stale or fail-open;
- worker uses app/migrator credentials;
- worker has broad table access;
- raw PDF is embedded in browser;
- parser/rendering lacks page, CPU, memory or timeout limits;
- storage quota/free-space protection is absent;
- orphan reconciliation is absent;
- object path, signed URL or medical content enters ordinary logs;
- cross-profile access is possible;
- migration has multiple heads;
- exact-head CI or PostgreSQL negative tests are missing;
- production upload is enabled before explicit controlled rollout approval.
