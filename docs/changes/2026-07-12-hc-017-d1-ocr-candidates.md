# 2026-07-12 — HC-017 D1 Local OCR Candidates

HC-017 D1 was implemented in PR `#56` and merged into `main`.

```text
verified head: dc28e9e220dd51264e6dab1244ce8d8696f501b2
merge commit: a33c3d515b885c6ea0e8f51291a1d25bed77cd7d
CI: #442
repository Alembic: 0054
```

D1 adds:

- dedicated `health_compass_ocr_worker LOGIN NOBYPASSRLS`;
- OCR runs, encrypted provenance artifacts and review candidates;
- FORCE RLS and owner/edit-only candidate text;
- bounded local Tesseract execution over authenticated C2 safe pages;
- strict TSV parsing and deterministic candidate aggregation;
- encrypted TSV storage;
- restricted queue/claim/heartbeat/complete/fail functions;
- OCR status and candidate-read API;
- safe UI statuses;
- unit and PostgreSQL privilege/state tests.

Every candidate starts as `needs_review`. OCR does not create conditions, measurements, laboratory observations or other medical facts.

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

Next stage:

```text
HC-017 D2 — Human Review and Patient Matching
```

Canonical evidence:

- `docs/implementation/HC-017-SLICE-D1-OCR-CANDIDATES-EVIDENCE-2026-07-12.md`;
- `docs/implementation/HC-017-SLICE-D-OCR-CANDIDATES-AND-HUMAN-REVIEW.md`;
- `docs/CURRENT-STATE.md`;
- `docs/PROJECT-PLAN.md`.