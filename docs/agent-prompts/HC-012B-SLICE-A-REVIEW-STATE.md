# Coding Prompt — HC-012b Slice A: Review State Foundation

## Context

Repository: `michailr1/health-compass`  
Base branch: `main`  
Canonical UX: `docs/CLINICAL-CONTEXT-INPUT-UX.md`  
Gap plan: `docs/HC-012B-DATA-MODEL-API-GAP-PLAN.md`  
Current production migration head at planning time: `0041`

## Safety constraints

- Do not deploy to production.
- Do not change `/opt/health-compass/current-subdomain`.
- Do not edit production files directly.
- Work only in a new feature branch from current `main`.
- Re-check actual Alembic head before naming the migration.
- Every new or altered user-data table must preserve ENABLE/FORCE RLS.
- App role must not receive DELETE.
- Preserve one transaction per HTTP request and existing RLS context handling.
- Do not add AI, OCR, dictionaries, typeahead or course-lifecycle changes in this slice.

## Goal

Implement first-class section review states for Clinical Context:

- `unknown`;
- `deferred`;
- `confirmed_none`;
- derived `has_entries`.

Add the neutral `Не сейчас` UX and reusable `WhyWeAsk` component without pressure UX.

## Required audit before coding

1. Identify the exact migration and schema for the current clinical section review table.
2. Identify current SQLAlchemy models, Pydantic schemas, services and routes used by Clinical Context review state.
3. Identify frontend query/mutation code and `ClinicalContextSection` state mapping.
4. Confirm whether current storage is boolean `confirmed_empty` or another representation.
5. Report the exact file-level implementation plan before changing code.

## Backend behavior

### Stored state

Store only:

- `unknown`;
- `deferred`;
- `confirmed_none`.

Do not store `has_entries` as an independent mutable flag.

### Effective state

The API must compute:

1. `has_entries` when the section has at least one relevant clinical record, including history according to the canonical plan;
2. otherwise the stored review state;
3. otherwise `unknown`.

Return at minimum:

```json
{
  "review_state": "unknown",
  "effective_state": "has_entries",
  "active_count": 1,
  "history_count": 2,
  "reviewed_at": "..."
}
```

### Transitions

Support:

- unknown → deferred;
- unknown → confirmed_none;
- deferred → unknown;
- deferred → confirmed_none;
- confirmed_none → unknown.

Rules:

- client cannot set `has_entries` directly;
- confirmed_none is rejected with `409 section_has_entries` if relevant records exist;
- adding the first record clears stored `deferred` or `confirmed_none` in the same transaction and writes audit;
- voiding the last record must not automatically create confirmed_none;
- no physical DELETE of review rows through app role.

### Endpoint

Use or adapt the existing review endpoint. Preferred contract:

```text
PATCH /profiles/{profile_id}/clinical-context/sections/{section}/review
```

Payload:

```json
{
  "review_state": "deferred",
  "version": 3
}
```

Use optimistic concurrency with current project conventions. Return `409` on stale update.

### Migration

If current schema uses `confirmed_empty boolean`:

- backfill `true` → `confirmed_none`;
- backfill `false`/NULL → `unknown`;
- keep backward compatibility during code transition;
- remove obsolete boolean only when backend and frontend no longer depend on it;
- preserve existing data and audit history.

Migration must include:

- CHECK constraints;
- indexes/unique constraint as required;
- ENABLE/FORCE RLS verification;
- grants without DELETE;
- downgrade that safely restores the previous representation where possible.

### Audit events

Add or map to existing event taxonomy:

- `clinical_section.review_deferred`;
- `clinical_section.review_unknown`;
- `clinical_section.confirmed_none`;
- `clinical_section.confirmed_none_cleared`.

Audit remains append-only.

## Frontend behavior

For each Clinical Context section expose:

- `Добавить запись`;
- section-specific `Подтвердить, что записей нет`;
- `Не сейчас`;
- `Зачем это нужно`.

### `Не сейчас`

- persists `deferred` on backend;
- uses neutral styling;
- does not show warning/error;
- does not reduce a score;
- does not block dashboard, AI, reports or recommendations;
- can be reversed later.

### WhyWeAsk component

Create a reusable component used by all four sections.

Canonical meaning:

> Эти сведения помогают Health Compass учитывать ваш контекст при анализе данных, отчётах и рекомендациях. Раздел можно не заполнять: все основные функции продолжат работать, но ответы могут быть менее персонализированными.

Requirements:

- collapsed by default on mobile;
- keyboard accessible;
- no percentages or “complete your profile” language;
- no medical-pressure wording;
- visible labels and correct ARIA semantics.

### Status labels

Map effective states to neutral labels:

- unknown → `Пока не заполнено`;
- deferred → `Отложено` or `Можно заполнить позже`;
- confirmed_none → explicit confirmed-empty label;
- has_entries → count-based label.

Color must not be the only state indicator.

## Required tests

### Database/backend

- migration up/down;
- existing confirmed-empty rows backfill correctly;
- untouched section = unknown;
- deferred persists;
- confirmed_none only when no records exist;
- first record clears deferred/confirmed_none;
- voiding last record does not imply confirmed_none;
- concurrent review update returns 409;
- owner/editor can change state;
- viewer/analyze read-only;
- outsider gets SQL 0 rows and API 404;
- no-context fail-closed;
- warm-row regression has no 54001;
- app role has no DELETE.

### Frontend

- all four states render correctly;
- `Не сейчас` mutation and reversal;
- WhyWeAsk keyboard and mobile behavior;
- no completion percentage or blocking copy;
- touch targets at least 44×44 CSS px;
- screen-reader status text;
- backend error does not incorrectly change local state.

## Out of scope

Do not implement in Slice A:

- typeahead;
- chips;
- dictionaries;
- symptom/diagnosis fields;
- approximate onset/current pattern;
- medication course guards;
- AI/OCR normalization;
- production rollout.

## Acceptance criteria

1. The four effective states are distinguishable and correctly persisted/derived.
2. `deferred` is a backend state, not frontend-only.
3. `has_entries` cannot drift from actual records.
4. Confirmed-none cannot coexist with existing records.
5. First record clears incompatible review state atomically.
6. `Не сейчас` is neutral and reversible.
7. WhyWeAsk is reusable and accessible.
8. RLS, FORCE RLS, audit and no-DELETE invariants remain intact.
9. Backend and frontend CI are green.
10. No production deployment or rollout is performed.

## Final report format

Return:

1. branch name and HEAD;
2. exact audited current schema/routes/files;
3. migrations created;
4. files changed;
5. data backfill behavior;
6. RLS and privilege verification;
7. tests run and results;
8. known limitations;
9. confirmation that production was not changed.
