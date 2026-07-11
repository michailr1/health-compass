# Fable 5 — независимое code review Health Compass

Дата: 2026-07-11  
Проверенный repository HEAD: `1a61f0307130e19fedeabd95218293d9a5075fe1`  
Ветка ревьюера: `claude/health-compass-code-review-ge02a8`  
Статус рабочего дерева при ревью: clean  
Вердикт: `FIX BEFORE ROLLOUT`

## 1. Область проверки

Проверялись фактические:

- backend и frontend;
- Alembic migrations;
- PostgreSQL RLS policies и grants;
- `SECURITY DEFINER` functions;
- Google OIDC, Email Magic Link, sessions и account linking;
- Clinical Context и Clinical Dictionaries;
- тесты и CI.

Документация использовалась только как справочный материал. Выводы ниже основаны на коде, миграциях и контрактах.

## 2. Executive summary

Архитектура изоляции данных сильная для проекта текущего масштаба. Подтверждены:

- `FORCE ROW LEVEL SECURITY` на tenant-таблицах;
- runtime role с `NOBYPASSRLS`;
- отдельная `NOLOGIN BYPASSRLS` роль для ограниченных helper-функций;
- `search_path=''`, `row_security=off` и отзыв `PUBLIC EXECUTE`;
- отсутствие подтверждённого cross-user leak или self-escalation;
- PKCE, state, nonce, issuer/audience/azp и verified-email checks в OIDC;
- одноразовость и rate limiting Magic Link;
- append-only audit, consent gate, provenance и immutable voided rows для клинических данных.

При этом перед следующим production rollout необходимо исправить дефекты корректности и целостности Clinical Context и duplicate resolution, а также усилить CI.

## 3. Findings

### FBL-01 — дублированные и контрактно несовместимые summary/review routes

Severity: `HIGH`  
Классификация: подтверждено кодом; архитектурный риск

Факты:

- `backend/app/services/clinical_context.py` содержит legacy `get_summary()` с полями `reviewed`, `confirmed_empty`, `reviewed_at`, `active_count`, `total_count`;
- `backend/app/api/routes/clinical_context.py` регистрирует `GET /profiles/{id}/clinical-context` и review route с `response_model=ClinicalContextSummary`;
- `ClinicalContextSummary` требует `review_state`, `effective_state`, `active_count`, `history_count`;
- корректная новая реализация находится в `backend/app/services/clinical_review.py` и `backend/app/api/routes/clinical_review.py`;
- рабочее поведение сейчас зависит от того, что `clinical_review_router` подключён раньше legacy router.

Риск:

Любая перестановка router registration, удаление нового router или рефакторинг может открыть legacy route и привести к `ResponseValidationError` / HTTP 500 на основном чтении Clinical Context.

Требуемое исправление:

- оставить один канонический summary/review implementation;
- удалить либо сделать недоступными legacy routes и service methods;
- добавить HTTP-level regression test через реальное FastAPI application.

### FBL-02 — duplicate activity/absorption не учитывает новые clinical tables

Severity: `MEDIUM` с блокирующим rollout-эффектом  
Классификация: подтверждено кодом; итоговый HTTP 500 требует runtime regression test

Факты:

- `app_duplicate_user_activity` не учитывает `profile_clinical_reviews` и `profile_intake_decisions`;
- `app_apply_duplicate_absorption` не удаляет эти строки;
- обе таблицы имеют `profile_id ... REFERENCES health_compass.health_profiles(id)` без `ON DELETE CASCADE`.

Сценарий:

1. Пользователь создаёт review/intake state в одном аккаунте.
2. Второй способ входа создаёт duplicate candidate.
3. Аккаунт ошибочно классифицируется как пустой.
4. Absorption пытается удалить `health_profiles`.
5. FK `RESTRICT` блокирует удаление, транзакция откатывается и flow завершается ошибкой.

Требуемое исправление:

Консервативно считать presence строк `profile_clinical_reviews` и `profile_intake_decisions` meaningful activity. Автоматическое удаление таких данных не использовать.

Обязательный тест:

PostgreSQL integration test, где absorbed account содержит одну review/intake row и получает controlled conflict, а не 500.

### FBL-03 — canonical concept может принадлежать неверному домену

Severity: `MEDIUM`  
Классификация: подтверждено кодом

Факты:

- API принимает свободные `code_system` и `code`;
- trigger преобразует UUID из `code` в `canonical_concept_id` для `code_system='health_compass'`;
- FK проверяет существование concept, но не соответствие domain таблице.

Сценарий:

Condition может ссылаться на medication concept, medication — на supplement concept и так далее.

Последствие:

Некорректная каноническая семантика может попасть в аналитику, retrieval и AI context.

Требуемое исправление:

- database-level domain validation;
- rejection mismatch;
- positive/negative API and PostgreSQL tests.

### FBL-04 — CI не выполняет полный TypeScript typecheck и полный lint

Severity: `MEDIUM`  
Классификация: подтверждено кодом

Факты:

- frontend build использует Vite/SWC и не заменяет `tsc --noEmit`;
- CI запускает ESLint только для фиксированного списка файлов;
- новые страницы, context и Clinical Context components могут не попасть в lint gate.

Требуемое исправление:

- `npm run lint` или `eslint .` для всего frontend source;
- `tsc -p tsconfig.app.json --noEmit`;
- оба шага должны быть обязательными CI gates.

### FBL-05 — downgrade migration coverage поверхностный

Severity: `LOW`  
Классификация: пробел тестов

Текущие tests проверяют отдельную старую границу и один `downgrade -1` от head, но не полный цикл `head → base → head`.

Требуемое исправление:

Добавить отдельный slow/integration job полного migration cycle на временной PostgreSQL DB.

### FBL-06 — избыточный UPDATE grant на users

Severity: `LOW`  
Классификация: defense in depth; через текущий API не подтверждена достижимость

Runtime role имеет табличный `UPDATE`, а self-update policy не ограничивает колонки. Следует перейти на column-level grants и явно запретить изменение identity-critical полей, включая email и status.

### FBL-07 — logout по GET

Severity: `LOW`  
Классификация: подтверждено кодом

`GET /api/auth/logout` изменяет server state и может быть вызван cross-site top-level navigation при `SameSite=Lax`.

Требуемое исправление:

Logout только через POST с Origin/CSRF protection либо эквивалентным подтверждением.

### FBL-08 — неиспользуемая CORS configuration

Severity: `LOW`  
Классификация: техдолг

`cors_origins` присутствует в settings, но `CORSMiddleware` не подключён. При текущем same-origin deployment это не functional bug, однако конфигурация вводит в заблуждение.

### FBL-09 — dictionary search не использует подготовленные индексы

Severity: `LOW`  
Классификация: производительность/техдолг

Поиск нормализует `display_name`/`alias_text` во время запроса и использует contains search с ведущим `%`, поэтому обычные индексы на `normalized_text` не дают ожидаемого эффекта.

## 4. Положительные подтверждённые свойства

- tenant isolation построен на PostgreSQL RLS, а не только на application checks;
- sensitive helper functions ограничены отдельным owner и explicit grants;
- OIDC verification включает PKCE, state, nonce, issuer, audience, azp и email verification;
- account linking использует browser binding и повторную оценку перед absorption;
- нельзя удалить последнюю identity;
- Clinical Context использует consent, audit, provenance, void и optimistic concurrency;
- seed import валидируется, versioned и идемпотентен по concept business key;
- CI использует PostgreSQL 16 integration environment для migrations и RLS tests.

## 5. Ограничения ревью

Не были подтверждены runtime-проверкой:

- реальный HTTP status duplicate absorption failure;
- production role provisioning;
- reverse-proxy security headers;
- реальные SMTP/OIDC interactions;
- полный локальный запуск frontend typecheck и всей test suite.

## 6. Итоговый вердикт

`FIX BEFORE ROLLOUT`.

Минимальный обязательный набор до продолжения rollout:

1. устранить duplicate summary/review routes;
2. синхронизировать duplicate activity/absorption с `profile_clinical_reviews` и `profile_intake_decisions`;
3. обеспечить domain integrity `canonical_concept_id`;
4. добавить полный TypeScript typecheck и full-source lint.

Findings FBL-05…FBL-09 допускаются как follow-up только после фикса первых четырёх и обязательных regression tests.
