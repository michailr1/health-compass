# HC-012b Slice B — Dictionaries and Typeahead Audit

Status: `IN PROGRESS`  
Base: `main` at `b67fb10def50a263c04cb0009c361fd20567273e`  
Production: untouched

## Canonical product rules

- Typeahead must never block free text.
- Global Dictionary is curated and profile-independent.
- User-entered text never enters Global Dictionary automatically.
- Personal Dictionary is built from confirmed profile history.
- AI Moderated Dictionary is out of scope for the first Slice B implementation.
- A selected suggestion and a free-text entry must remain distinguishable in provenance.
- `display_text` must preserve what the user entered or confirmed.
- `canonical_concept_id` is optional.

## Initial Slice B scope

### Backend

1. Add a curated global concept table with:
   - stable UUID;
   - section/domain;
   - canonical display name;
   - normalized search text;
   - optional short qualifier;
   - active flag;
   - source/provenance metadata.
2. Add aliases for search without duplicating concepts.
3. Expose read-only suggestion API scoped by section and query.
4. Combine global results with profile-specific history.
5. Keep all suggestion queries fail-closed under profile visibility/RLS rules.
6. Never write user text into the global tables from the application role.

### Frontend

1. Replace plain name input with accessible typeahead.
2. Allow keyboard and touch selection.
3. Always show `Добавить «<текст>»` when the input is non-empty and no exact selection was made.
4. Render the selected item as a chip before final save.
5. Preserve mobile wrapping and avoid horizontal scrolling.

## Proposed domains

- `condition_or_symptom`;
- `allergy_or_intolerance`;
- `medication`;
- `supplement`.

## Proposed API

```text
GET /profiles/{profile_id}/clinical-context/suggestions
    ?section=conditions
    &q=голов
    &limit=8
```

Response item:

```json
{
  "id": "uuid-or-null",
  "display_text": "Головная боль",
  "qualifier": null,
  "source": "global | personal",
  "canonical_concept_id": "uuid-or-null",
  "matched_text": "головная боль"
}
```

Free text is not returned as a stored suggestion; the frontend creates the explicit `Добавить …` option locally.

## Data migration approach

- next Alembic revision after `0042`;
- seed only a small reviewed starter set;
- keep seed data deterministic and idempotent;
- app role receives SELECT only on global dictionary tables;
- no INSERT/UPDATE/DELETE grants for app role;
- dictionary tables use RLS posture appropriate to global read-only reference data or explicit grants without profile data leakage.

## Open implementation questions to resolve from current code

- whether existing `code_system`/`code` fields can carry canonical references without a new FK;
- whether a separate `canonical_concept_id` column is required now or can be added in a follow-up migration;
- exact frontend component boundaries for reusable typeahead/chip behavior;
- ranking order between personal and global matches;
- normalization strategy for Russian and English text.

## Out of scope

- AI matching or embeddings;
- automatic medical classification;
- bulk import of large medical terminologies;
- OCR;
- course lifecycle questions;
- production rollout.
