# Health Compass — текущее состояние

Дата: 2026-07-12  
Основная ветка: `main`  
Repository application baseline: `06e4f0a228b4867d9bf7983284bc04f3cb53cd05`  
Repository Alembic head: `0053`  
Production URL: `https://health.funti.cc`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Текущий verdict: `HC-017 C2 MERGED / CI VERIFIED / NOT DEPLOYED`

## Production boundary

Production document upload remains unavailable.

```text
DOCUMENT_UPLOAD_ENABLED=false
```

Repository and production intentionally differ:

```text
repository: 06e4f0a2... / Alembic 0053
production: b8e86882... / Alembic 0049
```

Migrations `0050–0053`, encrypted document storage, scanner worker, quota controls, reconciliation and safe rendering have not been deployed. No VPS rollout task has been issued for HC-017.

## What works in production

- Google OIDC and Email Magic Links;
- PostgreSQL sessions;
- workspace/profile permissions and FORCE RLS;
- Basic Health Profile and weight history;
- consent, provenance and audit;
- Clinical Context and review states;
- contextual intake;
- Russian-first Clinical Dictionaries;
- owner-controlled permanent clinical-record erasure.

Production does not provide:

- document upload or storage;
- malware scanning;
- safe rendering;
- source/derivative preview or download;
- OCR;
- extraction review;
- Labs observations;
- metric dynamics.

## HC-017 Slice A — Architecture

Status: `MERGED` through PR `#47`.

Canonical document:

```text
docs/implementation/HC-017-DOCUMENTS-OCR-LABS-FOUNDATION.md
```

## HC-017 Slice B — Secure Document Intake Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

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
- owner/edit/view metadata boundary;
- analyze exclusion from raw-document metadata;
- bounded PDF/JPEG/PNG intake;
- pre-parser request limit;
- opaque storage keys;
- transaction rollback cleanup;
- content-free audit;
- capabilities/upload/list/detail API;
- minimal Documents UI.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-B-IMPLEMENTATION-2026-07-12.md
```

## HC-017 Slice C1 — Encrypted Scanner Worker Foundation

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #51
verified head: c32e420b59d950aad48366c79010f5ac9fecb43b
merge: a0dd405ca3e789cb70e5c4ad94de9a272dff878f
CI: #414
migration: 0051
```

Implemented:

- versioned `HCENC1` AES-256-GCM object envelope;
- unique nonce and AAD document/artifact binding;
- key files opened with `O_NOFOLLOW` and strict permissions;
- encrypted quarantine objects without persistent plaintext files;
- local ClamAV Unix-socket client;
- scanner signature freshness gate;
- separate `health_compass_worker LOGIN NOBYPASSRLS` role;
- no direct worker table grants;
- restricted claim/heartbeat/complete/fail functions;
- stale lease, retry and idempotent completion protection;
- infected-document rejection and deletion lifecycle;
- safe scanner status API/UI.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-C1-IMPLEMENTATION-2026-07-12.md
```

## HC-017 Slice C2 — Quotas, Reconciliation and Safe Rendering

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`.

```text
PR: #53
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
migrations: 0052–0053
```

### Quota and storage accounting

- profile/global byte limits;
- active-document and queued-job limits;
- transaction advisory locks prevent concurrent quota bypass;
- reserved free-space configuration;
- canonical `current_storage_key` for authoritative source objects.

### Renderer boundary

Required role:

```text
health_compass_renderer LOGIN NOBYPASSRLS
```

Controls:

- separate claim/heartbeat/complete/fail functions;
- no direct renderer table grants;
- full GCM verification before parser access;
- sealed read-only Linux memfd input and output;
- fixed executable paths and arguments;
- no shell invocation;
- CPU, memory, file-size, page, pixel and timeout limits;
- PDF encryption/page checks;
- PNG signature, chunk, CRC, dimensions and `IEND` validation;
- encrypted accepted source and safe-page derivatives;
- atomic and idempotent accepted promotion;
- raw PDF is not exposed through the browser.

### Reconciliation boundary

Required role:

```text
health_compass_reconciler LOGIN NOBYPASSRLS
```

Implemented:

- opaque source/artifact reference inventory;
- orphan isolation and deletion flow;
- missing referenced-object detection;
- content-free storage-missing audit;
- repeated missing-object checks are idempotent;
- no direct reconciler table grants.

### C2 verification

Exact-head CI `#433` passed:

- backend compile/Ruff/unit tests;
- frontend lint/typecheck/tests/build;
- migration boundary;
- full isolated `head → base → head`;
- scanner, renderer and reconciler execute matrices;
- no direct worker table privileges;
- functional renderer completion and artifact RLS;
- sealed-memory and strict PNG tests;
- reconciliation idempotency.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-C2-SAFE-RENDERING-EVIDENCE-2026-07-12.md
```

## Remaining production blockers

C1+C2 are repository foundations, not a production-ready service.

Required before rollout:

- production encryption-key provisioning, recovery and rotation procedure;
- private storage directories and permissions;
- dedicated OS users for scanner, renderer and reconciler;
- hardened systemd units and resource limits;
- verified production Poppler/ImageMagick versions;
- ClamAV/FreshClam installation and healthy signatures;
- scanner Unix-socket permission checks;
- reverse-proxy request-size boundary;
- isolated bounded multipart spool;
- measured production quota and disk-reserve values;
- clean/EICAR/malformed/password/timeout/resource probes;
- no-sensitive-log verification;
- independent combined C1+C2 security review;
- explicit controlled rollout approval.

## Next allowed work

```text
HC-017 Slice D — OCR Candidates and Human Review
```

Rules for Slice D:

1. OCR consumes only encrypted C2 safe-page artifacts.
2. Raw PDF never reaches OCR or browser preview.
3. OCR text is an untrusted draft, not a medical fact.
4. Candidate text requires owner/edit review.
5. Page and bounding-box provenance is retained.
6. Patient matching is a separate explicit decision.
7. No automatic Clinical Context or Labs record is created.
8. Optimistic concurrency protects human review.
9. Production upload remains disabled.
10. Slice D implementation and production rollout remain separate PRs.

## Stop conditions

Stop merge or rollout when:

- worker roles gain broad table privileges;
- parser/OCR receives unauthenticated source bytes;
- raw documents are exposed through static or download routes;
- encrypted object keys contain filenames or medical values;
- CPU, memory, file-size, page, pixel or timeout limits are absent;
- missing-object reconciliation is non-idempotent;
- OCR output becomes a clinical fact automatically;
- patient mismatch can be bypassed;
- logs contain filenames, object paths, OCR text or medical values;
- Alembic has multiple heads;
- exact-head CI or negative PostgreSQL tests are missing;
- production upload is enabled before controlled rollout approval.
