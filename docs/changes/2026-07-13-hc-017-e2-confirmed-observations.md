# 2026-07-13 — HC-017 E2 confirmed observations

HC-017 Slice E2 was implemented and merged through PR `#65`.

```text
verified head: 55f10d311d1f39262d557fa7b60cc07060ac5590
merge:         1d61331194edf0f78b94a304d27ccf31dfa2a755
CI:            #491 — passed
migration:     0058
```

E2 introduces an explicit confirmation transaction between E1 Lab drafts and confirmed laboratory observations.

Implemented controls:

- immutable observation and source-snapshot tables;
- owner/edit-only confirmation;
- owner/edit/view/analyze confirmed-only reads;
- no worker confirmation;
- active consent and current source-version checks;
- explicit acknowledgements;
- additional assignment acknowledgement for `not_present`;
- profile-scoped idempotency;
- deterministic candidate locking before immutable snapshot copying;
- one observation per draft;
- content-free audit;
- no automatic interpretation, normalization or unit conversion.

Final threat review found no unresolved Critical or High repository finding. It caused hardening of replay matching, concurrent confirmation and source-candidate TOCTOU behavior before merge.

Production did not change:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

The next repository stage is E3 correction, void and owner-only erasure. No production rollout is authorized.
