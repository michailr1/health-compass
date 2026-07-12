# HC-017 B–E2 — controlled production rollout

Status: `AUTHORIZED FOR PHASE 1 PREPARATION / NOT YET DEPLOYED`  
Target environment: `https://health.funti.cc`  
Target host: `funti.cc` / `172.245.108.154`  
Repository: `/opt/health-compass/repo`

## 1. Purpose

Deploy the current repository implementation through HC-017 E2 to the existing production host for owner testing, while keeping document upload disabled and preserving a fail-safe rollback path.

This rollout is permitted because the service currently has no external users or irreplaceable production health data. It is still treated as a controlled migration because authentication, RLS, database roles and the application schema are security-sensitive.

## 2. Responsibility boundary

The VPS agent:

- connects only to `funti.cc` (`172.245.108.154`);
- deploys an exact commit SHA already present in GitHub;
- does not write product code;
- does not create or edit migrations;
- does not commit, push, merge, open PRs or change GitHub state;
- does not print secrets, `.env` contents, database URLs, encryption keys or OAuth/SMTP credentials;
- stops on any target-host, backup, migration, build, RLS, service or HTTP ambiguity.

GitHub documentation and code changes remain the responsibility of the main development agent.

## 3. Phase 1 scope

Phase 1 deploys:

- application code through HC-017 E2;
- Alembic migrations `0050` through `0058`;
- frontend routes and UI through E2;
- document/OCR/Labs schema and restricted database functions;
- the existing fail-safe production configuration.

Mandatory Phase 1 setting:

```text
DOCUMENT_UPLOAD_ENABLED=false
```

Phase 1 does not:

- enable document upload;
- provision encryption credentials;
- start scanner, renderer, reconciler or OCR workers;
- install ClamAV, Poppler, ImageMagick or Tesseract;
- create document storage or spool directories;
- perform OCR or confirmed-Lab end-to-end testing;
- change OAuth, SMTP, DNS, Apache routing or existing secrets.

## 4. Why document upload remains disabled

The current application configuration intentionally rejects `DOCUMENT_UPLOAD_ENABLED=true` outside development until the scanner, renderer, OCR and rollout controls are separately approved.

Therefore Phase 1 can verify:

- database migration safety;
- backend startup and health;
- frontend serving and bundle switch;
- Google and Magic Link authentication;
- existing profile and Clinical Context behavior;
- RLS/security regressions;
- presence of the new disabled document UI/routes without accepting uploads.

It cannot yet verify the full upload → scan → render → OCR → review → Lab confirmation pipeline on production.

## 5. Serving-path invariant

Apache serves `health.funti.cc` from:

```text
/opt/health-compass/current-subdomain
```

The frontend rollout must atomically switch exactly that symlink. `/opt/health-compass/current` must not be assumed to be the serving path.

Before switching, the VPS agent must confirm the active Apache `DocumentRoot`/alias configuration. After switching, it must fetch production `index.html`, extract the referenced JS asset and prove that the asset belongs to the new release and returns HTTP `200`.

## 6. Mandatory preflight

Before any change, record without exposing secrets:

- `hostname -f || hostname`;
- public/resolved IP for `funti.cc`;
- repository path and clean `git status`;
- `HEAD_BEFORE`;
- current backend service unit name, `FragmentPath`, `ExecStart`, `WorkingDirectory` and environment-file path names only;
- active frontend symlink target;
- Apache serving path for `health.funti.cc`;
- current Alembic revision and heads;
- PostgreSQL service status;
- available disk space and inode usage;
- backend/frontend runtime versions;
- current `/api/health` and `/` HTTP status.

Stop without changes when:

- the host/IP does not match;
- `/opt/health-compass/repo` is absent;
- the repository contains uncommitted changes;
- Alembic has multiple heads;
- the backend unit or serving symlink cannot be identified confidently;
- disk space is insufficient for backup, build and release;
- current health checks already fail and the cause is not understood.

## 7. Backup gate

Before migrations:

1. create a timestamped PostgreSQL custom-format backup in the existing protected backup directory;
2. verify the backup with `pg_restore --list`;
3. record path, size and checksum;
4. preserve the previous frontend symlink target;
5. preserve `HEAD_BEFORE` and the current backend unit definition metadata.

Do not print database credentials. Use the existing protected production configuration or existing backup mechanism.

No migration or release switch is permitted unless backup verification succeeds.

## 8. Exact-SHA build and verification

The VPS agent must:

1. fetch origin without modifying GitHub;
2. resolve the exact requested target SHA;
3. prove it is reachable from `origin/main`;
4. check out/deploy that exact SHA using the server's established release method;
5. install backend dependencies in the existing isolated Python environment;
6. run backend compile, Ruff and non-integration tests;
7. run frontend `npm ci`, lint, typecheck, tests and production build;
8. verify `DOCUMENT_UPLOAD_ENABLED=false` without printing the env file;
9. verify the application configuration can load in production mode.

Stop before migration if any check fails.

## 9. Migration gate

Using the existing migrator identity:

```text
alembic current
alembic heads
alembic upgrade head
alembic current
```

Expected result:

```text
single repository head: 0058
production before: 0049
production after: 0058
```

The migration must also prove that the required PostgreSQL roles exist before their migrations need them:

```text
health_compass_worker
health_compass_renderer
health_compass_reconciler
health_compass_ocr_worker
health_compass_rls_definer
```

The LOGIN worker roles must be `NOBYPASSRLS`, non-superuser, no-createdb, no-createrole and no-replication. The definer role must remain `NOLOGIN BYPASSRLS`. Role passwords and DSNs must never be printed.

If a required role is absent, stop before migration and report only the missing role names. Do not invent credentials or alter role architecture without a separate approved provisioning instruction.

Automatic Alembic downgrade is forbidden.

## 10. Backend and frontend release

After successful migration:

- restart the existing backend service;
- wait for readiness;
- require local `127.0.0.1:8100/health` HTTP `200`;
- require public `/api/health` HTTP `200`;
- create a new immutable frontend release directory;
- copy the exact target build output into it;
- atomically switch `/opt/health-compass/current-subdomain`;
- validate Apache configuration;
- reload Apache without restart when possible;
- verify production `index.html` and referenced assets over HTTPS.

Do not delete previous releases during this rollout.

## 11. Automated smoke tests

Required public checks:

- `/` → `200`;
- `/login` → `200`;
- `/api/health` → `200`;
- `/api/auth/provider/google` → `307`;
- Google redirect uses `https://health.funti.cc/api/auth/callback` and includes account selection;
- email Magic Link request → expected accepted response without printing a token;
- direct frontend refreshes do not return `404`;
- document UI is present but upload remains disabled;
- no unexpected `5xx`.

Required database/security checks must be read-only or use disposable test identities/data only:

- one Alembic head at `0058`;
- application and worker roles retain expected `NOBYPASSRLS` attributes;
- worker roles have no broad direct mutation grants on HC-017 tables;
- expected restricted functions exist with PUBLIC execute revoked;
- ordinary logs do not contain document content, OCR text, medical values, tokens or credentials.

## 12. Owner manual smoke

After the automated report, the owner verifies in a browser:

- Google login;
- Email Magic Link login;
- logout and re-login;
- dashboard/profile loading;
- Clinical Context create/edit/remove flows;
- permanent deletion flow from HC-016;
- direct refresh on new document/Lab routes;
- disabled upload state is understandable and does not break navigation.

Phase 1 is not accepted until owner smoke succeeds.

## 13. Log observation

Inspect only fresh logs from the new process/release window. Report counts and sanitized summaries for:

```text
Traceback
ERROR
CRITICAL
54001
42501
permission denied
HTTP 5xx
```

Do not paste sensitive request bodies, query strings, cookies, tokens, document text or environment values.

## 14. Rollback

Before migration failure:

- make no release switch;
- restore repository/release selection to the previous state when needed;
- keep production running on the previous release.

After migration but before frontend acceptance:

- do not run automatic Alembic downgrade;
- frontend may be rolled back by restoring the previous `/opt/health-compass/current-subdomain` target and reloading Apache;
- backend rollback is allowed only after confirming the previous code can run safely against schema `0058`;
- otherwise keep the new backend with document upload disabled or restore the verified database backup only by explicit owner decision.

On any cross-user leak, authentication bypass or RLS failure:

- stop the rollout;
- place the application in maintenance/unavailable state if required;
- preserve logs and evidence;
- do not prioritize availability over data isolation.

## 15. Required VPS report

The VPS agent returns:

- confirmed host/IP;
- target SHA and proof it belongs to `origin/main`;
- `HEAD_BEFORE` and deployed SHA;
- Alembic before/heads/after;
- required-role presence and sanitized attributes;
- backup path, size, checksum and `pg_restore --list` result;
- backend unit name and active state;
- frontend release path;
- `current-subdomain` before/after targets;
- production JS bundle before/after and HTTP asset status;
- all build/test/smoke results;
- fresh sanitized log findings;
- explicit confirmation that `DOCUMENT_UPLOAD_ENABLED=false`;
- confirmation that no worker services were started and no secrets were printed;
- any stop condition or deviation.

## 16. Phase 2 boundary

Full HC-017 B–E2 owner testing requires a separate Phase 2 after Phase 1 acceptance:

- production encryption-key provisioning and recovery procedure;
- private encrypted storage and isolated spool directories;
- dedicated OS users and hardened systemd units;
- ClamAV/FreshClam installation and healthy signatures;
- verified Poppler, ImageMagick, Tesseract and `rus+eng` traineddata;
- reverse-proxy body limit;
- measured quotas and free-space reserve;
- hostile-file/resource probes;
- database plus encrypted-object backup/restore test;
- a reviewed code change that permits controlled production enablement;
- explicit owner approval to set `DOCUMENT_UPLOAD_ENABLED=true`.

Until then, production upload remains disabled by configuration and by application validation.
