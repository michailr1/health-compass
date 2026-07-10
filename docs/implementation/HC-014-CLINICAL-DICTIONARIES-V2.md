# HC-014 — Clinical Dictionaries v2

Status: foundation slice in progress  
Base: clean `main` at `010e3977e4edabcf64630d51bc20ea0488b28506`  
Production: untouched

## Goal

Provide useful Russian-first suggestions for conditions, symptoms, allergens, medications and supplements without ever preventing free-text entry.

## Mandatory Russian naming policy

- The primary `display_name` shown to users is Russian.
- Russian consumer-facing wording is preferred over literal machine translation.
- English, Latin and international names are searchable aliases, not the default UI label.
- For medications, the canonical user-facing ingredient name is the Russian МНН where available.
- Russian trade names registered for the Russian market are searchable brand/product aliases.
- A brand is never silently substituted for its active ingredient, and an active ingredient is never silently substituted for a brand.
- For conditions and symptoms, Russian labels should be understandable to a non-clinician; ICD wording and codes are retained as mappings where appropriate.
- For supplements, the primary label is the commonly used Russian ingredient name; Latin botanical names and English names are aliases.

## Non-negotiable product rules

- The dictionary is assistive, never a gate.
- Unknown terms save immediately as user text.
- User-entered medical facts are never silently rewritten.
- Reconciliation with a canonical concept is optional and explicit.
- Canonical concepts, aliases, personal terms and commercial products are separate concerns.
- Every imported record must carry provenance, version, locale/country scope and lifecycle status before bulk distribution.

## Concept model

### Canonical concept

Stable internal identity for a condition/symptom, allergen, active medication ingredient or supplement ingredient. Its default display label is Russian.

### Alias

Russian synonyms and common spellings rank first. English, Latin, abbreviations, transliterations, historical spellings and country-aware brand terms remain searchable aliases.

### Personal term

Previously entered user text. Personal terms rank highly for that profile but do not automatically become global dictionary records.

### Product and brand

Medication and supplement brands/products must not be treated as canonical ingredients. Combination products map to multiple canonical ingredients in a later schema slice.

## Search pipeline

1. Unicode NFKC normalization.
2. Case folding.
3. `ё` → `е` equivalence.
4. Punctuation and separator normalization.
5. Whitespace collapse.
6. Deterministic ranking:
   - exact match;
   - personal term;
   - curated Russian alias;
   - Russian canonical display name;
   - international/English/Latin alias;
   - prefix match;
   - contains/fuzzy candidates;
   - free-text fallback in the UI.
7. Cyrillic/Latin transliteration and typo tolerance are the next search slice; they require bounded scoring and regression data rather than silent autocorrection.

## Source strategy

### Conditions and symptoms

Primary presentation layer: curated Russian user-friendly labels.

External mappings:

- official Russian ICD-11 terminology from WHO where available;
- Russian ICD-10 terminology for compatibility with current Russian medical records and historical documents;
- ICD codes are mappings, not the text forced into the UI.

### Medications

Primary Russian sources:

- ЕСКЛП for Russian МНН, dosage forms, strengths, trade names, packages and registration-related attributes;
- ГРЛС for registered Russian-market medication names and registration verification.

Secondary source:

- NLM RxNorm for international identifiers and English aliases only.

Canonical identity remains active-ingredient-first. Russian trade names are aliases/products with source and country scope `RU`.

### Allergens and intolerances

Primary labels are common Russian names of substances and ingredient classes. Medication-allergen relationships should reference Russian МНН and registered ingredient names where available.

### Supplements and БАД

Primary labels are common Russian ingredient names. Sources include:

- the EAEU unified register of state registration certificates for registered БАД/product names;
- Russian/EAEU registration data for product provenance;
- Latin botanical names, English names and US DSLD labels only as supplemental aliases or mappings.

Registry presence confirms registration, not efficacy, safety for a particular user or product quality.

### SNOMED CT

Optional mapping only. Distribution and deployment require territory-appropriate licensing. The MVP must not depend on SNOMED availability.

## Delivery slices

1. **Foundation** — normalization, deterministic ranking and architecture documentation; no migration.
2. **Seed format** — versioned manifests, validation and idempotent importer.
3. **Russian conditions/allergens** — curated Russian-first initial seed with ICD mappings.
4. **Russian medication ingredients and brands** — МНН plus RU trade-name aliases from ЕСКЛП/ГРЛС.
5. **Russian supplement ingredients and БАД aliases** — ingredient/form/composition separation plus EAEU product names.
6. **Personal reconciliation** — explicit user-approved mapping workflow.

## Acceptance examples

- Search `ибупрофен` → primary result `Ибупрофен`; Russian brands may appear as aliases/products.
- Search a Russian brand → show the registered brand and its active ingredient relationship without replacing the user's choice.
- Search `ashwagandha` → suggest `Ашваганда`; `Withania somnifera` remains a Latin alias.
- Search `изжога` → suggest the plain Russian symptom label, with an ICD mapping only in metadata.
- Search an unknown Russian term → allow immediate free-text save.

## Migration sequencing

Production is at Alembic `0045`, while another open branch already owns revision `0046`. This foundation intentionally introduces no migration. Any dictionary-v2 schema migration must be numbered only after the open migration sequence is resolved, avoiding parallel heads and revision collisions.

## Initial scale targets

These are product targets, not one-shot import requirements:

- conditions and symptoms: 400–600;
- allergens and intolerances: 150–250;
- medication active ingredients: 700–1200;
- supplement ingredients: 250–400.

Each batch must be reviewable, source-scoped and reversible.
