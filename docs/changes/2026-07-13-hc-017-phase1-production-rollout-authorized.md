# 2026-07-13 — HC-017 Phase 1 production rollout authorized

Status: `AUTHORIZED / NOT YET DEPLOYED`.

## Decision

The owner authorized deployment of the current `main` implementation to the existing `health.funti.cc` host for controlled testing before HC-017 E3.

The environment currently has no external users or irreplaceable production health data, so the working production host may be used as the owner test environment. The rollout remains backup-first and exact-SHA because authentication, PostgreSQL RLS and migrations are security-sensitive.

## Phase 1 boundary

Phase 1 deploys application code and migrations through Alembic `0058`, but keeps:

```text
DOCUMENT_UPLOAD_ENABLED=false
```

The current application intentionally rejects production startup with document upload enabled. Therefore Phase 1 validates migration, startup, authentication, existing product regression, frontend serving and security boundaries, but does not yet execute the full document/OCR/Labs pipeline.

## Agent responsibility

The VPS agent only deploys and verifies an exact GitHub SHA. It must not:

- write or edit product code;
- create or modify migrations;
- commit, push, merge or edit GitHub;
- invent database roles, passwords or environment values;
- expose secrets in output.

## Canonical rollout plan

```text
docs/implementation/HC-017-B-E2-CONTROLLED-PRODUCTION-ROLLOUT.md
```

## Production status

At the time of this decision:

```text
DEPLOYMENT NOT YET PERFORMED
PRODUCTION APPLICATION UNCHANGED
PRODUCTION ALEMBIC UNCHANGED
DOCUMENT UPLOAD DISABLED
```
