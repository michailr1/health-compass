# HC-015 — Production Rollout Runbook

Status: `PLANNED / NOT DEPLOYED`  
Created: 2026-07-11  
Approved source commit: `c87723d7b4d0e4d2db9f1e0df4e936fbfd543346`  
Source PR: `#39 — HC-015: Code Review Remediation (Slices A–F)`  
Target Alembic head: `0048`  
Production baseline before rollout: code `f3d7e8fedcdad5448abce5c74c1bdb698e5e82e6`, Alembic `0045`  
Production URL: `https://health.funti.cc`  

## Purpose

Safely deploy the merged HC-015 remediation from the exact approved commit. The rollout is backup-first and must stop on any uncertainty involving authentication, RLS, migration state, clinical-data integrity or log privacy.

Merge is not deployment. This runbook does not authorize automatic downgrade or destructive recovery.

## Required evidence before rollout

Do not start deployment until all conditions below are true:

1. `main` resolves exactly to `c87723d7b4d0e4d2db9f1e0df4e936fbfd543346`.
2. GitHub Actions is green for the final PR head and the resulting `main` merge commit, or an equivalent full CI run has been executed against the exact target SHA.
3. Alembic reports exactly one script head: `0048`.
4. Production still reports the recorded baseline or any deviation is explained before continuing.
5. `ACCOUNT_LINKING_ENABLED=true` is present in production configuration. Do not print secrets or the full environment.
6. A database backup can be created, checked with `gzip -t`, and its restore listing can be inspected.
7. Reverse-proxy access logging has been reviewed for query-string leakage.

## Critical reverse-proxy log check

HC-015 removes query strings from application and Uvicorn access logs. A reverse proxy can still leak Magic Link and OIDC parameters if its access log records `$request`, `$request_uri`, raw upstream URI or another field containing the query string.

Before deployment:

- locate the active virtual-host configuration for `health.funti.cc`;
- identify the effective `access_log` and `log_format`;
- confirm that authentication query strings are not written;
- prefer a safe request path field such as `$uri` rather than `$request_uri` or the full `$request`;
- alternatively disable access logging only for sensitive auth callback/consume locations while retaining error logging;
- validate configuration with the proxy's config-test command before reload;
- do not create a real reusable Magic Link token merely to test logging.

Stop the rollout if token-bearing query strings can reach any proxy, CDN, WAF, analytics or application log.

## Phase 1 — Read-only preflight

Capture without changing production:

```text
UTC timestamp
current production git/release SHA
current Alembic revision
current release symlink target
backend service name and active state
frontend release path
health endpoint status
available disk space
current repository working-tree state
script heads
```

Expected source state:

```text
main: c87723d7b4d0e4d2db9f1e0df4e936fbfd543346
Alembic script head: 0048
production before deploy: f3d7e8f / 0045
```

The production checkout must not contain uncommitted changes. Do not overwrite a dirty tree; stop and report it.

## Phase 2 — Backup

Create a timestamped PostgreSQL backup under the established backup directory, using the existing production backup mechanism and migrator/admin credentials without printing them.

Required evidence:

- absolute backup path;
- file size;
- `gzip -t` result;
- restore/listing check result;
- timestamp in UTC.

Do not continue if the backup is empty, corrupt, unreadable or its contents cannot be listed.

## Phase 3 — Prepare immutable release

Prepare a new immutable release from the exact commit:

```text
c87723d7b4d0e4d2db9f1e0df4e936fbfd543346
```

Requirements:

- fetch from the canonical remote;
- verify the commit exists and matches the approved SHA;
- do not deploy from an arbitrary local branch tip;
- install backend dependencies in the release environment;
- build frontend from the same commit;
- do not switch the live symlink yet;
- do not expose environment values in command output.

Run release-local checks where practical:

```text
python compileall
Ruff
backend unit tests or the approved deploy subset
frontend lint
typecheck
frontend tests
frontend build
alembic heads
```

## Phase 4 — Migration

Apply only the forward migrations:

```text
0045 → 0046 → 0047 → 0048
```

Important behavior:

- `0046` updates duplicate-user activity assessment;
- `0047` validates clinical dictionary domains and takes an `ACCESS EXCLUSIVE` lock on the four clinical tables during repair/validation and trigger replacement;
- `0048` narrows runtime UPDATE privileges on `users`.

Before running migration:

- verify no long-running transaction is holding or waiting on the affected clinical tables;
- use a controlled maintenance window if active writes are possible;
- record the migration start time;
- be prepared to stop rather than force-kill an unexplained database session.

After migration verify:

```text
alembic current = 0048
alembic heads = one head, 0048
health_compass_app remains NOBYPASSRLS
all user/medical tables retain ENABLE + FORCE RLS
sensitive definer functions are owned by health_compass_rls_definer
PUBLIC EXECUTE is absent where prohibited
users UPDATE grant is limited as designed
canonical_concept_id direct UPDATE is revoked from runtime role
```

Do not run automatic downgrade after a partially applied or uncertain migration. Preserve evidence and stop.

## Phase 5 — Backend and frontend activation

Use the existing immutable-release and symlink strategy.

Order:

1. migration completed and verified;
2. activate backend release;
3. restart/reload backend service;
4. wait for local health success;
5. activate frontend release;
6. verify public health and application entry point.

Record:

- release path;
- symlink target before and after;
- service status;
- process start time;
- target SHA shown by the release metadata.

## Phase 6 — Mandatory smoke tests

### General

- public application returns HTTP 200;
- public API health returns HTTP 200;
- backend local health returns HTTP 200;
- no unexpected redirect loop;
- static frontend assets load.

### Existing-session and sign-in behavior

- an existing valid session still loads the dashboard;
- Google login start remains functional;
- logout is performed by POST and revokes the local session;
- GET logout does not change state and returns the expected non-success behavior;
- production starts only with account-linking protection enabled.

### Scanner-safe Magic Link

Use a controlled test account and avoid exposing the token in output:

1. request a Magic Link;
2. open the GET link once;
3. confirm that only the neutral interstitial is shown and no session is created;
4. confirm that the token remains usable after the GET;
5. submit the explicit POST action;
6. confirm one session is created;
7. confirm replay is rejected;
8. search application, Uvicorn and reverse-proxy logs for the unique token fingerprint without printing the full token.

Stop immediately if the token appears in any log or GET consumes it.

### Clinical Context

- summary loads and matches the canonical response contract;
- create, edit and void a disposable test record;
- void without `expected_updated_at` is rejected;
- stale void returns controlled conflict;
- fresh void succeeds;
- `confirmed_none` cannot coexist with a concurrent active record;
- a wrong-domain dictionary concept is rejected with a controlled validation response;
- clearing code/code system clears the derived canonical mapping;
- dose can be cleared;
- date-only display does not shift calendar day.

Do not use real sensitive medical content for smoke data.

### Duplicate resolution safety

Do not execute destructive absorption against a real user during smoke testing.

Use read-only assessment or a dedicated disposable fixture to confirm:

- review-only activity is meaningful;
- intake-only activity is meaningful;
- meaningful accounts are blocked from automatic absorption;
- no FK violation or HTTP 500 is produced.

## Phase 7 — Log and database review

Review the deployment window for:

```text
HTTP 5xx
Traceback
StatementTooComplex
SQLSTATE 54001
SQLSTATE 42501
foreign-key violations
duplicate route warnings
concept_domain_mismatch
invalid or unknown concept errors
session/authentication loops
secret or medical-value leakage
```

Expected validation errors from deliberate negative smoke tests must be distinguished from unexpected production errors.

## Stop conditions

Stop and do not mark the rollout successful if any of the following occurs:

- target SHA differs from the approved commit;
- more than one Alembic head exists;
- backup validation fails;
- migration cannot reach `0048` cleanly;
- RLS, grants, function ownership or PUBLIC EXECUTE invariants differ;
- backend fails startup because production configuration is unsafe;
- GET consumes a Magic Link;
- any auth token, cookie, authorization value or medical value appears in logs;
- reverse proxy logs token-bearing query strings;
- duplicate resolution returns 500 or can remove meaningful data;
- wrong-domain canonical mapping is accepted;
- cross-user visibility changes from the established invisible/404 contract;
- unexplained 5xx, `54001`, `42501` or FK errors appear;
- a rollback would require guessing about database state.

## Recovery principles

- do not perform automatic Alembic downgrade after uncertain migration execution;
- preserve the database backup and all deployment logs;
- if migrations completed but application activation failed, prefer fixing or reverting application release while keeping the verified forward schema when compatible;
- if data integrity or tenant isolation is in doubt, place the service in maintenance rather than serving potentially unsafe responses;
- any restore must be an explicit owner-approved operation with a separate plan and evidence.

## Completion evidence

The rollout report must contain:

```text
production HEAD before / after
Alembic before / after
approved target SHA
backup path, size, gzip test and restore-listing result
release path and symlink target
backend service status
health endpoint results
Magic Link GET/POST/replay results
logout POST/GET results
Clinical Context smoke results
duplicate-resolution safety result
RLS/grants/function ownership verification
reverse-proxy/application log redaction evidence
log review summary
remaining risks
```

Only after all evidence is collected may HC-015 documentation move from `MERGED / NOT DEPLOYED` to `VERIFIED / DEPLOYED` and the rollout gate be removed.

## Known follow-ups not blocking this rollout

- CR-14: indexed/trigram dictionary search;
- CR-20: unused CORS configuration cleanup;
- CR-21: OIDC discovery/JWKS caching;
- open PR #25 must be rebased and its migration renumbered to follow `0048` before it can be merged.
