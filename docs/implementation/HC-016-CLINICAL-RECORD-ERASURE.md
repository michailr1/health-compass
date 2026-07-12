# HC-016 — Owner-controlled Clinical Record Erasure

Status: `MERGED / PRODUCTION MANUALLY ACCEPTED`  
Implemented and merged: 2026-07-12  
Production acceptance: 2026-07-12  
Source PR: `#44`  
UI copy follow-up: `#45`  
Merged application target: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Alembic head: `0049`

## Product decision

Clinical Context distinguishes two user intentions:

1. **Remove from profile** — the record is voided and retained in protected history.
2. **Delete permanently** — the live record and audit entries containing its medical values are erased.

This is required because a user can enter a fact by mistake or decide that they no longer want Health Compass to retain it.

## Privacy and safety contract

Permanent erasure:

- is available only to the profile owner;
- requires an explicit irreversible confirmation;
- requires the current `updated_at` value to prevent deleting a record changed in another window or device;
- remains available even when health-data consent is absent or has been revoked;
- deletes value-bearing audit events for the record in the same transaction;
- leaves only a generic content-free security tombstone;
- does not retain the record section, label, dose, reaction, status or deletion reason in that tombstone.

Backup lifecycle is governed by the separate infrastructure and privacy-retention policy. It is intentionally not described in the user-facing permanent-erasure confirmation.

## Database boundary

Direct table `DELETE` remains revoked from `health_compass_app`.

The only runtime erasure path is:

```text
health_compass.app_erase_clinical_record(...)
```

The function:

- is `SECURITY DEFINER`;
- is owned by `health_compass_rls_definer`;
- has a fixed empty `search_path` and `row_security=off`;
- has no PUBLIC EXECUTE;
- is executable only by the runtime application role;
- validates profile ownership inside PostgreSQL;
- serializes against Clinical Context review-state transitions;
- performs record deletion, audit scrubbing and tombstone creation atomically.

## API

Owner-only endpoints:

```text
DELETE /profiles/{profile_id}/conditions/{record_id}
DELETE /profiles/{profile_id}/allergies/{record_id}
DELETE /profiles/{profile_id}/medications/{record_id}
DELETE /profiles/{profile_id}/supplements/{record_id}
DELETE /profiles/{profile_id}/clinical-safety-flags/{record_id}
```

Request body:

```json
{
  "expected_updated_at": "<record timestamp>",
  "confirm_permanent_deletion": true
}
```

## UI

Each Clinical Context record exposes:

- **Убрать из профиля** — removes the record from the active profile while retaining protected history;
- **Удалить навсегда** — owner-only, with a separate destructive confirmation panel.

Current confirmation text:

```text
Запись и содержащие её медицинские значения в журнале изменений будут удалены. Отменить это действие нельзя.
```

The previous sentence about backup-retention periods was removed from the UI in PR `#45`.

## Verification requirements

The implementation and CI cover:

- direct runtime DELETE remains denied;
- editor, viewer and outsider cannot call permanent erasure;
- owner can erase without active consent;
- stale timestamp returns conflict without deleting anything;
- content-bearing audit rows are removed;
- only an empty generic tombstone remains;
- function ownership, fixed configuration and grants are verified;
- frontend sends explicit confirmation and optimistic-concurrency timestamp;
- migration `0048 → 0049`, downgrade and full migration cycle pass.

## Production acceptance

On 2026-07-12 the profile owner confirmed that the production UI and HC-016 flows work as intended, including the corrected confirmation copy.

This document records the confirmed user-level result. A detailed VPS command transcript, backup path, service output and disposable PostgreSQL test report were not copied into this repository entry and therefore are not asserted here.

Canonical acceptance record:

`docs/implementation/HC-016-PRODUCTION-ACCEPTANCE-2026-07-12.md`
