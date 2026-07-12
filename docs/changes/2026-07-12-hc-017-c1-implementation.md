# 2026-07-12 — HC-017 C1 Encrypted Scanner Worker Foundation

HC-017 Slice C1 was implemented in PR `#51` and merged into `main`.

Verified implementation head:

```text
c32e420b59d950aad48366c79010f5ac9fecb43b
```

Merge commit:

```text
a0dd405ca3e789cb70e5c4ad94de9a272dff878f
```

CI run:

```text
#414 — success
```

Repository Alembic head:

```text
0051
```

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

C1 adds repository foundations for:

- streaming AES-256-GCM encrypted objects;
- hardened key-file loading;
- opaque exclusive quarantine object publication;
- encrypted/scanner metadata;
- restricted `health_compass_worker` PostgreSQL boundary;
- claim, heartbeat, complete and fail functions;
- local ClamAV Unix-socket scanning;
- signature freshness and fail-closed behavior;
- infected/invalid object deletion lifecycle;
- safe scanner states in API and UI.

C1 does not add:

- production keys or storage directories;
- production worker/systemd service;
- installed ClamAV/FreshClam;
- quotas or reconciliation;
- safe rendering;
- OCR;
- Labs observations;
- production migration or deployment.

Next stage:

```text
HC-017 C2 — Quotas, Reconciliation and Safe Rendering
```

Canonical evidence:

- `docs/implementation/HC-017-SLICE-C1-IMPLEMENTATION-2026-07-12.md`;
- `docs/CURRENT-STATE.md`;
- `docs/PROJECT-PLAN.md`;
- `docs/source-index/SOURCE-REGISTER.md`.
