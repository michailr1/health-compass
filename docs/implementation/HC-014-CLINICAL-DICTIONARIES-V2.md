# HC-014 — Clinical Dictionaries v2

Status: foundation slice in progress  
Base: clean `main` at `010e3977e4edabcf64630d51bc20ea0488b28506`  
Production: untouched

## Goal

Provide useful Russian-first suggestions for conditions, symptoms, allergens, medications and supplements without ever preventing free-text entry.

## Non-negotiable product rules

- The dictionary is assistive, never a gate.
- Unknown terms save immediately as user text.
- User-entered medical facts are never silently rewritten.
- Reconciliation with a canonical concept is optional and explicit.
- Canonical concepts, aliases, personal terms and commercial products are separate concerns.
- Every imported record must carry provenance, version, locale/country scope and lifecycle status before bulk distribution.

## Concept model

### Canonical concept

Stable internal identity for a condition/symptom, allergen, active medication ingredient or supplement ingredient.

### Alias

Russian and English synonyms, common spelling variants, abbreviations, transliterations and country-aware brand terms.

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
   - curated alias;
   - canonical display name;
   - prefix match;
   - contains/fuzzy candidates;
   - free-text fallback in the UI.
7. Cyrillic/Latin transliteration and typo tolerance are the next search slice; they require bounded scoring and regression data rather than silent autocorrection.

## Source strategy

### Conditions and symptoms

WHO ICD-11 may be used for external mappings and terminology only under its published license and attribution requirements. The consumer-facing Russian labels remain a curated Health Compass presentation layer rather than copied diagnostic descriptions.

### SNOMED CT

Optional mapping only. Distribution and deployment require territory-appropriate licensing. The MVP must not depend on SNOMED availability.

### Medications

NLM RxNorm is useful for active-ingredient identifiers and English-language aliases, but it does not provide sufficient Russia/EU brand coverage. Canonical identity remains active-ingredient-first; country-specific brands are aliases/products with provenance.

### Supplements

NIH DSLD can support ingredient and US product-label references. It is not a global catalogue and must not be presented as proof of efficacy, safety or product quality.

## Delivery slices

1. **Foundation** — normalization, deterministic ranking and architecture documentation; no migration.
2. **Seed format** — versioned manifests, validation and idempotent importer.
3. **Conditions/allergens** — curated Russian-first initial seed.
4. **Medication ingredients** — active ingredients plus RU/EU/EN aliases.
5. **Supplement ingredients** — ingredient/form/composition separation.
6. **Personal reconciliation** — explicit user-approved mapping workflow.

## Migration sequencing

Production is at Alembic `0045`, while another open branch already owns revision `0046`. This foundation intentionally introduces no migration. Any dictionary-v2 schema migration must be numbered only after the open migration sequence is resolved, avoiding parallel heads and revision collisions.

## Initial scale targets

These are product targets, not one-shot import requirements:

- conditions and symptoms: 400–600;
- allergens and intolerances: 150–250;
- medication active ingredients: 700–1200;
- supplement ingredients: 250–400.

Each batch must be reviewable, source-scoped and reversible.
