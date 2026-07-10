# HC-012c — Contextual Intake Audit

Status: `IN PROGRESS`  
Base: `main` at `1b0bbe8bd63b180de9f73d6ecda5a85a773058c5`  
Production: untouched

## Product goal

When Health Compass encounters a relevant health fact during an analysis or conversation, the user must be able to choose one of four explicit outcomes:

1. `save_to_profile` — save as a durable profile fact;
2. `analysis_only` — use only for the current analysis;
3. `defer` — not now;
4. `explain` — show why the information is useful without committing any data.

No option may be preselected. The user must understand the persistence boundary before choosing.

## Core invariants

- `analysis_only` data is never written to durable Clinical Context tables.
- `defer` records only the decision to defer, not the proposed health fact.
- `explain` is a UI action and must not be treated as consent or persistence.
- `save_to_profile` reuses the same validated create services and audit/RLS controls as normal Clinical Context entry.
- outsider access remains 404 through profile visibility rules.
- one request equals one transaction.
- no AI diagnosis inference.

## Proposed backend model

Table: `profile_intake_decisions`

- `id uuid`;
- `profile_id uuid`;
- `prompt_key varchar(128)`;
- `context_type varchar(64)`;
- `decision varchar(32)`;
- `proposed_section varchar(32) nullable`;
- `proposed_display_text varchar(255) nullable`;
- `analysis_scope_id uuid nullable`;
- `decided_by_user_id uuid`;
- `decided_at timestamptz`;
- `request_id varchar(128) nullable`.

Stored decisions:

- `save_to_profile`;
- `analysis_only`;
- `defer`.

`explain` is intentionally not stored.

The table stores only minimal prompt metadata. For `analysis_only`, the actual transient payload belongs to the analysis request/session boundary and must not be persisted here.

## Proposed API

```text
POST /profiles/{profile_id}/contextual-intake/decisions
```

Request:

```json
{
  "prompt_key": "analysis.medication.detected",
  "context_type": "clinical_context",
  "decision": "analysis_only",
  "proposed_section": "medications",
  "proposed_display_text": "Метформин",
  "analysis_scope_id": "uuid"
}
```

For `save_to_profile`, the request includes a validated section payload and the service delegates to existing Clinical Context creation.

## Frontend component

`IntakePromptCard`

- concise fact preview;
- `Сохранить в профиль`;
- `Только для этого анализа`;
- `Не сейчас`;
- reusable `Зачем это нужно` disclosure;
- neutral, non-blocking copy;
- mobile-first controls;
- explicit persistence label for every action.

## First implementation slice

1. Migration and RLS for decision audit.
2. Backend decision schema/service/API.
3. `IntakePromptCard` as reusable component with deterministic callbacks.
4. Unit and RLS tests.
5. No attachment to an AI chat or document flow yet; integration points remain explicit props/API calls.

## Out of scope

- document upload/OCR;
- AI extraction;
- automatic prompt generation;
- persistent storage of analysis-only health facts;
- production rollout.
