# HC-015 — Code Review Remediation

Status: `PLANNED / BLOCKS NEW ROLLOUTS`  
Created: 2026-07-11  
Review baseline: `1a61f0307130e19fedeabd95218293d9a5075fe1`  
Production baseline: `f3d7e8fedcdad5448abce5c74c1bdb698e5e82e6`  
Production Alembic: `0045 (head)`  
Source: `docs/reviews/CODE-REVIEW-CONSOLIDATED-2026-07-11.md`

## Goal

Исправить подтверждённые дефекты корректности, целостности данных, auth lifecycle и CI до добавления новых функций или следующего production rollout.

HC-015 — remediation milestone, а не продуктовая фича.

## Scope

В HC-015 входят:

1. устранение дублирующих Clinical Context summary/review routes;
2. синхронизация duplicate assessment/absorption с текущей схемой;
3. scanner-safe Email Magic Link и POST logout;
4. целостность `canonical_concept_id` и alias upsert;
5. полный frontend lint/typecheck и migration-cycle tests;
6. optimistic concurrency для void/review transitions;
7. единый error contract и сохранение `request_id`;
8. небольшие подтверждённые UI correctness fixes.

Не входят OCR, Labs, Oura, AI, новые медицинские функции, Pet Health и крупный редизайн.

## Delivery order

```text
Slice A — route cleanup
→ Slice B — duplicate resolution
→ Slice C — auth/logging
→ Slice D — dictionary integrity
→ Slice E — CI/migrations
→ Slice F — concurrency/frontend contracts
→ independent review
→ controlled rollout
```

Рекомендуемая ветка реализации: `fix/hc-015-code-review-remediation`.

## Slice A — Clinical Context route cleanup

### Required

- оставить одного владельца summary/review API;
- удалить перекрывающиеся legacy route registrations;
- удалить или скрыть legacy service methods с несовместимым response shape;
- сохранить только уникальные list/create/update/void/safety routes;
- добавить проверку уникальности method/path.

### Acceptance

- `GET /profiles/{profile_id}/clinical-context` всегда возвращает валидный `ClinicalContextSummary`;
- порядок `include_router` не влияет на результат;
- существует ровно один route для каждой summary/review операции;
- HTTP-level tests проходят через реальное FastAPI application.

## Slice B — Duplicate resolution schema sync

### Required

- учитывать `profile_clinical_reviews` и `profile_intake_decisions` как meaningful activity;
- проверить все profile-owned таблицы, добавленные после migration `0038`;
- не удалять автоматически review/intake data;
- повторно оценивать eligibility внутри той же транзакции перед absorption;
- возвращать controlled conflict вместо 500.

### Acceptance

- аккаунт с review или intake row не считается пустым;
- absorption для него не запускается;
- truly empty duplicate по-прежнему поглощается;
- FK violation не выходит наружу;
- PostgreSQL tests покрывают review-only, intake-only, combined, empty и concurrent cases.

## Slice C — Auth and logging

### Email Magic Link

Канонический flow:

```text
GET link → confirmation page → explicit POST consume → session → redirect
```

GET не должен поглощать одноразовый token. Должны сохраниться expiry, replay protection, rate limits и отсутствие user enumeration.

### Logout

- state-changing logout только по POST;
- GET не отзывает session;
- сохранить local-session revocation и same-origin protection.

### Account linking

Production configuration должна быть fail-safe: нельзя молча отключить защиту от duplicate creation отсутствующей переменной или неверным default.

### Logging

- корректный structured JSON или документированный safe plain format;
- `request_id` в operational errors;
- без raw query strings на auth routes;
- без tokens, cookies, authorization headers и медицинских значений.

### Tests

- scanner GET не consumes link;
- POST consumes once;
- replay и expiry отклоняются;
- logout GET не меняет state, POST отзывает session;
- unsafe production configuration не проходит startup/deploy check;
- log redaction regression.

## Slice D — Clinical dictionary integrity

### Required

- concept domain должен соответствовать clinical section;
- изменение/очистка `code` или `code_system` атомарно обновляет либо очищает `canonical_concept_id`;
- invalid UUID, unknown concept и domain mismatch отклоняются на DB boundary;
- alias upsert использует реальный business key, а не только deterministic UUID;
- runtime role не получает лишний UPDATE на derived canonical columns.

### Migration rules

- одна линейная Alembic revision от актуального head;
- никаких parallel heads;
- existing inconsistent rows должны быть repaired или migration должна остановиться;
- downgrade не должен ложно показывать старое revision state при сохранённых grants/functions.

### Tests

- positive и wrong-domain cases для всех четырёх sections;
- clear/change code transitions;
- repeated seed import;
- merge с pre-existing concept/alias business key;
- privilege negative test.

## Slice E — CI and migration safety

Обязательные frontend gates:

```text
npm run lint
npx tsc -p tsconfig.app.json --noEmit
npm test
npm run build
```

Обязательные backend/database gates:

- Ruff и backend unit tests;
- PostgreSQL RLS/integration tests;
- `upgrade head → downgrade base → upgrade head` в отдельной test database;
- targeted assertions для grants, functions и policies;
- production DB не используется автоматическими tests.

Acceptance: ошибка TypeScript или ESLint в любом `src/` файле должна падать в CI.

## Slice F — Concurrency and frontend contracts

### Required

- void принимает `expected_updated_at` или эквивалентную version precondition;
- `confirmed_none` атомарно проверяет отсутствие записей;
- stale/concurrent writes возвращают стабильный 409;
- backend и frontend используют единый error envelope либо явно поддерживаемый набор;
- frontend сохраняет и показывает `request_id` для поддержки;
- исправить очистку dose, date-only UTC shift, видимость complete-course errors и stale editor state.

### Tests

- stale void conflict;
- concurrent confirmed-empty/insert race;
- error envelope with request ID;
- date-only serialization минимум в двух timezones;
- clearing dose;
- editor reset between records.

## Security invariants

HC-015 не должен ослабить:

- direct Google OIDC и Email Magic Links без внешнего IAM;
- одну DB transaction на request для RLS context;
- runtime `NOBYPASSRLS` и `FORCE RLS`;
- запрет `PUBLIC EXECUTE` для sensitive definer functions;
- запрет silent merge только по verified email;
- запрет удаления последней identity;
- consent, provenance, audit и free-text fallback;
- запрет автоматических диагнозов и рекомендаций доз.

## Review gate

Перед merge обязательны:

1. review фактического diff;
2. green CI на exact PR head SHA;
3. ручная проверка migration SQL, grants, function ownership и RLS;
4. route-table uniqueness check;
5. проверка auth logs на утечку параметров;
6. сопоставление каждого finding с code/test либо письменным defer.

## Rollout

Merge не равен deployment. Отдельный rollout выполняется backup-first из точного approved commit:

1. зафиксировать production HEAD/Alembic before;
2. создать и проверить backup;
3. применить migration;
4. развернуть backend/frontend;
5. выполнить health, auth, Clinical Context и duplicate-resolution smoke tests;
6. проверить логи на 5xx, Traceback, `54001`, `42501` и FK errors;
7. зафиксировать production HEAD, Alembic, release path и backup.

## Stop conditions

Остановить merge или rollout, если:

- остаются duplicate routes;
- wrong-domain concept сохраняется;
- GET consumes Magic Link;
- duplicate resolution возвращает 500 или затрагивает meaningful data;
- появляется второй Alembic head;
- полный lint/typecheck обходится;
- downgrade оставляет DB в состоянии, не соответствующем revision;
- CI запускался не на exact deployed SHA;
- в логах появляются секреты или медицинские значения.

## Definition of done

HC-015 завершён только когда:

- обязательные tests всех slices зелёные;
- findings CR-01…CR-13, CR-18 и CR-19 закрыты либо письменно переклассифицированы с evidence;
- independent review не содержит unresolved High findings;
- изменения слиты в `main` и успешно развёрнуты;
- production HEAD/Alembic зафиксированы;
- обновлены `CURRENT-STATE.md`, `DEVELOPMENT-HISTORY.md`, `PROJECT-PLAN.md`, review register и source register;
- итоговый verdict изменён на `ACCEPT WITH FOLLOW-UP` или `READY`.

## Follow-up after HC-015

После снятия rollout gate отдельно планируются:

- indexed/trigram dictionary search;
- typeahead debounce и request cancellation;
- OIDC discovery/JWKS cache;
- CORS config cleanup;
- auth module decomposition;
- оставшийся UI polish;
- alias expansion из HC-014.
