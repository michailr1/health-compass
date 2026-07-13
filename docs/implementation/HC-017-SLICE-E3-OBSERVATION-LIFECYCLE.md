# HC-017 E3 — Correction, Void and Owner-only Erasure

Status: `IMPLEMENTED IN BRANCH / REVIEW AND CI PENDING / NOT DEPLOYED`  
Migrations: `0059–0062`  
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
- requires fresh acknowledgement of source, unit/range, date, profile and structured-record creation;
- requires separate profile-assignment acknowledgement for `not_present`;
- inserts a new active observation;
- copies the immutable candidate/source snapshots;
- sets `new.supersedes_observation_id = old.id`;
- sets `old.superseded_by_observation_id = new.id`;
- changes only lifecycle metadata on the old row;
- preserves the complete predecessor/replacement chain.

The old correction SQL signature remains in migration history but application-role execute is revoked. Runtime correction uses only the hardened acknowledgement-bearing signature.

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
- resolves and rechecks the complete connected correction chain;
- locks the chain in deterministic order with `NOWAIT`;
- returns controlled `HC409` when the lifecycle is busy instead of deadlocking;
- deletes every observation in the stabilized chain atomically;
- deletes immutable source snapshots and originating draft/source rows;
- removes earlier Lab audit rows for the erased chain;
- leaves only a generic content-free `lab.observation.erased` tombstone;
- never stores medical values or erasure reasons in the tombstone.

Erasing one member removes the whole chain. This avoids dangling predecessor/successor links and unsupported provenance.

## 5. Document-linked Lab erasure

The owner-only document Lab erasure function:

- requires explicit confirmation and current document `updated_at`;
- marks the document `deletion_pending` immediately;
- deletes all Lab observations, source snapshots, drafts and draft sources for that document atomically;
- leaves external encrypted-object deletion to the separately controlled document storage lifecycle.

Migration `0060` adds an independent `SECURITY DEFINER` document-state guard to every Lab read policy. Active observations and OCR snapshots are hidden whenever the source document is `deletion_pending` or erased, even when document state changed through another application path.

Migration `0061` adds a protected transition trigger. Before any document enters deletion/erasure, related Lab drafts and observations are locked in deterministic order with `NOWAIT`. Concurrent correction/confirmation returns controlled `HC409`; it cannot create a post-erasure orphan or PostgreSQL deadlock.

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

The E3 migration corrects an E2 over-broad source policy: `view` and `analyze` retain active structured-observation access but no longer receive OCR text snapshots.

## 7. Database boundary

Direct application-role `INSERT`, `UPDATE` and `DELETE` on Lab observation/draft tables remain revoked. Existing document-intake and audit grants are preserved.

Runtime lifecycle mutations are limited to:

```text
app_correct_lab_observation(... acknowledgements ...)
app_void_lab_observation(...)
app_erase_lab_observation(...)
app_request_document_lab_erasure(...)
```

Read and transition guards:

```text
app_lab_document_available(...)
app_guard_document_lab_erasure_transition()
```

Each function:

- is `SECURITY DEFINER`;
- is owned by `health_compass_rls_definer`;
- uses empty `search_path` and `row_security=off`;
- rejects, returns false or is non-callable for unauthorized sessions;
- has PUBLIC execute revoked;
- is not executable by scanner/renderer/reconciler/OCR roles;
- returns content-free errors and writes content-free audit entries where applicable.

Migration `0062` extends the closed audit action vocabulary for the hardened correction/erasure action names without permitting arbitrary actions.

## 8. API and UI

```text
GET    /profiles/{profile_id}/labs/observations/history
POST   /profiles/{profile_id}/labs/observations/{id}/correct
POST   /profiles/{profile_id}/labs/observations/{id}/void
DELETE /profiles/{profile_id}/labs/observations/{id}
DELETE /profiles/{profile_id}/documents/{document_id}/lab-data
```

The lifecycle-history endpoint is owner/edit-only. Normal E2 observation reads remain active-only.

Frontend route:

```text
/app/labs
```

The UI:

- displays active and historical versions;
- creates corrections as new records;
- requires a reason for correction and void;
- asks for fresh explicit correction acknowledgements before sending the request;
- asks separately for profile assignment when the source had no patient name;
- makes permanent erasure owner-only;
- requires typing `УДАЛИТЬ` before irreversible erasure;
- does not add another primary mobile navigation tab.

## 9. Required verification

- direct source/value updates remain denied;
- correction creates a replacement and does not alter the old snapshot;
- correction requires fresh acknowledgements;
- old correction signature is not executable by the application role;
- idempotent correction returns the same replacement;
- stale lifecycle versions fail without partial writes;
- two concurrent corrections produce exactly one successor;
- correction versus void has one atomic winner;
- document erasure while a Lab row is locked returns `HC409`, not deadlock;
- view/analyze see only active structured observations;
- view/analyze cannot read source OCR snapshots;
- void remains available after consent withdrawal;
- voided observations disappear from active reads;
- editors cannot permanently erase;
- owners can erase after consent withdrawal;
- full chains and originating Lab drafts are removed atomically;
- document erasure leaves no document-derived Lab observation or draft;
- document-state guard hides rows even when `deletion_pending` was set elsewhere;
- functions/triggers have exact ownership, configuration and grants;
- full migration, downgrade, PostgreSQL/RLS, backend and frontend CI pass.

## 10. Stop conditions

Do not merge or deploy if:

- a confirmed source/value field can be edited in place;
- a correction can bypass fresh acknowledgements;
- a correction loses original provenance;
- more than one active successor can replace the same observation;
- a non-owner can permanently erase;
- erasure leaves a broken lifecycle link or sole-provenance row;
- correction/document deletion can deadlock or create a post-erasure record;
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
