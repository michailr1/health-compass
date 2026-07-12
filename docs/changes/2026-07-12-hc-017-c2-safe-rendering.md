# 2026-07-12 — HC-017 C2 Quotas, Reconciliation and Safe Rendering

HC-017 C2 was implemented in PR `#53` and merged into `main`.

```text
verified head: 568eca1ec1c91005b907cc79349036a71d7f6f83
merge: 06e4f0a228b4867d9bf7983284bc04f3cb53cd05
CI: #433
repository Alembic: 0053
```

Implemented:

- race-safe profile/global upload quotas;
- reserved free-space configuration;
- canonical source-object reference;
- encrypted safe-page artifact metadata with FORCE RLS;
- separate renderer and reconciler NOBYPASSRLS roles;
- no direct worker table grants;
- full GCM verification before parser access;
- sealed read-only memory-file input/output;
- bounded PDF/image subprocesses;
- strict PNG validation;
- encrypted accepted source and safe-page derivatives;
- atomic/idempotent accepted promotion;
- orphan and missing-object reconciliation;
- idempotent repeated missing-object audit behavior.

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

C2 does not add production package provisioning, upload enablement, browser document preview/download, OCR, extraction candidates or Labs observations.

Next stage:

```text
HC-017 Slice D — OCR Candidates and Human Review
```

Canonical evidence:

- `docs/implementation/HC-017-SLICE-C2-SAFE-RENDERING-EVIDENCE-2026-07-12.md`;
- `docs/CURRENT-STATE.md`;
- `docs/PROJECT-PLAN.md`;
- `docs/source-index/SOURCE-REGISTER.md`.
