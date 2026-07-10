# HC-012d — Profile Questionnaire Flow

Status: `IN PROGRESS`  
Base: `main` at `61f61a1051c397966b4dae508eb12b7a70e14078`  
Production: untouched

## Goal

Turn the existing profile and Clinical Context capabilities into one coherent user flow rather than a set of isolated controls.

## Scope

1. Profile completion progress derived from real persisted state.
2. Clear ordering of questionnaire sections.
3. Resume from the next incomplete section.
4. Editing existing Clinical Context records.
5. Viewing active records and history separately.
6. Ending medication and supplement courses without deleting history.
7. Re-starting a course as a new record rather than mutating old history.
8. Clear connection between profile completeness and the quality of dashboards, reports and AI consultations.

## Product rules

- Completion is informative, not coercive.
- The product continues to work with an incomplete profile.
- `Не сейчас` remains a valid decision.
- `Подтверждено отсутствие` counts as reviewed.
- A section with records counts as reviewed even if some optional fields are missing.
- Profile completion must never imply medical completeness or diagnostic certainty.
- Editing never physically deletes medical history.
- Ending a medication/supplement course sets historical status and end date.
- Restarting a course creates a new course record.

## Proposed questionnaire order

1. Basic profile data.
2. Conditions and symptoms.
3. Allergies and intolerances.
4. Medications.
5. Supplements.

## Proposed completion model

Each section exposes:

- `state`: `complete | deferred | incomplete`;
- `required_for_precision`: boolean;
- `missing_fields`: list of concrete user-facing gaps;
- `next_action`: route or section anchor;

Overall progress is derived from reviewed sections, not from raw field counts alone.

## First implementation slice

- backend profile-completion summary endpoint;
- frontend progress card and resume action;
- edit actions for existing Clinical Context records;
- active/history split;
- medication and supplement course completion;
- regression tests and RLS coverage.

## Out of scope

- AI-generated questions;
- OCR/document extraction;
- automatic medical classification;
- production rollout;
- merging HC-013 session management.
