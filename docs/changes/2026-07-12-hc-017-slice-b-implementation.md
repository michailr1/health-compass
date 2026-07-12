# 2026-07-12 — HC-017 Slice B Secure Document Intake Foundation

HC-017 Slice B was implemented in PR `#48` and merged into `main`.

Verified implementation head:

```text
46c5ea89d35cc85be0af3b80a9c56f40d5705ac5
```

Merge commit:

```text
ccabab77cf929456a74b69c3478c71f92f167f78
```

CI run `#402` passed backend, frontend, migration-cycle and PostgreSQL RLS/integration jobs.

Repository Alembic head is now:

```text
0050
```

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
```

Slice B adds a development/test-only secure intake foundation:

- document metadata and durable intake jobs;
- FORCE RLS and document-specific access matrix;
- private UUID-keyed quarantine storage adapter;
- PDF/JPEG/PNG validation;
- pre-parser body limits for normal and chunked requests;
- rollback cleanup for external objects;
- content-free audit;
- duplicate-account activity protection;
- upload/list/detail API;
- minimal Documents UI.

It does not add production storage, malware scanning, preview, download, worker processing, OCR, Labs data or production upload.

Production configuration rejects `DOCUMENT_UPLOAD_ENABLED=true` outside development.

Next stage:

```text
independent Slice B security review
→ production storage decision
→ scanner/worker design
→ HC-017 Slice C
```

Canonical evidence:

- `docs/implementation/HC-017-DOCUMENTS-OCR-LABS-FOUNDATION.md`;
- `docs/implementation/HC-017-SLICE-B-IMPLEMENTATION-2026-07-12.md`;
- `docs/CURRENT-STATE.md`;
- `docs/PROJECT-PLAN.md`.
