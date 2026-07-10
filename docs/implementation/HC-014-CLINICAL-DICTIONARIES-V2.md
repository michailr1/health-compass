# HC-014 — Clinical Dictionaries v2

Status: foundation slice in progress  
Production: untouched

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

## Delivery slices

1. Foundation: normalization and deterministic ranking.
2. Seed format: validation and idempotent import.
3. Russian conditions and allergens.
4. Russian medication ingredients and brands.
5. Russian supplement ingredients and БАД aliases.
6. Explicit personal-term reconciliation.

## Migration sequencing

Production is at Alembic `0045`, while another open branch already owns revision `0046`. This slice introduces no migration and must not create a parallel head.
