# Health Compass — текущее состояние

Дата: 2026-07-11  
Основная ветка: `main`  
Main HEAD на момент независимого ревью: `1a61f0307130e19fedeabd95218293d9a5075fe1`  
Production code: `f3d7e8fedcdad5448abce5c74c1bdb698e5e82e6`  
Production Alembic: `0045 (head)`  
Production URL: `https://health.funti.cc`  
Текущий engineering verdict: `FIX BEFORE ROLLOUT`

## Что работает в production

- FastAPI backend и React/Vite frontend;
- PostgreSQL + Alembic;
- direct Google OAuth 2.0 / OIDC;
- Email Magic Links через Brevo;
- локальные PostgreSQL sessions;
- users, identities, workspaces, profiles и permissions;
- FORCE ROW LEVEL SECURITY и tenant isolation;
- безопасный account linking и controlled duplicate resolution foundation;
- Basic Health Profile;
- история веса, provenance, consent и append-only audit;
- Clinical Context для состояний, аллергий, лекарств и добавок;
- review states `unknown`, `deferred`, `confirmed_none`, `has_entries`;
- contextual intake decisions;
- mobile-oriented questionnaire flow;
- Clinical Dictionaries v2 с Russian-first search и free-text fallback;
- dashboard context coverage и переходы к заполнению профиля.

## Production data state — Clinical Dictionaries v2

На 2026-07-10 успешно применён reviewed seed set.

Подтверждено:

- 69 concepts total;
- 107 aliases;
- 0 duplicate concept business keys;
- 0 duplicate aliases;
- 0 orphan aliases;
- все 66 reviewed business keys представлены;
- повторный apply идемпотентен;
- существовавшие UUID сохранены;
- Alembic остался `0045`.

Backup перед повторным import:

```text
/opt/health-compass/backups/clinical_dictionary_before_seed_retry_20260710T224649Z.sql.gz
```

Известные content gaps первого seed set:

- `мигрень` / `migraine`;
- `hypertension`;
- singular English `penicillin`;
- English phrase `vitamin d`.

Free-text entry остаётся доступным; gaps не являются importer defect.

## Подтверждённые security properties

Два независимых code review не обнаружили подтверждённого:

- cross-user data leak;
- обхода `FORCE RLS` runtime role;
- self-grant owner чужого profile;
- self-add в чужой workspace;
- удаления последней identity;
- silent account merge только по verified email.

Подтверждены:

- runtime role `NOBYPASSRLS`;
- отдельный `health_compass_rls_definer NOLOGIN BYPASSRLS`;
- ограниченные `SECURITY DEFINER` functions;
- `search_path=''`, `row_security=off` и отзыв `PUBLIC EXECUTE`;
- PKCE, state, nonce, issuer/audience/azp и verified-email checks;
- consent, provenance, void и audit для clinical data;
- одна DB transaction на request для transaction-local RLS context.

## Code review 2026-07-11

Проведены два независимых статических review актуального repository HEAD:

- ChatGPT architecture/code review;
- Fable 5 independent code review.

Канонические документы:

```text
docs/reviews/CODE-REVIEW-CONSOLIDATED-2026-07-11.md
docs/reviews/FABLE-5-INDEPENDENT-CODE-REVIEW-2026-07-11.md
```

Итог обоих review:

```text
FIX BEFORE ROLLOUT
```

Critical findings и подтверждённый tenant-isolation breach не обнаружены. Rollout gate установлен из-за дефектов корректности, schema drift и data integrity.

## Блокирующие findings

1. Duplicate Clinical Context summary/review routes с несовместимыми response contracts; текущее поведение зависит от порядка router registration.
2. Duplicate assessment/absorption не учитывает `profile_clinical_reviews` и `profile_intake_decisions`.
3. Email Magic Link выполняет meaningful consume через GET и может быть поглощён scanner/prefetch.
4. `canonical_concept_id` не полностью защищён от wrong-domain и stale mappings.
5. Frontend CI не запускает full-source lint и обязательный TypeScript typecheck.

Дополнительно приняты к исправлению:

- alias upsert по database business key;
- optimistic concurrency для void;
- race при `confirmed_none`;
- единый error envelope и сохранение `request_id`;
- safe structured logging и query/token redaction;
- fail-safe production account-linking configuration;
- POST logout;
- полный migration cycle;
- column-level narrowing для `users` UPDATE.

## Текущий обязательный этап

Следующая задача:

```text
HC-015 — Code Review Remediation
```

Канонический план:

```text
docs/implementation/HC-015-CODE-REVIEW-REMEDIATION.md
```

До завершения HC-015:

- не добавлять новые product features;
- не выполнять следующий production code rollout;
- не создавать параллельные Alembic heads;
- разрешены документация, tests и remediation branch;
- alias content expansion HC-014 не должна обходить remediation gate, если требует code rollout.

## Порядок HC-015

1. Clinical Context route cleanup.
2. Duplicate resolution schema synchronization.
3. Magic Link/logout/account-linking/logging hardening.
4. Canonical dictionary integrity migration.
5. Full lint/typecheck и migration-cycle CI.
6. Clinical concurrency и frontend API contract fixes.
7. Independent diff review.
8. Controlled backup-first rollout.
9. Production smoke и фиксация evidence.

## Известные ограничения продукта

- OCR/import документов не реализован;
- реальные загрузки лабораторных документов не реализованы;
- Labs core и динамика лабораторных показателей не реализованы;
- Oura и другие wearable integrations не реализованы;
- invitations и совместный доступ не завершены как user flow;
- AI explanation, evidence retrieval и doctor report не реализованы;
- clinical safety flags не выводятся автоматически из свободного текста;
- система не диагностирует заболевания и не рассчитывает дозы;
- словарь остаётся assistive и не заменяет free text.

## Следующий product этап после HC-015

После успешного remediation и rollout:

1. снять verdict `FIX BEFORE ROLLOUT` на основании evidence;
2. выполнить небольшой reviewed alias-expansion package HC-014;
3. вернуться к PHASE-03/04 document upload and OCR review foundation;
4. реализовать Labs core;
5. затем PHASE-05.5 Nutrition Photo MVP согласно отдельной спецификации.

## Роли

### ChatGPT / coding role

- архитектура и data contracts;
- product code;
- migrations, RLS и tests;
- frontend;
- документация;
- точные задачи VPS-agent.

### VPS-agent

- работает только с production host;
- фиксирует HEAD/Alembic before;
- создаёт backup;
- получает конкретный approved commit;
- выполняет build, migrations, systemd/release switch;
- запускает smoke tests и rollback при необходимости;
- не принимает архитектурных решений;
- не использует production DB для automated tests;
- не выводит secrets.

## Stop conditions

Остановить merge или rollout при:

- несовпадении expected HEAD;
- dirty production worktree;
- неуспешном backup;
- нескольких Alembic heads;
- неуспешной migration;
- duplicate route collision;
- wrong-domain canonical mapping;
- scanner GET, поглощающем Magic Link;
- duplicate resolution с 500/FK violation;
- признаках cross-user leak;
- `5xx`, `54001`, `42501`, `permission denied` или Traceback;
- CI, запущенном не на exact deployed SHA;
- появлении tokens, secrets или medical values в logs.
