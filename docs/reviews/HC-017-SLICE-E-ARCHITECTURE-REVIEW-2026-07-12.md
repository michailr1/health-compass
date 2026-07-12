# HC-017 Slice E — Confirmed Labs Architecture Review

Date: 2026-07-12  
Reviewed base: `34425d89fb205a43d8ce543862b2ab8371dabbb4`  
Repository Alembic head: `0055`  
Production: `b8e868825f378195975e2729f3f36c21a1afa2d0 / 0049`

## Verdict

```text
ARCHITECTURE ACCEPTED FOR FUTURE IMPLEMENTATION
NO SLICE E CODE YET
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

The proposed boundary preserves the distinction between finalized transcription and confirmed clinical observations. No confirmed Lab row can be created by OCR, parser, worker, dictionary or AI alone.

## Reviewed architecture

- source-preserving draft model;
- explicit value-kind/date/range contracts;
- multi-candidate provenance;
- patient-decision gate;
- atomic confirmation;
- immutable confirmed snapshots;
- duplicate/idempotency behavior;
- correction/void/erasure lifecycle;
- owner/edit/view/analyze matrix;
- document-linked deletion;
- logs and audit restrictions;
- staged E1/E2/E3 implementation.

## Confirmed strengths

### Separate confirmation boundary

Finalized D2 transcription is only eligible input. A separate owner/editor action is required to create a Lab observation.

### Source preservation

Original analyte, value, unit, range, date/specimen and flag text remain independent from parsed or canonical representations.

### Exact provenance

Every observation is linked to the current document, finalized OCR run, patient decision and exact OCR candidate versions/roles.

### Least privilege

Drafts are owner/edit-only. View/analyze receive only active confirmed structured observations. Workers cannot confirm or mutate clinical facts.

### Immutable confirmed data

Confirmed source/value fields are not updated in place. Corrections create replacement observations and an explicit supersession chain.

### Deletion completeness

Initial observations remain tied to one source document. Document deletion therefore has a deterministic sole-provenance erasure contract.

## Architecture findings resolved

### AR-E-01 — Finalized OCR could be mistaken for confirmed data

Severity before decision: `HIGH`.

Resolution:

- introduced a separate Lab draft;
- introduced explicit confirmation booleans;
- prohibited automatic observation creation;
- separated Slice D finalization from Slice E confirmation.

### AR-E-02 — Parsed numeric values could overwrite source text

Severity before decision: `HIGH`.

Resolution:

- all source fields remain mandatory provenance;
- parsed decimal/date/range fields are separate;
- source text remains available after confirmation and correction.

### AR-E-03 — Analyze role might gain OCR access

Severity before decision: `HIGH`.

Resolution:

- analyze receives active confirmed observations only;
- Lab drafts, OCR candidates and source text selection remain owner/edit-only;
- no preview/raw artifact access is added.

### AR-E-04 — Patient identity absent from document

Severity before decision: `HIGH`.

Resolution:

- unknown and mismatch block confirmation;
- not-present requires a second explicit assignment acknowledgement;
- no OCR-based automatic patient inference.

### AR-E-05 — Silent duplicate merging could destroy provenance

Severity before decision: `MEDIUM`.

Resolution:

- no silent merge;
- one draft creates at most one observation;
- same-looking result from another document remains separately sourced;
- duplicate detection is advisory only.

### AR-E-06 — Confirmed values could be edited destructively

Severity before decision: `HIGH`.

Resolution:

- no in-place confirmed field updates;
- corrections create a new snapshot;
- prior observation remains superseded with provenance.

### AR-E-07 — Document erasure could leave unsupported observations

Severity before decision: `HIGH`.

Resolution:

- initial observation provenance is restricted to one document/current OCR run;
- source deletion immediately hides and eventually erases drafts and sole-provenance observations;
- observation cannot survive without valid provenance.

## Remaining implementation decisions

These are not blockers for architecture acceptance, but must be settled in implementation PRs:

1. exact numeric precision/scale;
2. exact source-role enum and candidate-count limits;
3. dedicated laboratory analyte dictionary/domain timing;
4. exact API envelope and UI field layout;
5. whether E1 parsing is manual-only or includes deterministic suggestions;
6. exact void/correction reason limits;
7. erasure tombstone shape;
8. possible-duplicate warning algorithm, which must not merge automatically.

## Required implementation gates

Before E1 merge:

- recheck `main`, open PRs and Alembic heads;
- reserve next migration only then;
- implement draft/source tables with FORCE RLS;
- no direct broad runtime mutation grants;
- current finalized D2 run and patient decision checks;
- active consent and optimistic concurrency;
- PostgreSQL owner/editor/view/analyze/outsider tests;
- zero confirmed observations before explicit E2 confirmation.

Before E2 merge:

- immutable observation/source tables;
- atomic confirmation function;
- exact candidate/version manifest;
- patient match/not-present acknowledgement;
- idempotent retry and conflicting-retry tests;
- analyze confirmed-only access;
- no automatic interpretation or normalization;
- content-free audit.

Before E3 merge:

- correction replacement chain;
- void and owner-only erasure;
- document deletion propagation;
- consent-withdrawn erasure path;
- no orphaned sole-provenance observation;
- independent security review.

## Production decision

Slice E architecture does not authorize production rollout.

Production remains:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

No Slice E code, migration, service provisioning or VPS task should start from this review alone.
