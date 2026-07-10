# HC-012c — Contextual Intake Audit

Status: `IMPLEMENTED — CI IN PROGRESS`  
Base: `main` at `1b0bbe8bd63b180de9f73d6ecda5a85a773058c5`  
Production: untouched

## Product goal

When Health Compass encounters a relevant health fact during an analysis or conversation, the user chooses one explicit outcome:

1. `save_to_profile` — save as a durable profile fact;
2. `analysis_only` — use only for the current analysis;
3. `defer` — not now;
4. `explain` — show why the information is useful without committing data.

No option is preselected.

## Implemented invariants

- `analysis_only` rejects `record_payload` at schema validation.
- `defer` rejects both durable and transient payloads.
- `explain` remains a local UI action and is not persisted.
- `save_to_profile` validates through the existing section-specific Clinical Context schemas.
- durable saves reuse the existing create service, consent checks, audit events and review-state clearing.
- decision audit stores no proposed health-fact text.
- outsider access remains governed by profile visibility and RLS.
- one request remains one transaction.
- no AI diagnosis inference.

## Implemented backend model

Table: `profile_intake_decisions`

- `id uuid`;
- `profile_id uuid`;
- `prompt_key varchar(128)`;
- `context_type varchar(64)`;
- `decision varchar(32)`;
- `proposed_section varchar(32) nullable`;
- `analysis_scope_id uuid nullable`;
- `decided_by_user_id uuid`;
- `decided_at timestamptz`;
- `request_id varchar(128) nullable`.

Stored decisions:

- `save_to_profile`;
- `analysis_only`;
- `defer`.

The app role has SELECT and INSERT only. UPDATE and DELETE are revoked. RLS and FORCE RLS are enabled.

## Implemented API

```text
POST /profiles/{profile_id}/contextual-intake/decisions
```

For `save_to_profile`, the request contains `proposed_section` and `record_payload`. The service validates the payload with the existing section schema and creates the record using the standard Clinical Context service.

For `analysis_only`, the request contains an `analysis_scope_id` but cannot contain `record_payload`.

For `defer`, neither `analysis_scope_id` nor `record_payload` is accepted.

Response:

```json
{
  "decision_id": "uuid",
  "decision": "analysis_only",
  "record_id": null
}
```

## Implemented frontend component

`IntakePromptCard`

- concise fact preview;
- `Сохранить в профиль`;
- `Только для этого анализа`;
- `Не сейчас`;
- local `Зачем это нужно` disclosure;
- explicit persistence boundary copy;
- mobile-first controls;
- deterministic callback contract.

## Tests

Added coverage for:

- save-to-profile request shape;
- analysis-only scope requirement;
- rejection of analysis-only record payloads;
- defer payload rejection;
- append-only table privileges;
- FORCE RLS;
- migration head `0045`.

## Out of scope

- document upload/OCR;
- AI extraction;
- automatic prompt generation;
- persistent storage of analysis-only health facts;
- attachment to a concrete chat/analysis flow;
- production rollout.
