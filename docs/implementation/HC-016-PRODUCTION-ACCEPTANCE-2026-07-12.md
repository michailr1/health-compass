# HC-016 — Production Acceptance

Status: `MANUAL PRODUCTION ACCEPTANCE CONFIRMED`  
Date: 2026-07-12  
Production URL: `https://health.funti.cc`  
Source PR: `#44`  
UI copy follow-up: `#45`  
Merged application target: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Expected Alembic head for HC-016: `0049`

## Accepted result

The profile owner confirmed that the production interface and HC-016 behavior work as intended.

Accepted user-visible behavior:

- **Убрать из профиля** remains a separate soft-removal action;
- **Удалить навсегда** is presented separately to the profile owner;
- permanent deletion requires a destructive confirmation;
- the warning clearly states that the action cannot be undone;
- the sentence about backup-retention periods is no longer shown in the confirmation UI.

Current confirmation text:

```text
Запись и содержащие её медицинские значения в журнале изменений будут удалены. Отменить это действие нельзя.
```

## Implementation evidence already in Git

PR `#44` and its CI cover the HC-016 implementation, including:

- owner-only permanent erasure;
- explicit `confirm_permanent_deletion=true`;
- optimistic concurrency through `expected_updated_at`;
- erasure after withdrawal or absence of medical-data consent;
- no direct runtime DELETE on clinical tables;
- narrowly scoped `SECURITY DEFINER` execution;
- removal of value-bearing audit events;
- creation of an empty `clinical_record.erased` tombstone;
- migration `0048 → 0049` and migration-cycle checks.

PR `#45` contains only the approved user-copy correction and passed CI before merge.

## Evidence boundary

This acceptance record is intentionally limited to facts available in the canonical Git history and the owner’s manual production confirmation.

The detailed VPS rollout transcript was not copied into this record. Therefore this document does not invent or assert:

- a database-backup path or checksum;
- exact release-symlink paths;
- service-process identifiers;
- deployment-window log counts;
- disposable PostgreSQL test output executed on the VPS.

Those operational details may be attached later only from the original VPS report.

## Final status

```text
HC016_ACCEPTED
```
