# 2026-07-13 — HC-017 B–E2 Phase 1 manually accepted

Status: `MANUALLY ACCEPTED / FULL DOCUMENT PIPELINE STILL DISABLED`.

## Owner verification

The owner completed the post-rollout browser smoke on `https://health.funti.cc` and confirmed that the deployed UI opens correctly.

Accepted scope:

- application shell and navigation load;
- Google-authenticated application access remains usable;
- dashboard/profile routes open;
- Clinical Context remains accessible;
- HC-016 permanent-erasure UI remains accessible;
- `/app/documents` opens and survives direct refresh;
- `/app/lab-drafts` opens and survives direct refresh;
- the deployed disabled document foundation does not break the existing product.

## Acceptance result

```text
SERVER ROLLOUT: ACCEPTED
AUTOMATED SMOKE: PASSED
SECURITY CHECKS: PASSED
MANUAL UI SMOKE: PASSED
HC-017 B–E2 PHASE 1: MANUALLY ACCEPTED
```

## Boundary

This acceptance applies only to the Phase 1 deployment of code, schema, frontend routes and restricted PostgreSQL interfaces.

It does not mean that the document-processing product pipeline is enabled or accepted.

The following remain disabled/not provisioned:

```text
DOCUMENT_UPLOAD_ENABLED=false
scanner worker: not running
renderer worker: not running
reconciler worker: not running
OCR worker: not running
production document storage: not provisioned
malware scan pipeline: not running
safe rendering pipeline: not running
OCR pipeline: not running
```

Full upload → scan → render → OCR → human review → Lab confirmation testing requires the separately controlled Phase 2 rollout.

## UX findings accepted for follow-up

The owner/Fable review of the deployed UI produced the tracked HC-019 task:

- reduce primary mobile navigation to five items;
- rename the user-facing Documents workflow to `Анализы`;
- explain what users upload and why confirmation is required;
- replace the top-level `Oura` vendor tab with the `Сон` data domain;
- keep device vendors inside integration settings;
- hide `Подключить источник` until a real integration exists;
- remove storage-path and `карантин` developer language from UI.

Canonical HC-019 specification:

```text
docs/implementation/HC-019-NAVIGATION-AND-EMPTY-STATE-UX.md
```

HC-019 is scheduled after HC-017 E3 and must not be mixed into E3's database/security contract.

## Next repository task

```text
HC-017 E3 — Correction, Void and Owner-only Erasure
```

No new production rollout is authorized by this acceptance record.
