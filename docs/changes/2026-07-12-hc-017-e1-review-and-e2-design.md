# 2026-07-12 — HC-017 E1 review and E2 architecture

An independent post-merge security review was completed for E1 baseline:

```text
2ad0ca47d994472201c218b3e6af37145cbacdec
```

Review verdict:

```text
ACCEPT FOR REPOSITORY FOUNDATION
NO UNRESOLVED CRITICAL OR HIGH FINDING
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

The review confirms that E1 creates only owner/editor source-preserving drafts and that migrations `0056–0057` enforce current document/OCR/patient/consent context on every mutation.

Slice E2 architecture was defined for:

```text
explicit acknowledgement
→ atomic current-source validation
→ immutable observation snapshot
→ immutable source snapshot
→ idempotent draft consumption
→ confirmed-only access
```

E2 design requires:

- owner/edit-only confirmation;
- no worker confirmation;
- one observation per E1 draft;
- profile-scoped idempotency;
- explicit assignment acknowledgement for `not_present` patient decisions;
- current draft/document/review/patient/candidate versions;
- active consent;
- no silent canonical mapping or unit conversion;
- no in-place mutation of confirmed source/value fields;
- no source deletion that orphans a confirmed observation.

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

Canonical documents:

- `docs/reviews/HC-017-SLICE-E1-INDEPENDENT-SECURITY-REVIEW-2026-07-12.md`;
- `docs/implementation/HC-017-SLICE-E2-CONFIRMED-OBSERVATIONS.md`.
