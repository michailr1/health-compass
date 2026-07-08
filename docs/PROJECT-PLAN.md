# Health Compass — канонический план проекта

Версия: 1.1  
Дата: 2026-07-09  
Рабочая ветка: `feat/direct-google-and-email-auth`

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
- фактического кода, миграций, тестов и production-результатов.

Принятые продуктовые решения вынесены в `PRODUCT-UX-BASELINE.md`, AI-ограничения — в `AI-PRODUCT-SAFETY.md`.

При расхождении приоритет источников:

1. код, миграции и тесты;
2. подтверждённое production-состояние;
3. ADR и security-инварианты;
4. этот план, `CURRENT-STATE.md`, `PRODUCT-UX-BASELINE.md` и `AI-PRODUCT-SAFETY.md`;
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
- Код изменяет ChatGPT/coding role; VPS-агент только разворачивает и обслуживает production.

## 4. Этапы

### PHASE-01 — Базовая платформа и production

Статус: `IN PROGRESS`

Включает:

- FastAPI + React/Vite;
- PostgreSQL и Alembic;
- production deployment;
- HTTPS;
- перенос на `https://health.funti.cc`;
- health endpoints, журналирование и rollback.

Критерий завершения:

- поддомен работает;
- старый `/health` перенаправляется;
- production разворачивается из `main`;
- README и runbook актуальны.

### PHASE-02 — Identity, sessions и tenant isolation

Статус: `IMPLEMENTED / VERIFYING RELEASE`

Реализовано:

- Google OIDC с PKCE, state, nonce и `prompt=select_account`;
- Email Magic Links через Brevo;
- локальные PostgreSQL sessions;
- workspace/profile bootstrap;
- FORCE RLS;
- отдельная роль `health_compass_rls_definer`;
- устранение RLS-рекурсии;
- закрытие self-grant owner и self-add workspace escalation;
- 22 интеграционные проверки без ошибок.

Осталось:

- scanner-safe magic-link landing/POST confirmation;
- формальный релизный PR в `main`;
- автоматизировать обязательный двухпользовательский RLS regression suite.

### PHASE-03 — Human profile и ввод данных

Статус: `PLANNED`

Первый продуктовый вертикальный срез:

```text
Login
→ Onboarding
→ Empty Dashboard
→ Upload Analysis
→ Processing
→ OCR Review
→ Lab Results
→ Metric Dynamics
→ AI Explanation with Evidence
→ Doctor Report
```

Состав:

- персональные данные;
- цели и ограничения;
- заболевания, лекарства и аллергии;
- ручной ввод показателей;
- загрузка PDF/изображений лабораторных результатов;
- очередь обработки;
- OCR с confidence и обязательным human confirmation;
- provenance для каждого значения;
- lab results table;
- график динамики и reference band;
- подготовка данных для doctor report.

Frontend baseline:

1. AppShell, navigation и theme context.
2. Auth UI и onboarding.
3. Empty Dashboard.
4. Upload и processing status.
5. OCR Review с autosave draft.
6. Lab Results и Metric Dynamics.
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

- consents;
- управление активными сессиями;
- экспорт данных;
- удаление профиля;
- retention;
- аудит доступа;
- удаление raw, normalized, derived data и embeddings;
- отдельный consent для внешнего LLM.

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

1. Завершить перенос на root-domain `health.funti.cc`.
2. Развернуть поддомен параллельно старому `/health`.
3. Проверить Google, Email Magic Link, logout, refresh маршрутов, cookie paths и RLS.
4. Включить redirect со старого URL.
5. Создать PR `feat/direct-google-and-email-auth → main`.
6. Выпустить тег `v0.1.0-auth-mvp`.
7. Утвердить API contracts первого PHASE-03 vertical slice.
8. Реализовать frontend foundation и Empty Dashboard.
9. Реализовать Upload → Processing → OCR Review.
10. Реализовать Lab Results → Metric Dynamics → Doctor Report.
11. AI explanation подключать только после evidence enforcement и consent model.

## 6. Правило обновления

После каждого этапа обязательно обновляются:

- `docs/CURRENT-STATE.md`;
- этот файл;
- `docs/DEVELOPMENT-HISTORY.md`;
- `docs/reviews/FABLE-RECOMMENDATIONS.md`;
- `docs/PRODUCT-UX-BASELINE.md`, если изменился продуктовый или интерфейсный baseline;
- `docs/AI-PRODUCT-SAFETY.md`, если изменились AI-функции или safety rules;
- README, если изменились публичные URL, архитектура или запуск;
- ADR, если принято архитектурное решение.
