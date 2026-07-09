# Health Compass — канонический план проекта

Версия: 1.3  
Дата: 2026-07-09  
Основная ветка: `main`

Этот документ — живой основной план проекта. Он обновляется после каждого завершённого этапа, архитектурного решения, внешнего ревью и production-проверки.

## 1. Цель

Создать многопользовательский защищённый портал персонального здоровья, который объединяет данные пользователя, лабораторные результаты, носимые устройства, медицинские документы и AI-помощника с обязательной опорой на источники и медицинские ограничения.

## 2. Источники плана

План сформирован на основе:

- `01-health-compass-master-plan.pdf`;
- `03-implementation-roadmap.xlsx`;
- `04-health-compass-vision-and-roadmap.pptx`;
- `14-unit-economics.xlsx`;
- `START-HERE.md`;
- ревью Fable по архитектуре, RLS, безопасности, продукту и интерфейсу;
- Fable Stage 3 Product/UX/AI artifacts;
- Fable Stage 3.5 UI Blueprint artifacts;
- Fable Stage 2.5 Progressive Health Intake artifacts;
- фактического кода, миграций, тестов и production-результатов.

Принятые продуктовые решения вынесены в `PRODUCT-UX-BASELINE.md` и `PROGRESSIVE-HEALTH-INTAKE.md`, техническая спецификация Slice 1 — в `BASIC-HEALTH-PROFILE-SLICE-1.md`, AI-ограничения — в `AI-PRODUCT-SAFETY.md`.

При расхождении приоритет источников:

1. код, миграции и тесты;
2. подтверждённое production-состояние;
3. ADR и security-инварианты;
4. этот план и канонические документы в `docs/`;
5. исходные PDF/XLSX/PPTX и внешние ревью.

## 3. Принципы

- Security first.
- PostgreSQL и RLS как граница изоляции пользователей.
- Никакого Authentik, Keycloak или внешнего IAM для MVP.
- Прямой Google OIDC и Email Magic Links.
- Собственные users, identities, sessions, workspaces, profiles и permissions.
- Одна транзакция на запрос для установки RLS-контекста.
- Все медицинские выводы должны быть объяснимы и связаны с источниками.
- Никаких автоматических диагнозов, назначений или расчёта доз.
- OCR-данные не становятся подтверждённым фактом без проверки пользователя.
- Human и Pet контуры разделены; Pet Health не блокирует Human MVP.
- Onboarding не блокируется большой медицинской анкетой.
- Медицинский контекст собирается прогрессивно и только по необходимости.
- Код изменяет ChatGPT/coding role; VPS-агент только разворачивает и обслуживает production.

## 4. Этапы

### PHASE-01 — Базовая платформа и production

Статус: `COMPLETED`

Реализовано:

- FastAPI + React/Vite;
- PostgreSQL и Alembic;
- production deployment;
- HTTPS;
- production на `https://health.funti.cc`;
- старый `/health` перенаправляется на новый домен;
- production разворачивается из `main`;
- health endpoints, журналирование и rollback;
- релиз `v0.1.0-auth-mvp`.

### PHASE-02 — Identity, sessions и tenant isolation

Статус: `COMPLETED`

Реализовано:

- Google OIDC с PKCE, state, nonce и `prompt=select_account`;
- Email Magic Links через Brevo;
- локальные PostgreSQL sessions;
- workspace/profile bootstrap;
- FORCE RLS;
- отдельная роль `health_compass_rls_definer`;
- устранение RLS-рекурсии;
- закрытие self-grant owner и self-add workspace escalation;
- двухпользовательская production-проверка tenant isolation;
- friendly page для использованной/просроченной magic link.

Отдельный backlog:

- scanner-safe magic-link landing/POST confirmation;
- автоматизированный обязательный двухпользовательский RLS regression suite.

### PHASE-02.5 — Progressive Health Intake

Статус: `SLICE 1 SPECIFIED / IMPLEMENTATION PENDING`

Цель: дать анализам и AI минимально необходимый контекст без блокирующей анкеты перед первым полезным действием.

Ключевое решение:

```text
Login
→ минимальный onboarding
→ Empty Dashboard / первое действие
→ добровольный Health Profile
→ контекстные дозапросы
→ подтверждённый импорт фактов из документов
```

Правила:

- имя профиля и необходимые согласия — обязательны;
- дата рождения и пол — опциональны;
- для MVP используется одно поле `sex` с label «Пол», без разделения пола и гендера;
- значения: `male`, `female`, `not_specified`;
- отсутствие данных не блокирует продукт;
- каждое поле объясняет, зачем оно нужно;
- intake не используется для самодиагностики;
- OCR и AI не меняют профиль без подтверждения пользователя.

#### Slice 1 — Basic Health Profile

- расширение существующей `health_compass.health_profiles`, без создания второй таблицы профиля;
- редактирование имени, даты рождения и пола;
- рост и timezone;
- история веса в `body_measurements`;
- минимальный consent gate перед сохранением медицинских данных;
- provenance и append-only audit trail;
- autosave стабильных полей;
- contextual readiness вместо health score;
- маршрут `/app/profile`;
- `app_can_edit_profile(uuid)`;
- RLS, column-level privileges и cross-user negative tests;
- регресс SQLSTATE `54001`;
- migration head `0021`, планируемая миграция `0022`.

Каноническая спецификация Slice 1: `docs/BASIC-HEALTH-PROFILE-SLICE-1.md`.

#### Slice 2 — Clinical Context

- состояния;
- аллергии;
- лекарства;
- витамины, минералы и БАДы;
- дозировки, единицы, частота, даты и статус;
- provenance, confirmation и audit.

#### Slice 3 — Contextual Intake

- `IntakePromptCard`;
- сохранить в профиль;
- использовать только для текущего анализа;
- не сейчас;
- `WhyWeAskPopover`;
- suppression повторного вопроса в одной сессии.

Analysis-only context не сохраняется как постоянный медицинский факт.

#### Slice 4 — переход к Documents/OCR

```text
Upload
→ Processing
→ OCR Review
→ Confirm
→ Lab Results
→ Metric Dynamics
→ Contextual Intake
→ AI Explanation with Evidence
→ Doctor Report
```

Не входят в Slice 1:

- состояния, аллергии, лекарства и добавки;
- `IntakePromptCard`;
- большая обязательная анкета;
- lifestyle-модули;
- семейный анамнез;
- полная emergency card;
- давление как generic measurement;
- автоматическая диагностика;
- автоматический импорт фактов из OCR;
- Pet intake.

Канонический продуктовый документ: `docs/PROGRESSIVE-HEALTH-INTAKE.md`.

### PHASE-03 — Human Documents, OCR и Labs

Статус: `PLANNED`

Первый продуктовый вертикальный срез:

```text
Login
→ Minimal Onboarding
→ Empty Dashboard
→ Upload Analysis
→ Processing
→ OCR Review
→ Lab Results
→ Metric Dynamics
→ Contextual Intake Prompt when needed
→ AI Explanation with Evidence
→ Doctor Report
```

Состав:

- загрузка PDF/изображений лабораторных результатов;
- очередь обработки;
- OCR с confidence и обязательным human confirmation;
- patient matching;
- provenance для каждого значения;
- lab results table;
- график динамики и reference band;
- контекстные уточнения только тогда, когда они меняют интерпретацию;
- подготовка данных для doctor report.

Frontend baseline:

1. AppShell, navigation и theme context.
2. Minimal onboarding, Health Profile entry point и Empty Dashboard.
3. Upload и processing status.
4. OCR Review с autosave draft.
5. Lab Results и Metric Dynamics.
6. Contextual Intake Prompt.
7. AI Assistant UI с EvidenceBlock.
8. Doctor Report.
9. Settings, sessions, privacy, export/delete.
10. Attention Inbox, search и notifications.

До появления реального импорта разрешены только явно помеченные демонстрационные данные.

### PHASE-04 — Источники данных и интеграции

Статус: `PLANNED`

- Oura OAuth и синхронизация;
- лабораторные PDF/CSV;
- Apple Health / Google Health Connect по отдельному решению;
- raw ingestion + нормализация;
- идемпотентность и курсоры синхронизации;
- data freshness и sync status;
- безопасная обработка bulk upload.

### PHASE-05 — Health timeline и аналитика

Статус: `PLANNED`

- единая временная шкала;
- тренды сна, активности, веса и лабораторных показателей;
- baseline пользователя;
- выявление значимых изменений;
- объяснимые карточки приоритетов;
- Attention Inbox;
- поиск по документам, показателям и timeline.

### PHASE-06 — Совместный доступ

Статус: `PLANNED`

- приглашения;
- роли owner/edit/analyze/view;
- отзыв доступа;
- аудит действий;
- отдельные политики RLS и негативные тесты для каждого сценария;
- caregiver mode и profile transfer только после отдельного threat review.

### PHASE-07 — Privacy и lifecycle данных

Статус: `PLANNED`

- полноценный consent center и версии текстов;
- управление активными сессиями;
- экспорт данных;
- удаление профиля;
- retention;
- аудит доступа;
- удаление raw, normalized, derived data и embeddings;
- отдельный consent для внешнего LLM.

Минимальный consent gate для записи базовых медицинских данных реализуется раньше, в Slice 1, и затем расширяется в PHASE-07.

### PHASE-08 — AI Health Assistant

Статус: `PLANNED`

- retrieval-grounded ответы;
- обязательные evidence/citations;
- Fact / Interpretation / Recommendation separation;
- red-flag маршрутизация;
- запрет опасных советов, диагнозов и расчёта доз;
- фильтрация retrieval по `profile_id` до поиска;
- отдельное согласие на внешний LLM;
- privacy-minimized `ai_runs`;
- `ai_evidence`, `ai_feedback`, `ai_safety_events`;
- prompt-injection tests для документов;
- versioned prompts и medical rules.

Реализация обязана соответствовать `AI-PRODUCT-SAFETY.md`.

### PHASE-09 — Расширение продукта

Статус: `BACKLOG`

- семейные профили;
- Pet Health только с отдельной моделью данных, prompts, norms и retrieval indices;
- clinician/caregiver workflows;
- Offline Emergency Card;
- подписка и unit economics;
- мобильное приложение/PWA.

## 5. Ближайший план

1. Создать feature-ветку Slice 1 от актуального `main`.
2. Реализовать migration `0022` и DB/RLS tests.
3. Расширить существующую модель профиля и добавить measurements/audit/consent models.
4. Реализовать API contracts Slice 1.
5. Реализовать `/app/profile`, autosave, readiness и историю веса.
6. Выполнить backend/frontend тесты и security review.
7. Обновить `CURRENT-STATE.md` и `DEVELOPMENT-HISTORY.md` после завершения реализации.
8. Не выполнять deployment до отдельного решения.
9. После Slice 1 перейти к Clinical Context.
10. После PHASE-02.5 перейти к Upload → Processing → OCR Review.

## 6. Правило обновления

После каждого этапа обязательно обновляются:

- `docs/CURRENT-STATE.md`;
- этот файл;
- `docs/DEVELOPMENT-HISTORY.md`;
- `docs/reviews/FABLE-RECOMMENDATIONS.md`;
- `docs/source-index/SOURCE-REGISTER.md`;
- `docs/PRODUCT-UX-BASELINE.md`, если изменился продуктовый или интерфейсный baseline;
- `docs/PROGRESSIVE-HEALTH-INTAKE.md`, если изменились intake-решения;
- `docs/BASIC-HEALTH-PROFILE-SLICE-1.md`, если изменились решения Slice 1;
- `docs/AI-PRODUCT-SAFETY.md`, если изменились AI-функции или safety rules;
- README, если изменились публичные URL, архитектура или запуск;
- ADR, если принято архитектурное решение.