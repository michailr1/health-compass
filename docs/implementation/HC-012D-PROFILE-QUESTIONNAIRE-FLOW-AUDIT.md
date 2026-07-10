# HC-012d — Profile Questionnaire Flow

Status: `IMPLEMENTED — CI GREEN`  
Base: `main` at `61f61a1051c397966b4dae508eb12b7a70e14078`  
Production: untouched

## Goal

Turn the existing profile and Clinical Context capabilities into one coherent user flow rather than a set of isolated controls.

## Implemented scope

1. Profile completion progress derived from real persisted state.
2. Clear ordering of questionnaire sections.
3. Resume from the next incomplete section.
4. Editing existing Clinical Context records.
5. Viewing active records and history separately.
6. Ending medication and supplement courses without deleting history.
7. Re-starting a course as a new record rather than mutating old history.
8. Clear explanation that incomplete data reduces personalization but does not block the product.

## Product rules

- Completion is informative, not coercive.
- The product continues to work with an incomplete profile.
- `Не сейчас` remains a valid decision.
- `Подтверждено отсутствие` counts as reviewed.
- A section with records counts as reviewed even if optional fields are missing.
- Profile completion never implies medical completeness or diagnostic certainty.
- Editing never physically deletes medical history.
- Ending a medication/supplement course sets status `completed` and an end date.
- Restarting a course creates a new record through the normal add flow.

## Questionnaire order

1. Basic profile data.
2. Conditions and symptoms.
3. Allergies and intolerances.
4. Medications.
5. Supplements.

## Completion model

`GET /profiles/{profile_id}/completion` returns:

- completed and total section counts;
- progress percentage;
- next incomplete section;
- ordered section state;
- concrete missing fields for basic profile data;
- navigation anchors for resume flow.

The summary is derived from profile readiness, Clinical Context review state and record history. No duplicate progress table is introduced.

## Frontend

The profile route now renders:

- a non-blocking completion card;
- percentage and completed-section count;
- `complete`, `deferred`, and `incomplete` states;
- direct links to questionnaire sections;
- a resume button for the next incomplete section;
- active Clinical Context records under `Сейчас`;
- historical records in a collapsible `История` group;
- edit controls using the existing optimistic-concurrency PATCH API;
- `Завершить курс` for active medications and supplements.

Edits invalidate both Clinical Context and completion-summary queries.

## Validation

CI run `#312` passed:

- frontend lint, tests and build;
- backend compile, Ruff and unit tests;
- PostgreSQL migration and RLS cycle.

Regression coverage includes active/history classification and existing profile/Clinical Context security checks.

## Out of scope

- AI-generated questions;
- OCR/document extraction;
- automatic medical classification;
- production rollout;
- merging HC-013 session management.
