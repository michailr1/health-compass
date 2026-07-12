# HC-017 Slice E1 — Source-preserving Lab Drafts Evidence

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`  
Date: 2026-07-12  
Source PR: `#61`  
Verified head: `419386e909207ab67921c008e210c059aba6658c`  
Merge commit: `2ad0ca47d994472201c218b3e6af37145cbacdec`  
CI run: `#477`  
Repository Alembic head: `0057`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## Verdict

```text
MERGED INTO REPOSITORY MAIN
CI VERIFIED
NOT DEPLOYED
NO CONFIRMED LAB OBSERVATIONS
```

E1 introduces source-preserving structured drafts only. A draft marked `ready` remains non-clinical and is not available to analytics, `analyze`, AI interpretation or metric dynamics.

## Implemented database boundary

Migrations:

```text
0056 — source-preserving Lab draft tables and restricted functions
0057 — current document/OCR/patient/consent checks on every mutation
```

Tables:

```text
health_compass.lab_observation_drafts
health_compass.lab_observation_draft_sources
```

Both tables use:

- `ENABLE ROW LEVEL SECURITY`;
- `FORCE ROW LEVEL SECURITY`;
- owner/edit-only read visibility;
- no direct runtime INSERT, UPDATE or DELETE grants.

All mutations use narrow `SECURITY DEFINER` functions owned by `health_compass_rls_definer`, with fixed empty `search_path`, `row_security=off`, revoked PUBLIC EXECUTE and app-only execution.

## Source-preserving data contract

E1 stores source text separately from parsed representations:

- analyte wording;
- value wording;
- unit or explicit absence;
- reference range or explicit absence;
- source observation date/time text or explicit unknown;
- optional parsed date/datetime;
- specimen, flag and comment text;
- explicit numeric, text or qualitative value kind.

E1 does not silently:

- canonicalize analytes;
- convert units;
- interpret reference ranges;
- classify normal/abnormal;
- diagnose or recommend treatment.

## Provenance and concurrency

Every source manifest identifies exact reviewed OCR candidates and source roles.

Mutations require current versions of:

- the Lab draft;
- source document;
- finalized OCR review;
- patient decision;
- selected OCR candidates.

Allowed patient decisions:

```text
match
not_present
```

`unknown` and `mismatch` cannot create or advance a Lab draft.

Active health-data consent is checked during:

- draft creation;
- draft field updates;
- source-manifest replacement;
- ready/rejected status transitions.

The post-creation consent-revocation regression is covered by PostgreSQL integration tests.

## Access matrix

| Action | owner | edit | view | analyze | outsider |
|---|---:|---:|---:|---:|---:|
| Read Lab drafts | yes | yes | no | no | no |
| Create/update draft | yes | yes | no | no | no |
| Replace source manifest | yes | yes | no | no | no |
| Mark ready/rejected | yes | yes | no | no | no |
| Confirm observation | not implemented | not implemented | no | no | no |

Worker roles have no E1 mutation functions or direct table grants.

## API and UI

Implemented API:

```text
GET   /profiles/{profile_id}/documents/{document_id}/lab-drafts/context
GET   /profiles/{profile_id}/documents/{document_id}/lab-drafts
GET   /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}
POST  /profiles/{profile_id}/documents/{document_id}/lab-drafts
PATCH /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}
PUT   /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/sources
POST  /profiles/{profile_id}/documents/{document_id}/lab-drafts/{draft_id}/status
```

Frontend route:

```text
/app/documents/{document_id}/labs
```

The UI can create a source-preserving draft, select reviewed OCR fragments for analyte/value provenance and mark a draft ready for a later, separate confirmation step. It cannot create a confirmed observation.

## Verification evidence

Exact head `419386e9...` passed CI `#477`:

- Python compile;
- Ruff;
- backend unit tests;
- frontend lint;
- TypeScript typecheck;
- frontend tests and build;
- migration boundary tests;
- full `head → base → head` cycle;
- PostgreSQL RLS, privilege, provenance and stale-version tests;
- post-creation consent-revocation tests;
- proof that no `lab_observations` table or confirmed facts are created.

## Production boundary

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

No VPS deployment task is authorized for E1.

## Next stage

```text
HC-017 Slice E2 — Explicit Confirmation and Confirmed Observations
```

E2 requires a separate architecture/security review and implementation PR. It must create immutable observations only through an explicit, atomic, idempotent confirmation transaction with current provenance and acknowledgements.
