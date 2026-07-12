# Health Compass — текущее состояние

Дата: 2026-07-12  
Основная ветка: `main`  
Main HEAD: `ccabab77cf929456a74b69c3478c71f92f167f78`  
Production URL: `https://health.funti.cc`  
Production application target: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic: `0049`  
Repository Alembic head: `0050`  
Текущий engineering verdict: `HC-017 SLICE B MERGED / NOT DEPLOYED`

## Evidence boundary

Production и repository state теперь намеренно различаются:

- `main` содержит HC-017 Slice B и migration `0050`;
- production остаётся на application target `b8e868...` и Alembic `0049`;
- document upload в production отсутствует;
- `DOCUMENT_UPLOAD_ENABLED` должен оставаться `false`;
- production startup validation отклоняет попытку включить Slice B upload вне development.

Владелец ранее подтвердил production HC-016. Детальный VPS-отчёт HC-016 не был перенесён в репозиторий, поэтому отсутствующие operational values не восстанавливаются предположениями.

## Что работает в production

- FastAPI backend и React/Vite frontend;
- PostgreSQL + Alembic;
- direct Google OAuth 2.0 / OIDC;
- Email Magic Links через Brevo;
- локальные PostgreSQL sessions;
- users, identities, workspaces, profiles и permissions;
- FORCE RLS и tenant isolation;
- account linking и controlled duplicate resolution;
- Basic Health Profile;
- история веса, consent, provenance и audit;
- Clinical Context для состояний, аллергий, лекарств и добавок;
- review states и contextual intake;
- Clinical Dictionaries v2;
- отдельные действия **Убрать из профиля** и **Удалить навсегда** для клинических записей.

## HC-014 — Clinical Dictionaries v2

Production seed подтверждён:

- 69 concepts;
- 107 aliases;
- 0 duplicate concept business keys;
- 0 duplicate aliases;
- 0 orphan aliases;
- все 66 reviewed business keys представлены;
- повторный apply идемпотентен;
- существовавшие UUID сохранены.

Free-text fallback остаётся доступным.

## HC-015 — Code Review Remediation

Статус: `DEPLOYED / AUTOMATED VERIFIED / OWNER SMOKE CONFIRMED`.

Production application commit:

```text
c87723d7b4d0e4d2db9f1e0df4e936fbfd543346
```

Alembic после HC-015:

```text
0048
```

Canonical evidence:

```text
docs/implementation/HC-015-PRODUCTION-EVIDENCE-2026-07-11.md
```

## Safari Magic Link regression

Исправлен hotfix:

```text
8c09c02fa007cd5e5945c5a93b4913ce63868e68
```

Работа Email Magic Link на iPhone Safari подтверждена владельцем.

## HC-016 — Owner-controlled Clinical Record Erasure

Статус: `MERGED / PRODUCTION MANUALLY ACCEPTED`.

Source PRs:

- PR `#44` — permanent clinical record erasure;
- PR `#45` — удаление backup-retention sentence из пользовательского предупреждения.

Merged application target:

```text
b8e868825f378195975e2729f3f36c21a1afa2d0
```

Alembic:

```text
0049
```

Security contract:

- у runtime app нет прямого DELETE на clinical tables;
- owner-only erasure идёт через restricted `SECURITY DEFINER` function;
- stale `expected_updated_at` ничего не удаляет;
- erasure доступен после отзыва consent;
- value-bearing audit rows удаляются;
- остаётся только content-free tombstone.

## HC-017 — Human Documents, OCR Review and Labs

### Architecture

Status: `MERGED` through PR `#47`.

Canonical document:

```text
docs/implementation/HC-017-DOCUMENTS-OCR-LABS-FOUNDATION.md
```

### Slice B — Secure Document Intake Foundation

Status: `IMPLEMENTED / MERGED / NOT DEPLOYED`.

Source PR:

```text
#48
```

Verified implementation head:

```text
46c5ea89d35cc85be0af3b80a9c56f40d5705ac5
```

Merge commit:

```text
ccabab77cf929456a74b69c3478c71f92f167f78
```

CI:

```text
#402 — success
```

Repository migration:

```text
0049 → 0050
```

Implemented in repository:

- `profile_documents`;
- `document_processing_jobs`;
- RLS + FORCE RLS;
- owner/edit insert;
- owner/edit/view metadata visibility;
- analyze excluded from document metadata;
- no direct runtime UPDATE/DELETE;
- streamed development/test upload into private quarantine;
- PDF/JPEG/PNG checks;
- 20 MiB file limit;
- pre-parser multipart body limit, including chunked uploads;
- 25 MP image limit;
- opaque UUID-based keys;
- rollback cleanup for route, commit and cancellation failures;
- content-free audit;
- duplicate-account activity protection;
- profile-aware capabilities API;
- upload/list/detail API;
- `/app/documents` metadata/status UI.

Not implemented:

- production object storage;
- malware scanner;
- safe PDF inspection;
- worker role and processing service;
- preview or download;
- OCR;
- extraction review;
- confirmed Labs observations;
- metric dynamics;
- document void/permanent erasure;
- production rollout.

Canonical evidence:

```text
docs/implementation/HC-017-SLICE-B-IMPLEMENTATION-2026-07-12.md
```

## Confirmed security properties

- runtime role `NOBYPASSRLS`;
- dedicated `health_compass_rls_definer NOLOGIN BYPASSRLS`;
- sensitive definer functions have fixed settings and no PUBLIC EXECUTE;
- one transaction per request for transaction-local RLS context;
- document metadata uses a narrower read boundary than normal profile data;
- `analyze` cannot access raw document metadata;
- storage key never contains user filename or medical values;
- external quarantine artifact is removed when the database transaction fails;
- oversized document requests are rejected before multipart parsing;
- document rows block incorrect “empty duplicate account” absorption.

## Current product limitations

- production document upload is not available;
- OCR is not available;
- Labs core is not available;
- metric dynamics is not available;
- no production document storage or scanner is approved;
- no background document worker exists;
- Oura and other wearable integrations are not implemented;
- invitations and collaborative access are incomplete as a user flow;
- AI explanation, evidence retrieval and doctor report are not implemented;
- the system does not diagnose diseases or calculate medication doses.

## Next required stage

```text
HC-017 Slice C — Scanner and Safe Rendering
```

Before implementation:

1. perform an independent security review of Slice B;
2. choose the production private-storage model;
3. choose and threat-review the malware scanner;
4. define isolated worker role and credentials;
5. define bounded PDF inspection and rasterization;
6. recheck current main and Alembic head;
7. create a separate Slice C branch.

No VPS deployment task should be created for Slice B.

## Non-blocking technical follow-ups

- revoke unnecessary PUBLIC EXECUTE from ordinary trigger functions;
- migrate deprecated `authlib.jose` usage to `joserfc`;
- add dictionary search indexes;
- clean unused CORS configuration;
- cache OIDC discovery/JWKS;
- retain restricted historical Apache logs according to policy.

## Stop conditions for Slice C

Stop merge or rollout when:

- production storage is public or inside the web root;
- scanner is absent, stubbed or fail-open;
- scanner outage permits promotion or OCR;
- worker uses app or migrator credentials;
- worker can enumerate arbitrary profiles;
- raw PDF is embedded directly in the browser;
- page, CPU, memory or timeout limits are absent;
- storage key or signed URL appears in logs;
- document contents or medical values appear in ordinary logs;
- cross-profile access is possible;
- migration has multiple heads;
- exact-head CI or PostgreSQL negative tests are missing.
