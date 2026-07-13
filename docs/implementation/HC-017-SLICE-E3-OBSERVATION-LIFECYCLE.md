# HC-017 E3 — Correction, Void and Owner-only Erasure

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`  
Migrations: `0059–0062`  
PR: `#70`  
Verified head: `0b7b72b87c0f046385eb12849dc37cab8d558c02`  
Merge: `c7dcae4da3860f6f73224f639be78424c6f3fa63`  
CI: `#544 / success`

Production remains application `fb1e7a2f...`, Alembic `0058`, upload disabled and workers stopped.

## 1. Purpose

Add an explicit lifecycle for confirmed laboratory observations without ever editing confirmed source/value fields in place.

E3 distinguishes three user intentions:

1. **Correct** — create a new immutable replacement snapshot.
2. **Void** — remove an observation from active use while preserving provenance and a bounded reason.
3. **Delete permanently** — owner-only irreversible removal of the complete connected correction chain and its value-bearing provenance.

## 2. Immutable replacement contract

Correction never updates these fields on an existing confirmed observation:

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

The older acknowledgement-free correction SQL signature remains in migration history but is not executable by `health_compass_app`.

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

Erasing one member removes the whole chain so no dangling predecessor/successor or unsupported provenance remains.

## 5. Document-linked Lab erasure

The owner-only document Lab erasure function:

- requires explicit confirmation and current document `updated_at`;
- marks the document `deletion_pending` immediately;
- deletes all Lab observations, source snapshots, drafts and draft sources for that document atomically;
- leaves external encrypted-object deletion to the separate document-storage lifecycle.

Migration `0060` adds an independent `SECURITY DEFINER` document-state guard to every Lab read policy. Lab rows are hidden whenever their source document is `deletion_pending` or erased, even if another application path changed the document.

Migration `0061` adds a protected transition trigger. Before a document enters deletion/erasure, related Lab drafts and observations are locked in deterministic order with `NOWAIT`. Concurrent correction/confirmation returns controlled `HC409`; it cannot create a post-erasure orphan or PostgreSQL deadlock.

This contract does not claim that the encrypted source object has already been physically erased.

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

E3 fixes an over-broad E2 source policy: `view` and `analyze` retain active structured-observation access but no longer receive OCR text snapshots.

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

Migration `0062` extends the closed audit action vocabulary for hardened correction/erasure action names without permitting arbitrary actions.

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

## 9. Verification evidence

Exact-head CI #544 passed:

- backend compile, Ruff and unit tests;
- frontend lint, typecheck, tests and build;
- migration boundary tests;
- full `head → base → head` migration cycle;
- PostgreSQL integration and RLS tests.

Negative coverage proves:

- direct source/value updates remain denied;
- correction creates a replacement and does not alter the old snapshot;
- correction requires fresh acknowledgements;
- the old correction signature is not executable by the app role;
- idempotent correction returns the same replacement;
- stale lifecycle versions fail without partial writes;
- two concurrent corrections produce exactly one successor;
- correction versus void has one atomic winner;
- document erasure while a Lab row is locked returns `HC409`, not deadlock;
- view/analyze see only active structured observations;
- view/analyze cannot read source OCR snapshots;
- void remains available after consent withdrawal;
- editors cannot permanently erase;
- owners can erase after consent withdrawal;
- full chains and originating Lab drafts are removed atomically;
- document-state guard hides rows even when `deletion_pending` was set elsewhere;
- functions/triggers have exact ownership, configuration and grants;
- frontend cancellation sends no correction request.

Independent review verdict:

```text
ACCEPT / NO UNRESOLVED CRITICAL OR HIGH FINDING
```

Canonical merge evidence:

```text
docs/changes/2026-07-13-hc-017-e3-merged.md
```

## 10. Stop conditions

Do not deploy if:

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
PRODUCTION APPLICATION=fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
PRODUCTION ALEMBIC=0058
E3 MERGED / CI VERIFIED / NOT DEPLOYED
```

Any E3 production rollout requires a separate backup-first exact-SHA decision and VPS deployment instruction.
