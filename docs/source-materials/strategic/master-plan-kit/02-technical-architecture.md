# 02 — Техническая архитектура Health Compass

Версия: 1.0 · Дата: 2026-07-08
Входные данные: архив ветки `feat/direct-google-and-email-auth` (без `.git`, HEAD неизвестен — зафиксировать при следующем ревью), предыдущие ревью, описание владельца.
Связанные файлы: `01-health-compass-master-plan.md`, `06-data-model.md`, `07-security-and-threat-model.md`, `10-machine-readable-roadmap.yaml`, `11-adr/`.

---

## 1. Фактическое состояние (по коду архива, не по README)

### 1.1 Backend (реализовано)

* FastAPI + SQLAlchemy 2 (async, `asyncpg` runtime / `psycopg` для миграций), Alembic (21 миграция, head = `0021`).
* Схема `health_compass`: `users`, `user_identities`, `auth_sessions`, `workspaces`, `workspace_members`, `health_profiles`, `profile_permissions`, `invitations`, `dashboard_snapshots`, `email_login_tokens`, служебные таблицы (`service_metadata`, `audit_events`, `processing_jobs` — модели есть, использование минимально).
* Аутентификация: прямой Google OIDC (PKCE, state/nonce в коротких cookies, проверка `email_verified`) и Email Magic Links (SHA-256 hash токена, rate-limit в SECURITY DEFINER функции, одноразовое потребление).
* Identity — строго `(provider, subject)`; `users.email` не уникален (миграция `0018` сняла unique — верно).
* Сессии: серверные, в `auth_sessions`, cookie `hc_session` (Secure, HttpOnly, SameSite=Lax, path=/health/api), TTL 12 ч, hash SHA-256.
* RLS: включён и `FORCE` на всех identity/tenant-таблицах (`0015`); helper-функции переведены на выделенную роль `health_compass_rls_definer` (NOLOGIN, BYPASSRLS) с `SECURITY DEFINER`, `SET search_path = ''`, `SET row_security = off` (`0020`, `0021`).
* Одна транзакция на запрос (`get_session` оборачивает запрос в `session.begin()`); RLS-контекст ставится `set_config(..., true)` — транзакционно-локально. Это правильная и важная инварианта.
* Dev-auth через заголовок `X-Health-Compass-User-Id` — только `allow_dev_auth && is_development && localhost`; `validate_production()` запрещает вне development.
* Тесты: конфигурация с защитой от prod-БД (имя БД обязано оканчиваться на `_test`), тесты миграций, OIDC, ошибок. Интеграционных RLS-тестов на изоляцию арендаторов НЕТ — пробел.

### 1.2 Frontend (реализовано)

React 18 + Vite + shadcn/ui + Recharts. Страницы Dashboard/History/Genetics/Oura/Sources/ActionPlan работают на статических демо-данных из `src/data/demo.ts`; к API подключён только auth-контур. `DemoBanner` присутствует.

### 1.3 Противоречия документации (обязательный раздел)

| # | Документ | Утверждение | Фактическое состояние | Уверенность |
|---|---|---|---|---|
| C-1 | `docs/current-architecture.md` | «Backend ❌ Отсутствует», «Авторизация ❌», mock-логин | Backend, БД, RLS и две схемы аутентификации реализованы | Высокая (код + миграции) |
| C-2 | `docs/authentication-roadmap.md` | Рекомендован Authentik | Ветка реализует прямой Google OIDC + magic links; Authentik — архивная ветка | Высокая |
| C-3 | `README.md` | Актуальная архитектура | Ближе к правде, но не описывает RLS-роль `health_compass_rls_definer` и email_login_tokens | Средняя |
| C-4 | `backend/IDENTITY_STAGE.md` | Промежуточный этап | Частично устарел | Средняя |

**Source of truth:** код + Alembic-миграции. Действие: задача HC-004 — переписать `docs/current-architecture.md` и `docs/authentication-roadmap.md`, добавить `docs/source-of-truth-status.md` (входит в PHASE-01).

---

## 2. Разбор инцидента `StatementTooComplex` (SQLSTATE 54001)

### 2.1 Причинная цепочка (подтверждена кодом)

1. `0006` создала helper-функции (`app_can_view_profile`, `app_has_workspace_access`) как `SECURITY DEFINER`; владелец — `health_compass_migrator`, который владеет таблицами.
2. Политика `profile_access_select` на `profile_permissions` вызывает `app_can_view_profile(profile_id)`, которая сама читает `profile_permissions`.
3. До `0015` владелец таблиц неявно обходил RLS ⇒ вызов изнутри definer-функции не срабатывал по политике ⇒ рекурсии не было.
4. `0015` включила `FORCE ROW LEVEL SECURITY` ⇒ RLS стал применяться и к владельцу ⇒ запрос внутри функции снова активировал политику ⇒ политика снова вызвала функцию ⇒ бесконечная рекурсия ⇒ `stack depth limit exceeded` на `INSERT INTO profile_permissions` при первом реальном Google-входе.
5. `0020`/`0021` разорвали цикл: функции переведены во владение `health_compass_rls_definer` (BYPASSRLS) + `SET row_security = off`, `search_path=''`, полностью квалифицированные имена, `REVOKE FROM PUBLIC`, EXECUTE только `health_compass_app`; добавлены нерекурсивные политики `pp_self_select`, `wm_self_select`; bootstrap-INSERT-политики ужесточены (`pp_owner_bootstrap_insert` требует `permission='owner'` И `app_owns_profile`; `wm_creator_bootstrap_insert` требует `role='owner'` И `app_created_workspace`) — закрыты self-grant и self-add.

### 2.2 Оценка выбранного решения и альтернативы

Выбранная модель (`health_compass_rls_definer` NOLOGIN + BYPASSRLS + row_security=off + фиксированный search_path + минимальные SELECT-права) — **корректна и является отраслевым стандартом** для PostgreSQL RLS с helper-функциями. Замечания и альтернативы:

1. **Альтернатива A (рекомендуемая к рассмотрению до масштабирования): избавиться от FORCE RLS на большинстве таблиц.** `FORCE` защищает только от обхода владельцем; runtime-роль `health_compass_app` не владеет таблицами, поэтому обычный `ENABLE RLS` уже полностью её ограничивает. FORCE полезен как defense-in-depth против случайного запуска кода под migrator, но именно он спровоцировал инцидент. Решение: оставить FORCE (глубокая защита ценна для медицинских данных), но зафиксировать в ADR-007, что каждая новая политика обязана проходить тест на рекурсию (см. HC-002).
2. **Альтернатива B: полностью нерекурсивные политики без definer-функций** — политики на `profile_permissions`/`workspace_members` только вида `user_id = app_current_user_id()`, а «объектные» проверки — на прикладном уровне. Дешевле и переносимее (нет BYPASSRLS), но переносит гарантии из БД в приложение. Не рекомендуется как основной путь для медицинских данных; допустима для некритичных таблиц.
3. **Замечание Z-1:** `app_current_user_id()`/`app_current_session_hash()` не обращаются к таблицам — им не нужны `SECURITY DEFINER`/`BYPASSRLS` (внесено `0021` «на всякий случай»). Безопасно, но избыточные привилегии противоречат принципу минимализма; допустимо вернуть INVOKER (низкий приоритет, HC-019).
4. **Замечание Z-2:** миграции `0020`/`0021` требуют предсозданную роль (fail-fast с понятным сообщением) — хороший паттерн; внести провижининг роли в deployment-runbook и в проверки VPS-агента.

### 2.3 Оставшиеся дефекты RLS (найдены в коде, требуют исправления в PHASE-01)

| ID | Дефект | Где | Риск |
|---|---|---|---|
| RISK-001 | `users_oidc_insert ... WITH CHECK (true)` — любой запрос под app-ролью может вставлять произвольные строки в `users` | `0009`/`0012`, действует | Замусоривание, преднамеренные коллизии email, обход инварианты «user создаётся только auth-потоком». Заменить на `WITH CHECK (id = app_current_user_id())` (код уже ставит контекст до INSERT). |
| RISK-002 | `dashboard_owner_insert WITH CHECK (app_can_view_profile(profile_id))` — право `view` позволяет ПИСАТЬ снапшоты | `0013` | Эскалация внутри профиля: наблюдатель изменяет то, что видит владелец. Требовать `edit`/`owner`. |
| RISK-003 | `profile_access_select USING app_can_view_profile(profile_id)` — любой viewer видит все грант-записи профиля | `0006` | Утечка списка людей с доступом. Сузить до owner-профиля + self (`pp_self_select` уже есть). |
| RISK-004 | Нет DELETE/UPDATE политик для отзыва прав, нет политики добавления ДРУГИХ участников (invitations-поток не реализован) | все версии | Функциональный пробел: шаринг невозможен безопасно. |
| RISK-005 | `workspace_access_select` (через функцию) и `wm_self_select` дублируются | `0006`+`0020` | Не дефект безопасности; упростить и задокументировать целевую матрицу политик. |
| RISK-006 | Bootstrap (`services/bootstrap.py`) вставляет каждому новому пользователю ФЕЙКОВЫЙ dashboard: «Подтвердить предполагаемый Factor V Leiden», выдуманные сон/активность | код | Медицинская безопасность: реальный пользователь видит вымышленный генетический риск как свой. Блокер продукта: убрать демо-данные из bootstrap, пустое состояние + onboarding. |
| RISK-007 | Нет фонового удаления протухших `auth_sessions` и `email_login_tokens` | код | Рост таблиц, устаревшие хэши. Добавить janitor-job. |
| RISK-008 | CSRF: колонка `csrf_token_hash` есть, механизм не реализован; logout доступен GET-ом | код | SameSite=Lax закрывает основное, но state-changing POST API потребуют CSRF-токен до расширения API. |
| RISK-009 | Magic-link consume — GET: корпоративные сканеры писем дожигают одноразовые ссылки | `email_auth.py` | Ложные «ссылка недействительна». Интерстициальная страница + POST-consume. |
| RISK-010 | Нормализация email различается: Google-путь `strip().lower()`, email-путь `casefold()` | код | Редкие расхождения Unicode. Единая `normalize_email`. |
| RISK-011 | Google re-login перезаписывает `user.email` без проверки коллизий с email-identity другого пользователя | `auth.py` | Дубликаты по design допустимы, но нужен UX связывания аккаунтов (ADR-003), иначе пользователи «теряют» данные между двумя своими аккаунтами. |
| RISK-012 | Интеграционных тестов изоляции RLS нет (двухпользовательские сценарии) | tests | Регрессии политик незаметны. HC-002 — обязательный тестовый пакет. |

---

## 3. Целевая архитектура (modular monolith)

Микросервисы для MVP не вводятся (ADR-001). Целевые модули внутри одного backend:

```
app/
  core/          config, security, oidc, magic_links, request_id, logging
  db/            session, rls, base
  modules/
    identity/    users, identities, sessions, linking
    tenancy/     workspaces, members, invitations, permissions
    profiles/    health_profiles (human), pets (veterinary)
    documents/   files, versions, extractions, provenance
    labs/        lab_reports, result_items, test_definitions (human/vet раздельные справочники)
    measurements/
    timeline/    materialized medical/vet events
    wearables/   provider connections, sync, raw events, normalized metrics
    ai/          conversations, runs, evidence, safety events
    reports/
    billing/     plans, entitlements, quotas (позже)
  workers/       arq-джобы: ocr, ai, wearable_sync, notifications, janitor, exports
```

### 3.1 Компоненты и технологии (зачем / этап / альтернативы / цена отказа)

| Технология | Зачем | Этап | Альтернатива | Цена сложности | Последствия отказа |
|---|---|---|---|---|---|
| PostgreSQL (есть) | Основное хранилище + RLS | сейчас | — | — | — |
| Очередь: **ARQ + Redis** | OCR/AI/sync — не в HTTP-запросе | PHASE-04 | Постгрес-очередь (`processing_jobs` уже есть) — допустимо до Redis | Redis = ещё один сервис на VPS | Синхронные загрузки → таймауты |
| Постгрес-очередь (SKIP LOCKED) | Стартовый вариант без Redis | PHASE-04 | ARQ | Меньше инфраструктуры | Ограничения по throughput — на MVP не важны |
| Object storage: локальная FS → **S3-совместимое (MinIO или внешний S3)** | Файлы документов вне БД | PHASE-04 (FS), PHASE-07+ (S3) | Хранить bytea в PG — не рекомендуется | MinIO = сервис + бэкапы | Раздутая БД, дорогие бэкапы |
| ClamAV | Антивирус загрузок | PHASE-04 | Отказ от проверки | ~1 ГБ RAM | Malware в хранилище, риск для экспорта |
| OCR: Tesseract (rus+eng) → внешний Vision API по флагу | Извлечение из сканов | PHASE-05 | Только внешний API | Точность Tesseract ниже | Ручной ввод всего |
| pgvector | Embeddings для grounding AI | PHASE-08 | Внешняя векторная БД — не нужна | Расширение PG | AI без цитат по документам |
| TimescaleDB | НЕ вводить на MVP | — | Обычные таблицы + BRIN-индексы | — | Достаточно до миллионов точек |
| Sentry (self-hosted или SaaS без PII) | Ошибки | PHASE-02 | Логи | Настройка scrubbing | Слепота к продовым ошибкам |
| Prometheus + Grafana | Метрики | PHASE-02 (минимум: systemd + healthcheck), полноценно PHASE-07 | Uptime-мониторинг | Ещё сервисы | Нет наблюдаемости sync/джоб |
| OpenTelemetry | Трассировка | после MVP | — | — | — |
| CI: GitHub Actions | Тесты + линт + миграционный прогон на каждый PR | PHASE-02 | — | — | Регрессии RLS доезжают до prod |

### 3.2 Инварианты (обязаны соблюдаться всеми агентами)

1. Один HTTP-запрос = одна транзакция; `set_config(..., true)`; никакого commit внутри до конца запроса.
2. Runtime-роль `health_compass_app` никогда не владеет таблицами; DDL — только `health_compass_migrator` через Alembic.
3. Каждая новая таблица с пользовательскими данными: `ENABLE`+`FORCE RLS` + политики в той же миграции + rls-тест в том же PR.
4. Helper-функции RLS: владелец `health_compass_rls_definer`, `SECURITY DEFINER`, `search_path=''`, `row_security=off`, полные имена, `REVOKE FROM PUBLIC`.
5. Identity = `(provider, subject)`; email никогда не объединяет аккаунты автоматически.
6. Human- и pet-домены не делят справочники норм, дозировок и AI-промты (ADR-018).
7. Никаких демо/фейковых медицинских данных в реальных профилях.
8. Production меняется только VPS-агентом по runbook, код — только из Git.

### 3.3 Deployment (текущий + целевой)

Текущий: Apache (funti.cc) → SPA статикой из `/opt/health-compass/current`, backend `health-compass-api.service` на 127.0.0.1:8100, env в `/etc/health-compass/backend.env`. `de.funti.cc` — НЕ production; каждая инструкция VPS-агенту начинается с проверок hostname/IP/каталога/сервиса/branch/HEAD/чистоты дерева/`alembic current`/целевой БД (см. `09-agent-prompts/vps-agent-prompts.md`).

Целевые добавления по этапам: PHASE-02 — CI, staging-БД, backup-скрипт с проверкой восстановления; PHASE-04 — воркер (systemd unit `health-compass-worker.service`), каталог файлов с квотами; PHASE-07 — Redis, мониторинг; PHASE-08 — pgvector, внешние LLM-ключи в отдельном secret-файле с минимальными правами.

---

## 4. Порядок стабилизации (PHASE-01, блокеры)

1. HC-001 — верифицировать применённость `0020`/`0021` на prod, e2e Google-вход и magic link на живой БД (VPS-агент, только чтение + smoke).
2. HC-002 — интеграционные RLS-тесты: два пользователя, изоляция SELECT/INSERT/UPDATE по всем 10 таблицам, регресс-тест рекурсии (INSERT в `profile_permissions` при FORCE RLS), тест self-grant/self-add.
3. HC-003 — миграция `0022`: RISK-001 (users insert), RISK-002 (dashboard insert = edit|owner), RISK-003 (сужение profile_permissions select).
4. HC-005 — удалить демо-данные из bootstrap (RISK-006), пустое состояние на фронте.
5. HC-004 — привести документацию к правде (см. §1.3).
6. HC-006 — janitor-job (протухшие сессии/токены), единая normalize_email, интерстициал magic-link.

Полная детализация этапов и задач — `03-implementation-roadmap.xlsx` и `10-machine-readable-roadmap.yaml`.
