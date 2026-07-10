# HC-012e — Dashboard Profile Context

Status: `IMPLEMENTED — CI GREEN`  
Base: `main` at `579f4fe0aebde92adfee7747b3b36792de478936`  
Production: untouched

## Goal

Make profile and questionnaire state visible in the main dashboard so users understand how much context Health Compass is using and what can improve personalization.

## Implemented product rules

- An incomplete profile never blocks dashboard access.
- Missing profile data does not invalidate already collected measurements.
- Missing context is described as reduced personalization, not as an error.
- The user sees the next useful profile action instead of a generic demand to complete everything.
- Deferred sections remain respected and do not trigger urgent reminders.
- Health metrics and priorities remain based on persisted dashboard snapshots, not on completion percentage.
- A failure of the completion endpoint does not make the dashboard unavailable.

## Implemented scope

1. Dashboard loading now requests the derived profile-completion summary alongside the dashboard snapshot.
2. A compact `DashboardProfileContextCard` is shown on both empty and populated dashboards.
3. The card displays completion percentage and reviewed section count.
4. The next action links directly to the corresponding questionnaire anchor.
5. Fixed copy implying a universally “sufficient base” was replaced with context-aware wording.
6. Profile completion and health metrics are presented as separate concepts.
7. Shared `ProfileCompletionSummary` types are reused by the profile and dashboard screens.
8. Empty-dashboard copy now separates source/measurement onboarding from optional questionnaire completion.

## Resilience

`loadDashboard()` treats the completion summary as supplemental:

- dashboard snapshot 404 still produces a valid empty dashboard with profile context;
- completion API failures resolve to `completion: null`;
- unexpected dashboard API failures remain visible and are not suppressed.

## Validation

CI run `#322` passed:

- frontend lint, tests and build;
- backend compile, Ruff and unit tests;
- PostgreSQL migration and RLS cycle.

Frontend regression coverage includes:

- missing dashboard snapshot with available completion summary;
- completion API failure with a valid dashboard snapshot;
- propagation of unexpected dashboard failures;
- neutral messaging for empty, partial and reviewed profile context.

## Out of scope

- generating medical priorities from questionnaire answers;
- AI consultation implementation;
- changing dashboard snapshot schema;
- production rollout;
- merging HC-013 session management.
