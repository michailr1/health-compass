# 2026-07-13 — Linux memfd compatibility for constrained CPython builds

Status: `IMPLEMENTED IN BRANCH / CI PENDING / NOT DEPLOYED`.

## Incident

The HC-017 Phase 1 production preflight correctly stopped before migrations because eight rendering/OCR tests failed on the production Python runtime.

The host capability was verified independently:

```text
kernel: 5.4.0-216-generic
kernel memfd_create: supported
file sealing: supported
libc memfd_create: supported
CPython 3.12.13 HAVE_MEMFD_CREATE: 0
```

The failure was caused by a self-contained manylinux CPython build omitting the `os.memfd_create`, `os.MFD_*` and `fcntl.F_*` wrappers at compile time. It was not a missing kernel capability.

No migration, backend restart or frontend release switch occurred.

## Decision

Do not skip the security tests and do not replace sealed memory files with disk-backed temporary files.

Add a centralized Linux compatibility layer that:

- preserves the native CPython API when present;
- otherwise calls libc `memfd_create` for the same Linux kernel primitive;
- restores only missing official Linux UAPI constants;
- continues to apply and verify read-only file seals;
- fails closed with `ENOSYS` when neither native nor libc support exists;
- never creates a filesystem plaintext fallback.

## Verification requirements

- forced libc fallback test;
- missing-stdlib-surface installation test;
- write rejection after seals;
- all existing rendering/OCR tests remain enabled;
- exact-head backend, frontend and PostgreSQL CI;
- production preflight rerun with the same self-contained Python before migration.

## Production boundary

```text
PRODUCTION APPLICATION UNCHANGED
PRODUCTION ALEMBIC UNCHANGED
DOCUMENT_UPLOAD_ENABLED=false
ROLLOUT STOP REMAINS IN EFFECT UNTIL NEW EXACT SHA PASSES CI AND VPS PREFLIGHT
```
