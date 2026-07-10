# HC-012b Slice C — Clarifying Questions Audit

Status: `IN PROGRESS`  
Base: `main` at `0c060556b4f82533f36759b67f0e5d5f0b1c361b`  
Production: untouched

## Purpose

Add short, observable-fact questions after a user selects or enters a Clinical Context item.

The UI must not require medical terminology or force classification such as “chronic” versus “temporary”.

## Canonical question sets

### Conditions and symptoms

- How long ago: `recent`, `long_ago`, `unknown`, optional date/period.
- Present now: `yes`, `resolved`, `recurring`, `unknown`.
- A symptom must never be automatically converted into a diagnosis.

### Allergies and intolerances

- Optional reaction text.
- Optional severity: `mild`, `moderate`, `severe`, `unknown`.
- Current relevance: `yes`, `no`, `unknown`.
- No automatic inference of anaphylaxis or severity from free text.

### Medications

- Current use: `yes`, `no`, `unknown`.
- Optional start date or approximate period.
- Optional dose and unit.
- Optional frequency.
- Optional reason.
- Course lifecycle remains explicit and historical; restarting creates a new course.

### Supplements

- Current use: `yes`, `no`, `unknown`.
- Optional dose and unit.
- Optional frequency.
- Optional start date or approximate period.

## Implementation constraints

- Questions appear only after a chip exists.
- Optional answers may be skipped.
- `Не знаю` is a first-class answer.
- Existing free-text and canonical provenance must remain intact.
- Existing create APIs should be extended rather than duplicated.
- No AI classification, OCR, diagnosis inference, or production rollout.

## Initial technical plan

1. Audit existing schema fields against the canonical question sets.
2. Reuse existing fields where semantics match.
3. Add only missing structured fields in the next migration.
4. Add a reusable progressive question panel in frontend.
5. Preserve one transaction per record creation.
6. Add backend validation, frontend tests, migration/RLS tests.
