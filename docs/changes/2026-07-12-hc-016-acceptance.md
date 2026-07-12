# 2026-07-12 — HC-016 production acceptance

HC-016 owner-controlled permanent Clinical Context record erasure was merged through PR `#44` with migration `0049`.

A follow-up copy-only PR `#45` removed the backup-retention sentence from the destructive confirmation. The remaining warning states that the clinical record and medical values in its change history will be deleted and that the action cannot be undone.

The profile owner manually confirmed on 2026-07-12 that the production interface and HC-016 flows work as intended.

Final merged application target:

```text
b8e868825f378195975e2729f3f36c21a1afa2d0
```

Evidence boundary: the detailed VPS rollout report was not copied into the canonical repository record. Backup path, release paths, service output, log counts and VPS-side disposable PostgreSQL results are therefore not asserted here.

Canonical documents:

- `docs/implementation/HC-016-CLINICAL-RECORD-ERASURE.md`;
- `docs/implementation/HC-016-PRODUCTION-ACCEPTANCE-2026-07-12.md`;
- `docs/CURRENT-STATE.md`;
- `docs/PROJECT-PLAN.md`.
