# 2026-07-12 — HC-017 Slice E Confirmed Labs Architecture

Slice E architecture was defined after the completed D1/D2 OCR and human-review repository stages.

Repository baseline:

```text
34425d89fb205a43d8ce543862b2ab8371dabbb4
Alembic: 0055
```

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

The architecture introduces three future implementation stages:

```text
E1 — source-preserving Lab drafts
E2 — explicit confirmed observations
E3 — correction, void and erasure lifecycle
```

Key accepted decisions:

- finalized OCR transcription is not a Lab fact;
- owner/editor creates a separate structured draft;
- exact OCR candidates and source roles form the provenance manifest;
- source analyte/value/unit/range/date/specimen text remains preserved;
- parsed and canonical fields remain separate;
- patient unknown/mismatch blocks confirmation;
- not-present requires an additional explicit profile-assignment acknowledgement;
- confirmation is a separate atomic transaction;
- confirmed observations are immutable snapshots;
- correction creates a replacement/supersession chain;
- duplicate-looking observations are not silently merged;
- analyze receives active confirmed observations only;
- document erasure removes sole-provenance drafts and observations;
- no worker can confirm, correct, void or erase observations;
- no diagnosis, interpretation, recommendation or dose calculation is produced.

Canonical documents:

- `docs/implementation/HC-017-SLICE-E-CONFIRMED-LABS-CORE.md`;
- `docs/reviews/HC-017-SLICE-E-ARCHITECTURE-REVIEW-2026-07-12.md`;
- `docs/SECURITY-INVARIANTS.md`;
- `docs/CURRENT-STATE.md`;
- `docs/PROJECT-PLAN.md`;
- `docs/source-index/SOURCE-REGISTER.md`.

Current status:

```text
SLICE E ARCHITECTURE DEFINED AND REVIEWED
NO SLICE E CODE
NOT DEPLOYED
PRODUCTION UNCHANGED
```
