# HC-012e — Dashboard Profile Context

Status: `IN PROGRESS`  
Base: `main` at `579f4fe0aebde92adfee7747b3b36792de478936`  
Production: untouched

## Goal

Make profile and questionnaire state visible in the main dashboard so users understand how much context Health Compass is using and what can improve personalization.

## Product rules

- An incomplete profile must never block dashboard access.
- The dashboard must not imply that missing profile data invalidates already collected measurements.
- Missing context is described as reduced personalization, not as an error.
- The user sees the next useful profile action, not a generic demand to complete everything.
- Deferred sections remain respected and must not trigger aggressive reminders.
- Health claims and priorities remain based on persisted dashboard data, not on profile-completion percentage.

## Scope

1. Load derived profile completion together with the dashboard.
2. Show a compact context-coverage card on both empty and populated dashboards.
3. Display completion percentage and reviewed section count.
4. Link directly to the next incomplete questionnaire section.
5. Replace misleading fixed copy such as “достаточная база” when profile context is incomplete.
6. Keep dashboard metrics and questionnaire progress conceptually separate.
7. Add presentation and loading tests.

## Out of scope

- generating medical priorities from questionnaire answers;
- AI consultation implementation;
- changing dashboard snapshot schema;
- production rollout;
- merging HC-013 session management.
