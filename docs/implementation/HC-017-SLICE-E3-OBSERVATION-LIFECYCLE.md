# HC-017 E3 — Correction, Void and Owner-only Erasure

Status: `IMPLEMENTED IN BRANCH / REVIEW AND CI PENDING / NOT DEPLOYED`  
Migration: `0059`  
Production remains: application `fb1e7a2f...`, Alembic `0058`.

## 1. Purpose

Add an explicit lifecycle for confirmed laboratory observations without ever editing confirmed source/value fields in place.

E3 distinguishes three user intentions:

1. **Correct** — create a new immutable replacement snapshot.
2. **Void** — remove an observation from active use while preserving provenance and a bounded reason.
3. **Delete permanently** — owner-only irreversible removal of the complete connected correction chain and its value-bearing provenance.

## 2. Immutable replacement contract

Correction never updates these fields on the confirmed observation:

- source analyte wording;
- source value wording;
- parsed value and comparator;
- unit and reference-range wording;
- source date/specimen/flag/comment;
- document/OCR/candidate provenance snapshots.

A correction:

- requires owner/edit access;
- requires active health-data consent because it creates a new medical record;
- requires optimistic `lifecycle_version`;
- requires a bounded reason and idempotency key;
- inserts a new active observation;
- copies the immutable candidate/source snapshots;
- sets `new.supersedes_observation_id = old.id`;
- sets `old.superseded_by_observation_id = new.id`;
- changes only lifecycle metadata on the old row;
- preserves the complete predecessor/replacement chain.

## 3. Void contract

Void:

- requires owner/edit access;
- applies only to an active observation;
- requires optimistic `lifecycle_version`;
- requires a bounded explicit reason;
- changes only lifecycle fields;
- preserves source/value/provenance snapshots;
- remains available after consent withdrawal;
- immediately excludes the observation from `view`, `analyze`, metrics and normal active reads.

## 4. Permanent erasure contract

Permanent observation erasure:

- is available only to the profile owner;
- requires explicit irreversible confirmation;
- requires optimistic `lifecycle_version`;
- remains available after consent withdrawal;
- resolves the complete connected correction chain;
- deletes every observation in that chain atomically;
- deletes immutable source snapshots and originating draft/source rows;
- removes earlier Lab audit rows for the erased chain;
- leaves only a generic content-free `lab.observation_erased` tombstone;
- never stores the medical values or erasure reason in the tombstone.

Erasing one member removes the whole chain. This avoids dangling predecessor/successor links and unsupported provenance.

## 5. Document-linked Lab erasure

The owner-only document Lab erasure function:

- requires explicit confirmation and current document `updated_at`;
- marks the document `deletion_pending` immediately;
- makes document-derived observations inaccessible through RLS immediately;
- deletes all Lab observations, source snapshots, drafts and draft sources for that document atomically;
- leaves external encrypted-object deletion to the separately controlled document storage lifecycle.

This function does not claim that the encrypted source object has already been physically erased.

## 6. Access matrix

| Operation/data | owner | edit | view | analyze |
|---|---:|---:|---:|---:|
| Read active structured observation | yes | yes | yes | yes |
| Read superseded/voided lifecycle history | yes | yes | no | no |
| Read OCR reviewed-text source snapshots | yes | yes | no | no |
| Correct by replacement | yes | yes | no | no |
| Void | yes | yes | no | no |
| Permanently erase observation chain | yes | no | no | no |
| Request document-linked Lab erasure | yes | no | no | no |

The E3 migration corrects an E2 over-broad source policy: `view` and `analyze` retain access to active structured observations but no longer receive OCR text snapshots.

## 7. Database boundary

Direct application-role `INSERT`, `UPDATE` and `DELETE` remain revoked.

Runtime mutations are limited to:

```text
app_correct_lab_observation(...)
app_void_lab_observation(...)
app_erase_lab_observation(...)
app_request_document_lab_erasure(...)
```

Each function:

- is `SECURITY DEFINER`;
- is owned by `health_compass_rls_definer`;
- uses empty `search_path` and `row_security=off`;
- rejects non-application sessions;
- has PUBLIC execute revoked;
- is not executable by scanner/renderer/reconciler/OCR roles;
- returns content-free errors and writes content-free audit entries.

## 8. API

```text
GET    /profiles/{profile_id}/labs/observations/history
POST   /profiles/{profile_id}/labs/observations/{id}/correct
POST   /profiles/{profile_id}/labs/observations/{id}/void
DELETE /profiles/{profile_id}/labs/observations/{id}
DELETE /profiles/{profile_id}/documents/{document_id}/lab-data
```

The lifecycle-history endpoint is owner/edit-only. Normal E2 observation reads remain active-only.

## 9. Required verification

- direct source/value updates remain denied;
- correction creates a replacement and does not alter the old snapshot;
- idempotent correction returns the same replacement;
- stale lifecycle versions fail without partial writes;
- view/analyze see only active structured observations;
- view/analyze cannot read source OCR snapshots;
- void remains available after consent withdrawal;
- voided observations disappear from active reads;
- editors cannot permanently erase;
- owners can erase after consent withdrawal;
- full chains and originating Lab drafts are removed atomically;
- document erasure leaves no document-derived Lab observation or draft;
- functions have exact ownership/config/grants;
- full migration, downgrade guard, PostgreSQL/RLS, backend and frontend CI pass.

## 10. Stop conditions

Do not merge or deploy if:

- a confirmed source/value field can be edited in place;
- a correction loses original provenance;
- more than one active successor can replace the same observation;
- a non-owner can permanently erase;
- erasure leaves a broken lifecycle link or sole-provenance row;
- view/analyze can read OCR source text;
- document `deletion_pending` observations remain visible;
- medical values or reasons enter ordinary audit/logs;
- direct broad runtime mutation grants exist;
- exact-head PostgreSQL negative tests are missing or failing.

## 11. Production boundary

```text
NO PRODUCTION CHANGE
DOCUMENT_UPLOAD_ENABLED=false
PRODUCTION ALEMBIC=0058
E3 REQUIRES INDEPENDENT REVIEW AND EXACT-HEAD CI BEFORE ANY ROLLOUT DECISION
```
