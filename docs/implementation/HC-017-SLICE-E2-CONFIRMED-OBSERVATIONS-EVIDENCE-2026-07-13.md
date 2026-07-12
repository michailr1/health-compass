# HC-017 Slice E2 — Confirmed Observations Implementation Evidence

Date: 2026-07-13  
Source PR: `#65`  
Verified implementation head: `55f10d311d1f39262d557fa7b60cc07060ac5590`  
Merge commit: `1d61331194edf0f78b94a304d27ccf31dfa2a755`  
CI: `#491 — passed`  
Repository Alembic head: `0058`  
Deployment: `NOT DEPLOYED`

## Verdict

```text
IMPLEMENTED
MERGED
CI VERIFIED
NO UNRESOLVED CRITICAL OR HIGH REPOSITORY FINDING
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

## Implemented boundary

E2 adds a separate, explicit transaction that converts one current E1 `ready` draft into one immutable confirmed laboratory observation.

```text
ready source-preserving draft
→ explicit confirmation preview
→ mandatory acknowledgements
→ atomic current-source validation
→ immutable observation
→ immutable source snapshots
→ content-free audit
```

A ready draft remains non-clinical until this action succeeds.

## Database evidence

Migration `0058_add_confirmed_lab_observations.py` adds:

- `lab_observations`;
- `lab_observation_sources`;
- E1 transition `ready → confirmed`;
- `confirmed_at`, `confirmed_by_user_id` and `confirmed_observation_id` on drafts;
- one observation per source draft;
- profile-scoped confirmation idempotency;
- restrictive provenance foreign keys;
- audit action `lab.observation_confirmed`.

Both E2 tables use `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.

Application access:

- owner/edit/view/analyze may read confirmed active observations and immutable confirmed source snapshots according to profile visibility;
- only owner/edit may invoke confirmation;
- the application role has no direct INSERT, UPDATE or DELETE privilege on E2 tables;
- scanner, renderer, reconciler and OCR workers have no E2 table or confirmation-function access;
- PUBLIC EXECUTE is revoked.

## Atomic confirmation checks

`health_compass.app_confirm_lab_observation(...)` locks and validates:

- the current E1 draft and its exact timestamp;
- owner/edit permission;
- active owner health-data consent;
- accepted, non-erased source document and exact document timestamp;
- successful OCR run and finalized D2 review;
- exact review-finalization timestamp;
- current patient decision and exact decision timestamp;
- patient decision `match` or `not_present` only;
- extra profile-assignment acknowledgement for `not_present`;
- complete analyte and value provenance;
- current accepted/edited candidate versions;
- deterministic candidate row locks before immutable snapshot copying;
- idempotency-key and source-draft uniqueness.

Any failed check aborts observation, source snapshots, draft transition and audit as one transaction.

## Immutability and safety

Confirmed observation value/source fields have no application mutation route. E2 performs no:

- analyte normalization;
- unit conversion;
- reference-range interpretation;
- normal/abnormal decision;
- diagnosis;
- recommendation;
- medication or dose creation.

Corrections, voiding and permanent erasure are intentionally deferred to E3 and must use replacement/supersession or owner-only erasure transactions rather than in-place value editing.

## Threat-review hardening

Final review identified and closed:

1. replay ambiguity for the same draft under a different idempotency key;
2. concurrent source-draft confirmation conflict behavior;
3. a TOCTOU interval between candidate-version validation and immutable text copying.

The final implementation returns an existing observation only when source versions and acknowledgements match. Candidate rows are locked in deterministic order before version validation and snapshot insertion.

## CI evidence

Exact head `55f10d311d1f39262d557fa7b60cc07060ac5590` passed CI run `#491`:

- backend compile;
- Ruff;
- backend unit tests;
- frontend lint;
- frontend typecheck;
- frontend tests;
- frontend production build;
- migration boundary tests;
- full isolated `head → base → head` migration cycle;
- PostgreSQL integration and RLS matrix.

PostgreSQL coverage includes:

- ready draft creates zero confirmed observations;
- owner and editor confirmation;
- view/analyze confirmed-only visibility;
- outsider and no-context isolation;
- immutable source snapshot copying;
- direct mutation denial;
- PUBLIC and worker denial;
- stale candidate rejection;
- revoked-consent rejection with no partial rows;
- mandatory `not_present` acknowledgement;
- same-key replay;
- same-draft replay;
- different-draft idempotency conflict;
- concurrent confirmation producing exactly one observation;
- content-free audit.

## Production boundary

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

Migration `0058`, confirmed observations and the confirmation UI exist only in the repository. No HC-017 rollout is authorized.

## Next stage

The next allowed repository stage is E3:

- immutable correction through replacement and supersession;
- explicit voiding without in-place source/value mutation;
- owner-only permanent erasure;
- atomic source-document deletion propagation;
- proof that sole-provenance observations cannot be orphaned.
