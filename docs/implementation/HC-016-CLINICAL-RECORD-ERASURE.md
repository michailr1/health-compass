# HC-016 — Owner-controlled Clinical Record Erasure

Status: `IMPLEMENTED / NOT MERGED / NOT DEPLOYED`

## Product decision

Clinical Context now distinguishes two user intentions:

1. **Remove from profile** — the record is voided and retained in protected history.
2. **Delete permanently** — the live record and audit entries containing its medical values are erased.

This is required because a user can enter a fact by mistake or decide that they no longer want Health Compass to retain it.

## Privacy and safety contract

Permanent erasure:

- is available only to the profile owner;
- requires an explicit irreversible confirmation;
- requires the current `updated_at` value to prevent deleting a record changed in another window/device;
- remains available even when health-data consent is absent or has been revoked;
- deletes value-bearing audit events for the record in the same transaction;
- leaves only a generic content-free security tombstone;
- does not retain the record section, label, dose, reaction, status or deletion reason in that tombstone.

Existing backups are not rewritten in place. The UI states that backup copies may persist until the configured retention period expires.

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

- **Убрать из профиля** — recoverable only through protected historical handling;
- **Удалить навсегда** — owner-only, with a separate destructive confirmation panel.

## Verification requirements

- direct runtime DELETE remains denied;
- editor/viewer/outsider cannot call permanent erasure;
- owner can erase without active consent;
- stale timestamp returns conflict without deleting anything;
- content-bearing audit rows are removed;
- only an empty generic tombstone remains;
- function ownership, fixed configuration and grants are verified;
- frontend sends explicit confirmation and optimistic-concurrency timestamp;
- migration `0048 → 0049`, downgrade and full migration cycle pass.
