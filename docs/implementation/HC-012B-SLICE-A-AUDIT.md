# HC-012b Slice A — Implementation Audit

Status: `IMPLEMENTED — CI IN PROGRESS`  
Base: `main` at `eb7d6ab4e8f2c85c0f58cd4e087ab19462e907de`  
Production: untouched

## Implemented schema

Migration `0042_add_clinical_review_states.py` adds:

```text
review_state = unknown | deferred | confirmed_none
```

Backfill:

- `confirmed_empty=true` → `confirmed_none`;
- `confirmed_empty=false` → `unknown`.

The legacy `confirmed_empty` column is temporarily preserved and synchronized by a database trigger so existing SQL tests and older clients remain compatible during the transition.

Security invariants remain:

- UNIQUE `(profile_id, section)`;
- ENABLE RLS;
- FORCE RLS;
- view access through `app_can_view_profile`;
- writes through `app_can_edit_profile` and current actor;
- app role without DELETE.

## Implemented API

Primary endpoints:

- `GET /profiles/{profile_id}/clinical-context/state`;
- `PATCH /profiles/{profile_id}/clinical-context/sections/{section}/review`.

Compatibility endpoints remain functional:

- `GET /profiles/{profile_id}/clinical-context`;
- `POST /profiles/{profile_id}/clinical-context/review`;
- legacy `confirmed_empty` request payloads.

The API stores only:

- `unknown`;
- `deferred`;
- `confirmed_none`.

`has_entries` is derived from clinical history and cannot be submitted by a client.

Optimistic concurrency uses `expected_updated_at`; stale changes return `409 review_state_conflict`.

`confirmed_none` returns `409 section_has_entries` when records/history exist.

## Implemented record interaction

Creating the first record in a section atomically clears incompatible `deferred` or `confirmed_none` state in the same request transaction.

Voiding the final record does not automatically create `confirmed_none`.

## Implemented frontend

`ClinicalContextSection` now provides:

- `Добавить запись`;
- explicit confirmed-none action;
- neutral `Не сейчас`;
- reversible `Изменить решение`;
- reusable `WhyWeAsk` disclosure;
- status labels for unknown, deferred, confirmed-none and has-entries;
- mobile-sized controls and non-blocking copy.

The interface explicitly states that all core functions remain available without completing Clinical Context, with potentially lower personalization.

## Audit events

Migration `0042` permits:

- `clinical_section.review_deferred`;
- `clinical_section.review_unknown`;
- `clinical_section.confirmed_none`;
- `clinical_section.confirmed_none_cleared`.

Existing `clinical_context.reviewed` history remains valid.

## Tests

Added/updated coverage for:

- allowed stored states;
- rejection of client-submitted `has_entries`;
- legacy request compatibility;
- frontend status mapping;
- migration head `0042`;
- no effective DELETE privilege;
- full migration/RLS cycle.

CI history:

- run `#237`: frontend and PostgreSQL/RLS passed; one legacy backend property assertion failed;
- compatibility property added;
- run `#239`: current validation run.

## Non-negotiable invariants

- `has_entries` cannot drift from clinical records;
- `deferred` is persisted on backend;
- confirmed-none cannot coexist with history;
- no physical DELETE;
- RLS/FORCE RLS preserved;
- outsider API remains 404;
- production is not deployed from this branch.
