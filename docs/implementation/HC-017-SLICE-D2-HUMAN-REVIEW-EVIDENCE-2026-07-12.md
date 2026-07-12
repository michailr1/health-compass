# HC-017 Slice D2 — Human OCR Review and Patient Matching Evidence

Status: `IMPLEMENTED / MERGED / CI VERIFIED / NOT DEPLOYED`  
Date: 2026-07-12  
Source PR: `#58`  
Verified implementation head: `4ecae1fb0816803b2d858db1f5016bce589544d5`  
Merge commit: `f67a1128e29a1c62e8a3b27dd20c973df82947ad`  
CI run: `#454`  
Repository Alembic head: `0055`  
Production application: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`

## Verdict

```text
MERGED INTO REPOSITORY
NOT DEPLOYED
OCR REVIEW IS TRANSCRIPTION ONLY
```

D2 adds explicit human review and patient matching over D1 OCR candidates. It does not create Clinical Context, body measurements, laboratory observations, diagnoses, recommendations or medication data.

## Implemented database boundary

Migration `0055` adds:

- `document_ocr_patient_decisions`;
- FORCE RLS for patient decisions;
- owner/edit-only patient-decision reads;
- review metadata on `document_ocr_runs`;
- `reviewed` document OCR state;
- stricter candidate-state constraints;
- content-free review audit actions;
- app-only candidate review, patient decision and finalization functions.

The runtime application role has no direct INSERT, UPDATE or DELETE grants on:

- `document_ocr_candidates`;
- `document_ocr_patient_decisions`;
- `document_ocr_runs`.

All mutations execute through hardened SECURITY DEFINER functions owned by `health_compass_rls_definer`, with fixed empty search path, `row_security=off`, revoked PUBLIC EXECUTE and exact app-role grants.

## Review actions

Supported candidate actions:

```text
accept
edit
reject
defer
```

Rules:

- owner/edit only;
- active health-data consent of the profile owner;
- required `expected_updated_at` optimistic concurrency;
- accepted text equals original OCR text;
- edited text is an explicit bounded replacement;
- rejected/deferred candidates have no reviewed text;
- review note is optional and bounded;
- decisions remain changeable until finalization;
- finalized reviews are read-only.

## Explicit patient decision

States:

```text
unknown
match
mismatch
not_present
```

The decision is always explicit. OCR text is never used to infer the patient automatically.

Finalization is blocked when:

- decision is missing or `unknown`;
- decision is `mismatch`;
- decision timestamp is stale.

## Manifest-bound finalization

Finalization requires:

- current accepted document and current successful OCR run;
- owner/edit authorization;
- active health-data consent;
- exact current document timestamp;
- exact candidate ID/timestamp manifest;
- exact patient-decision timestamp;
- no `needs_review` candidate;
- no deferred candidate;
- patient decision `match` or `not_present`.

A repeated finalization with the identical original preconditions returns success without creating a second audit event.

Finalization changes only OCR review state:

```text
document.ocr_status = reviewed
run.review_status = finalized
```

It creates no clinical or Labs rows.

## API and UI

Implemented API:

```text
GET   /profiles/{profile_id}/documents/{document_id}/ocr/review
PATCH /profiles/{profile_id}/documents/{document_id}/ocr/candidates/{candidate_id}
PUT   /profiles/{profile_id}/documents/{document_id}/ocr/patient-match
POST  /profiles/{profile_id}/documents/{document_id}/ocr/finalize
```

Implemented UI:

```text
/app/documents/{document_id}/review
```

The UI provides:

- original OCR text;
- confidence and page metadata;
- explicit accept/edit/reject/defer actions;
- revisable decisions before finalization;
- explicit patient match/mismatch/not-present decision;
- stale/conflict-safe messages;
- finalization only when all preconditions are satisfied;
- read-only finalized review.

No raw PDF, safe-page image, TSV, object key or worker output is delivered.

## Verification

Exact reviewed head:

```text
4ecae1fb0816803b2d858db1f5016bce589544d5
```

CI run `#454` passed:

- backend compile;
- Ruff;
- backend unit tests;
- frontend lint;
- TypeScript typecheck;
- frontend tests;
- production frontend build;
- migration `0055` boundary;
- isolated full `head → base → head` migration cycle;
- PostgreSQL D2 RLS and state-flow integration.

PostgreSQL tests prove:

- app role cannot directly update OCR candidates;
- owner/editor can read and review;
- view/analyze/outsider see no candidate text;
- stale candidate updates fail without mutation;
- revoked consent blocks review;
- mismatch blocks finalization;
- deferred candidates block finalization;
- patient decision can be updated explicitly;
- identical finalization is idempotent;
- audit payloads contain no OCR or reviewed text;
- zero conditions, allergies, medications, supplements or body measurements are created.

## Downgrade safety

Migration `0055` refuses downgrade while any human-review data exists:

- patient decisions;
- non-default run review status;
- candidate decisions other than `needs_review`.

This prevents silent loss of reviewed text, patient decisions or finalization provenance.

## Explicitly not implemented

- analyte/value/unit extraction;
- Clinical Context creation;
- confirmed Labs observations;
- metric dynamics;
- safe-page preview delivery;
- production worker/systemd provisioning;
- production document upload;
- production migration or rollout.

## Next stage

```text
HC-017 Slice E — Confirmed Labs Core
```

Slice E must remain a separate explicit confirmation boundary. It may consume only finalized D2 transcription and must preserve source wording, value, unit, reference range and document/page provenance. It must not diagnose, interpret or normalize silently.

## Production boundary

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

No VPS rollout task is authorized by the D2 merge.