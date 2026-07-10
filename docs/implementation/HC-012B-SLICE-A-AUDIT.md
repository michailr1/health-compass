# HC-012b Slice A — Implementation Audit

Status: `IN PROGRESS`  
Base: `main` at `eb7d6ab4e8f2c85c0f58cd4e087ab19462e907de`  
Production: untouched

## Confirmed current implementation

### Database

`profile_clinical_reviews` was introduced by migration `0039_add_clinical_context_review_state.py`.

Current columns:

- `id uuid`;
- `profile_id uuid`;
- `section varchar(32)`;
- `confirmed_empty boolean NOT NULL DEFAULT false`;
- `reviewed_at timestamptz`;
- `reviewed_by_user_id uuid`;
- `updated_at timestamptz`.

Current constraints and security:

- UNIQUE `(profile_id, section)`;
- sections limited to conditions/allergies/medications/supplements;
- ENABLE RLS;
- FORCE RLS;
- SELECT through `app_can_view_profile`;
- INSERT/UPDATE through `app_can_edit_profile` and current actor;
- app role has SELECT/INSERT and column-level UPDATE;
- app role must remain without DELETE after migration `0041`.

### ORM

`backend/app/models/clinical_context.py` contains `ProfileClinicalReview` with boolean `confirmed_empty`.

### Existing audit

Current review changes use the generic action:

- `clinical_context.reviewed`.

Slice A must extend this to explicit review-state audit semantics while preserving existing history.

## Required implementation files

The existing HC-012b code is concentrated in:

- `backend/alembic/versions/0039_add_clinical_context_review_state.py`;
- new migration after current head (`0042` if head remains `0041`);
- `backend/app/models/clinical_context.py`;
- `backend/app/schemas/clinical_context.py`;
- `backend/app/schemas/clinical_context_summary.py`;
- `backend/app/services/clinical_context.py`;
- `backend/app/api/routes/clinical_context.py`;
- `backend/tests/test_clinical_review_rls.py`;
- `backend/tests/test_clinical_context_hardening.py`;
- `backend/tests/test_migrations.py`;
- `src/components/ClinicalContextSection.tsx`;
- `src/components/ClinicalContextSection.test.ts`;
- `src/lib/api.ts`.

## Planned schema change

Replace the boolean-only representation with:

```text
review_state = unknown | deferred | confirmed_none
```

`has_entries` remains derived and is never accepted as a stored client value.

Backfill:

- `confirmed_empty=true` → `confirmed_none`;
- `confirmed_empty=false` → `unknown`.

The obsolete boolean can only be dropped after backend and frontend no longer reference it in the same reviewed change set.

## Non-negotiable invariants

- adding the first record clears `deferred` or `confirmed_none` atomically;
- confirmed-none is rejected while records exist;
- voiding the final record does not create confirmed-none;
- no physical DELETE;
- RLS/FORCE RLS preserved;
- outsider API remains 404;
- no production deployment from this branch.
