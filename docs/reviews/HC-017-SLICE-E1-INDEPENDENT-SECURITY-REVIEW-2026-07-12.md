# HC-017 Slice E1 — Independent Security Review

Date: 2026-07-12  
Reviewed merge: `2ad0ca47d994472201c218b3e6af37145cbacdec`  
Verified implementation head: `419386e909207ab67921c008e210c059aba6658c`  
Source PR: `#61`  
CI: `#477 — passed`

## Verdict

```text
ACCEPT FOR REPOSITORY FOUNDATION
NO UNRESOLVED CRITICAL OR HIGH FINDING
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

E1 correctly creates owner/editor-only non-clinical drafts. It does not create confirmed observations or expose drafts to `view` or `analyze`.

## Reviewed scope

- migrations `0056–0057`;
- Lab draft and draft-source tables;
- RLS policies and grants;
- source-preserving value schema;
- current-context and consent gates;
- backend models, schemas, services and routes;
- frontend draft page and API helpers;
- unit, migration-cycle and PostgreSQL tests;
- audit/logging boundary.

## Confirmed strengths

### Access and privilege boundary

- Both E1 tables use ENABLE and FORCE RLS.
- Only owner/edit may read drafts and source manifests.
- View, analyze, outsider and no-context reads return no E1 rows.
- Runtime app has no direct INSERT, UPDATE or DELETE grants.
- Worker roles have no E1 mutation grants.
- Mutations use restricted `SECURITY DEFINER` functions.
- PUBLIC EXECUTE is revoked.

### Source preservation

- Source analyte and value wording remain explicit.
- Unit, range and date absence are represented explicitly.
- Parsed numeric/date fields do not overwrite source text.
- Numeric, text and qualitative value kinds are mutually exclusive.
- No canonical analyte mapping or unit conversion occurs.

### Provenance and concurrency

- Draft sources identify exact OCR candidates, roles, pages and candidate versions.
- Document, finalized OCR review and patient-decision versions are checked.
- Migration `0057` closes the initial gap where source/status mutations could otherwise outlive consent or current source context.
- Active consent is rechecked on every mutation.
- Ready transition requires current analyte/value provenance.

### Product safety

- `ready` remains non-clinical.
- E1 creates no confirmed-observation table or row.
- E1 creates no Clinical Context or body-measurement facts.
- Audit events are content-free.
- UI contains no confirmation action.

## Findings resolved before merge

| Finding | Severity before fix | Resolution |
|---|---:|---|
| Source/status mutations did not initially recheck current document/OCR/patient/consent context | High | forward migration `0057` introduced context-bound signatures and removed the shorter mutation path |
| Ready status could rely on stale source rows | High | `0057` revalidates candidate state and exact candidate timestamps |
| Post-creation consent revocation lacked an explicit regression | Medium | dedicated PostgreSQL test proves source/status mutations fail after revocation |
| Short-signature downgrade could reintroduce the bypass | High | downgrade restores only fail-closed compatibility stubs |
| Mutable response default in schema | Low | replaced with `default_factory` |

## Remaining findings and E2 blockers

### E1-R1 — Ready draft is not immutable clinical data

Severity: `EXPECTED / E2 BLOCKER`

A ready draft is intentionally owner/edit-only and may not be read by view/analyze or used by analytics/AI. E2 must copy an immutable snapshot in one confirmation transaction.

### E1-R2 — E2 must revalidate all source context

Severity: `HIGH IF OMITTED / E2 BLOCKER`

Confirmation must recheck:

- draft timestamp and ready status;
- current document timestamp/state;
- finalized D2 review timestamp;
- patient-decision timestamp/value;
- exact candidate versions;
- active consent;
- owner/edit permission.

E1 validation cannot be treated as permanent authorization.

### E1-R3 — `not_present` needs stronger acknowledgement

Severity: `HIGH IF OMITTED / E2 BLOCKER`

E1 allows a draft when the source does not identify the patient. E2 must require an additional explicit assignment acknowledgement before creating a confirmed observation.

### E1-R4 — Idempotency and duplicate prevention do not yet exist

Severity: `HIGH IF OMITTED / E2 BLOCKER`

E2 requires:

- one observation per draft;
- profile-scoped idempotency key;
- safe replay behavior;
- concurrent-confirmation tests;
- no silent merging of duplicate-looking observations.

### E1-R5 — Confirmed-data immutability is not implemented

Severity: `EXPECTED / E2 BLOCKER`

E2 must add immutable observation/source snapshots with no direct UPDATE or DELETE grants. Correction and void belong to E3.

### E1-R6 — Document deletion must not orphan future observations

Severity: `HIGH IF OMITTED / E2/E3 BLOCKER`

Until E3 defines atomic erasure, confirmed observations should restrict source deletion rather than become unsupported.

### E1-R7 — Source text duplication is sensitive

Severity: `MEDIUM / CONTROLLED`

E1 intentionally stores source-preserving medical text. Current controls are appropriate:

- owner/edit-only RLS;
- no content in audit/logs;
- no view/analyze access;
- document-linked deletion.

E2 source snapshots must apply equally strict protection while allowing only confirmed reads.

## Production decision

E1 remains repository-only. The following are prohibited:

- applying migrations `0050–0057` as an isolated production rollout;
- enabling document upload;
- treating E1 drafts as clinical facts;
- exposing E1 drafts to view/analyze;
- starting metric dynamics from E1 drafts.

## Acceptance criteria for E2 review

E2 must prove:

- separate explicit confirmation endpoint and UI;
- owner/edit-only confirmation;
- no worker confirmation;
- immutable observation and source snapshots;
- current context and consent validation;
- `not_present` assignment acknowledgement;
- atomic draft consumption and observation creation;
- exact replay/idempotency behavior;
- confirmed-only read matrix;
- no direct mutation grants;
- no medical values in ordinary logs/audit;
- deletion cannot orphan confirmed provenance;
- full migration cycle and negative PostgreSQL tests.
