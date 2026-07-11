# HC-015 — Production Rollout Evidence

Status: `DEPLOYED / AUTOMATED VERIFIED / MANUAL SMOKE PENDING`  
Date: 2026-07-11  
Production URL: `https://health.funti.cc`  
Approved application commit: `c87723d7b4d0e4d2db9f1e0df4e936fbfd543346`  
Production Alembic: `0048`  
Source PR: `#39`  
Rollout runbook: `docs/implementation/HC-015-PRODUCTION-ROLLOUT.md`

## Verdict

HC-015 was deployed successfully from the exact approved application commit.
Automated rollout checks passed. No automated evidence of RLS regression, auth
loop, route collision, migration failure, 5xx, query-token leakage or clinical
dictionary integrity failure was found.

Manual owner-level smoke remains pending for:

1. real Google login;
2. real Email Magic Link GET → explicit POST consume → replay rejection;
3. one disposable Clinical Context create/edit/void flow.

Until those three checks are complete, the final project status is
`AUTOMATED VERIFIED / MANUAL SMOKE PENDING`, not fully closed.

## Rollout window

- Start: `2026-07-11 14:09 UTC`
- End: `2026-07-11 15:00 UTC`

## Production state

| Item | Before | After |
|---|---|---|
| Application commit | `f3d7e8fedcdad5448abce5c74c1bdb698e5e82e6` | `c87723d7b4d0e4d2db9f1e0df4e936fbfd543346` |
| Alembic | `0045` | `0048` |
| Frontend symlink | `/opt/health-compass/releases/ui-20260710T210205Z` | `/opt/health-compass/releases/hc015-20260711T145239Z` |
| Backend service | active | active after restart |

The production repository is intentionally detached at the approved application
commit. The repository `main` may be ahead due to documentation-only commits;
that does not require another application rollout.

## Backup evidence

| Item | Evidence |
|---|---|
| Path | `/opt/health-compass/backups/health_compass_before_hc015_20260711T144816Z.dump` |
| Size | `305 KB` |
| Format/listing check | `pg_restore --list: OK` |
| SHA-256 | `8690649572ff0b33d58d1c3627719ffcb626fbb47a008d8996a582e8b3280025` |
| Permissions | `0600 root:root` |

The backup is retained. No restore or downgrade was performed.

## Migration evidence

Applied forward chain:

```text
0045 → 0046 → 0047 → 0048
```

Confirmed after migration:

- exactly one Alembic head: `0048`;
- runtime role remains `NOBYPASSRLS`;
- tenant and medical tables retain RLS + FORCE RLS;
- runtime UPDATE on `users` is limited to `display_name` and `updated_at`;
- runtime has no direct UPDATE on `canonical_concept_id`;
- clinical dictionary domain-integrity triggers are active on all four clinical tables;
- wrong-domain and invalid UUID paths are rejected by the trigger contract.

## Build and test evidence

Backend:

- dependency installation: passed;
- `compileall`: passed;
- `app.main` import: passed;
- single Alembic script head: passed.

Frontend:

- `npm ci`: passed;
- full lint: zero errors, 24 existing `react-refresh` warnings;
- TypeScript typecheck: passed;
- tests: `43/43` passed across 9 files;
- production build: passed.

## Health and activation evidence

After backend restart and frontend symlink switch:

- local backend health: HTTP 200;
- public API health: HTTP 200;
- public frontend: HTTP 200;
- static assets: HTTP 200;
- no redirect loop;
- backend service active.

## Logging gate and historical containment

Apache access logging was changed before rollout to a query-safe format:

```text
LogFormat "%a %l %u %t \"%m %U %H\" %>s %O %D \"%{User-Agent}i\"" health_safe
```

The format uses `%U` and does not log `%r`, `%q` or Referer.

Probe results after rollout:

| Marker | Access | Error | Journal | Uvicorn |
|---|---:|---:|---:|---:|
| Query marker | 0 | 0 | 0 | 0 |
| Referer marker | 0 | 0 | 0 | 0 |

Safe path logging remained present.

Historical exposure was detected in rotated Apache logs created before the fix:

- 59 Magic Link query matches;
- 19 OIDC callback code matches;
- 19 OIDC callback state matches;
- total historical auth-query matches: 97.

No matching log content was printed or deleted. Existing health-subdomain logs
were changed to `0640 root:adm`; Apache logrotate already uses
`create 640 root adm`.

This is a contained historical incident, not an active logging leak. Retention
and access must remain restricted.

## Deployment-window log review

Counts during the deployment window:

| Category | Count |
|---|---:|
| HTTP 5xx | 0 |
| Traceback | 0 |
| ERROR / CRITICAL | 0 |
| SQLSTATE 54001 / 42501 | 0 |
| FK violations | 0 |
| Duplicate route warnings | 0 |
| Auth loops | 0 |
| Token/query leakage | 0 |
| Medical-value leakage | 0 |

## Duplicate-resolution evidence

Production currently has zero rows in both:

- `profile_clinical_reviews`;
- `profile_intake_decisions`.

Migration `0046` includes both tables in meaningful-activity assessment. The
production check was read-only; no real account absorption was executed.

## PUBLIC EXECUTE review

Two migrator-owned trigger functions retain PostgreSQL's default PUBLIC EXECUTE:

- `sync_clinical_dictionary_concept()`;
- `sync_clinical_review_legacy_flag()`.

They are ordinary trigger functions, not the sensitive `SECURITY DEFINER`
functions checked by the HC-015 migration-cycle invariant. PostgreSQL trigger
functions cannot be usefully called as ordinary functions, so this did not
block rollout. Nevertheless, the grants are unnecessary and should be revoked
in a separate forward hardening migration with regression coverage.

The sensitive definer-function set remains separately tested for:

- ownership by `health_compass_rls_definer`;
- absence of PUBLIC EXECUTE;
- fixed search path and row-security behavior.

## Remaining risks and follow-ups

1. Complete the three manual owner-level smoke tests.
2. Revoke PUBLIC EXECUTE from the two ordinary trigger functions in a new
   hardening migration.
3. Migrate deprecated `authlib.jose` usage to `joserfc`.
4. Preserve restricted access and normal rotation for historical Apache logs.
5. Rebase open PR #25 and renumber its migration to follow `0048` before merge.
6. Deferred HC-015 items remain: dictionary indexes, unused CORS configuration
   cleanup and OIDC discovery/JWKS caching.

## Final automated verdict

```text
VERIFIED_AUTOMATED / MANUAL_SMOKE_PENDING
```

HC-015 can move to fully verified only after the owner confirms the real Google,
Magic Link and disposable Clinical Context flows and no new production errors
or sensitive log entries appear during those checks.
