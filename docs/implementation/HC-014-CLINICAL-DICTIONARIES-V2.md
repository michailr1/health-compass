# HC-014 — Clinical Dictionaries v2

Status: foundation and reviewed seed set deployed  
Production code: `f3d7e8fedcdad5448abce5c74c1bdb698e5e82e6`  
Production Alembic: `0045 (head)`

## Goal

Provide useful Russian-first suggestions for conditions, symptoms, allergens, medications and supplements without ever preventing free-text entry.

## Mandatory Russian naming policy

- The primary `display_name` shown to users is Russian.
- Russian consumer-facing wording is preferred over literal machine translation.
- English, Latin and international names are searchable aliases, not default UI labels.
- For medications, the canonical user-facing ingredient name is the Russian МНН where available.
- Russian trade names registered for the Russian market are product/brand aliases, never canonical ingredients.
- For conditions and symptoms, Russian labels should be understandable to a non-clinician; ICD codes stay in metadata.
- For supplements, the primary label is the common Russian ingredient name; Latin botanical names and English names are aliases.

## Product rules

- The dictionary is assistive, never a gate.
- Unknown terms save immediately as user text.
- User-entered medical facts are never silently rewritten.
- Reconciliation with a canonical concept is optional and explicit.
- Canonical concepts, aliases, personal terms and commercial products are separate concerns.
- Imported batches must be versioned, source-scoped, reviewable and reversible.

## Search order

1. Exact normalized match.
2. Personal previously used term.
3. Curated Russian alias.
4. Russian canonical display name.
5. International/English/Latin alias.
6. Prefix and contains matches.
7. Free-text fallback.

Normalization covers Unicode NFKC, case folding, `ё/е`, punctuation and whitespace.

## Source strategy

- Conditions/symptoms: curated Russian labels with ICD-10/ICD-11 mappings where appropriate.
- Medications: ЕСКЛП and ГРЛС for Russian МНН, dosage forms and registered trade names; RxNorm only for supplemental international identifiers.
- Allergens: curated Russian substance/class names, including medication ingredients.
- Supplements/БАД: Russian ingredient names plus EAEU/Russian registered product names as aliases; registry presence does not imply efficacy.
- SNOMED CT: optional mapping only where licensing permits.

## Seed batches

Current reviewed seed set:

- `ru-RU-pilot-v1.json`: 16 concepts, 29 aliases;
- `ru-RU-common-conditions-allergens-v1.json`: 25 concepts, 47 aliases;
- `ru-RU-common-medications-supplements-v1.json`: 25 concepts, 31 aliases.

Total reviewed content: 66 concepts and 107 aliases.

## Seed workflow

Validation is the default and performs no database writes:

```bash
cd backend
.venv/bin/python scripts/import_clinical_dictionary_seed.py
```

Expected output includes `VALID` and `DRY_RUN`.

Applying a reviewed batch is always explicit and uses `DATABASE_MIGRATOR_URL`, never the runtime application role:

```bash
cd backend
.venv/bin/python scripts/import_clinical_dictionary_seed.py --apply
```

A production import requires a separate deployment approval, a pre-import backup, before/after counts, duplicate checks and health checks.

## Idempotency and business key

Concept identity in the database is governed by the unique business key:

```text
(domain, normalized_text)
```

The importer must upsert concepts on that key, not only on the deterministic UUID. When an existing concept has the same business key but a different UUID, the existing database `id` is preserved and aliases are attached to the actual returned `concept_id`.

Deterministic UUIDv5 values are used for newly inserted concepts and aliases. Repeating the same reviewed batch is expected to be idempotent.

## Production history

### 2026-07-10 — foundation rollout

- Clinical Dictionaries v2 code deployed successfully.
- Production Alembic remained at `0045`.
- All three manifests passed dry-run validation.
- No seed rows were written during the code rollout.

### 2026-07-10 — first seed import attempt stopped safely

Pre-import state:

- 9 existing concepts;
- 0 aliases;
- 0 rows with `source_system = 'health_compass_ru_curated'`.

The first pilot apply failed on unique constraint `uq_clinical_dictionary_domain_name` for `(domain, normalized_text)`. Root cause: the original importer used `ON CONFLICT (id)`, while existing concepts had different UUIDs but matching business keys.

Safety result:

- transaction rolled back;
- counts remained 9 concepts and 0 aliases;
- subsequent batches were not executed;
- migrations, frontend and user medical records were untouched;
- backup created at `/opt/health-compass/backups/clinical_dictionary_before_seed_20260710T172950Z.sql.gz`.

### 2026-07-10 — importer fix deployed

The importer was corrected to:

- use `ON CONFLICT (domain, normalized_text)`;
- preserve existing concept IDs;
- use PostgreSQL `RETURNING id`;
- attach aliases to the actual database concept ID;
- cover the production conflict scenario with a regression test.

Fix commit deployed to production: `e1b4dce3db2719ddce13f37f7248369f43f3b163`.

### 2026-07-10 — reviewed seed set imported successfully

Backup before retry:

`/opt/health-compass/backups/clinical_dictionary_before_seed_retry_20260710T224649Z.sql.gz`

Import result:

- all three packages passed dry-run;
- all three packages applied successfully;
- repeated apply was idempotent;
- Alembic remained `0045`;
- backend stayed healthy;
- frontend and user medical records were untouched.

Final database state:

- 69 total concepts;
- 107 aliases;
- 0 duplicate concept business keys;
- 0 duplicate aliases;
- 0 orphan aliases.

The database contains 69 concepts rather than 66 because 9 concepts already existed before the reviewed import and 6 of the 66 reviewed business keys overlapped those existing rows. Therefore:

- all 66 reviewed business keys are represented;
- 60 new concepts were inserted;
- 6 reviewed concepts reused existing rows;
- 3 pre-existing concepts were outside the reviewed set;
- all 9 pre-existing UUIDs were preserved.

Representative search checks passed for `головная боль`, `гипертония`, `пенициллин`, `витамин д`, `магний`, `headache` and `magnesium`.

## Known content gaps after first reviewed import

The following search forms were not present in the reviewed seed manifests and therefore did not match:

- `мигрень` / `migraine`;
- `hypertension`;
- singular English `penicillin`;
- English phrase `vitamin d`.

These are seed-content gaps, not importer defects. Existing related terms include `high blood pressure`, `penicillins`, `пенициллин`, `cholecalciferol` and `холекальциферол`. Free-text entry remains available for all unmatched terms.

The next curated content patch should add the missing aliases only after review, using the same versioned and idempotent workflow.

## Delivery slices

1. Foundation: normalization and deterministic ranking — complete and deployed.
2. Seed format: validation and idempotent import — complete and verified in production.
3. Russian conditions and allergens — first reviewed package deployed.
4. Russian medication ingredients — first reviewed package deployed.
5. Russian supplement ingredients — first reviewed package deployed.
6. Alias coverage expansion — next content task.
7. Explicit personal-term reconciliation — not started.
8. Official source ingestion and traceable mappings — not started.

## Migration sequencing

Production is at Alembic `0045`, while PR #25 owns revision `0046`. HC-014 introduces no migration and must not create a parallel head.

## Next step

Prepare a small reviewed alias-expansion package for the confirmed gaps, test it in dry-run and production-like PostgreSQL, and apply it only through the same backup-first controlled import process.
