# Health Compass — канонический план проекта

Версия: 1.0  
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
- фактического кода, миграций, тестов и production-результатов.

При расхождении приоритет источников:

1. код, миграции и тесты;
2. подтверждённое production-состояние;
3. ADR и security-инварианты;
4. этот план и `CURRENT-STATE.md`;
5. исходные PDF/XLSX/PPTX и внешние ревью.

## 3. Принципы

- Security first.
- PostgreSQL и RLS как граница изоляции пользователей.
- Никакого Authentik, Keycloak или внешнего IAM для MVP.
- Прямой Google OIDC и Email Magic Links.
- Собственные users, identities, sessions, workspaces, profiles и permissions.
- Одна транзакция на запрос для установки RLS-контекста.
- Все медицинские выводы должны быть объяснимы и связаны с источниками.
- Никаких автоматических диагнозов и назначений.
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

### PHASE-03 — Профиль и ввод данных

Статус: `PLANNED`

- персональные данные;
- цели и ограничения;
- заболевания, лекарства, аллергии;
- ручной ввод показателей;
- загрузка документов и лабораторных результатов;
- data provenance для каждого значения.

Пока реальный импорт не готов, разрешены только явно помеченные демонстрационные данные.

### PHASE-04 — Источники данных и интеграции

Статус: `PLANNED`

- Oura OAuth и синхронизация;
- лабораторные PDF/CSV;
- Apple Health / Google Health Connect по отдельному решению;
- raw ingestion + нормализация;
- идемпотентность и курсоры синхронизации.

### PHASE-05 — Health timeline и аналитика

Статус: `PLANNED`

- единая временная шкала;
- тренды сна, активности, веса и лабораторных показателей;
- baseline пользователя;
- выявление значимых изменений;
- объяснимые карточки приоритетов.

### PHASE-06 — Совместный доступ

Статус: `PLANNED`

- приглашения;
- роли owner/edit/analyze/view;
- отзыв доступа;
- аудит действий;
- отдельные политики RLS и негативные тесты для каждого сценария.

### PHASE-07 — Privacy и lifecycle данных

Статус: `PLANNED`

- consents;
- экспорт данных;
- удаление профиля;
- retention;
- аудит доступа;
- удаление derived data и embeddings.

### PHASE-08 — AI Health Assistant

Статус: `PLANNED`

- retrieval-grounded ответы;
- обязательные evidence/citations;
- red-flag маршрутизация;
- запрет опасных советов;
- отсутствие диагноза без врача;
- фильтрация retrieval по `profile_id` до поиска;
- отдельное согласие на внешний LLM.

### PHASE-09 — Расширение продукта

Статус: `BACKLOG`

- семейные профили;
- pet health contour только с отдельной моделью данных и нормами;
- clinician/caregiver workflows;
- подписка и unit economics;
- мобильное приложение/PWA.

## 5. Ближайший план

1. Закрепить документацию и source-of-truth в GitHub.
2. Изменить код для корневого поддомена `health.funti.cc`.
3. Развернуть поддомен параллельно старому `/health`.
4. Проверить Google, Email Magic Link, logout, refresh маршрутов и RLS.
5. Включить редирект со старого URL.
6. Создать PR `feat/direct-google-and-email-auth → main`.
7. Выпустить тег `v0.1.0-auth-mvp`.
8. Начать PHASE-03: реальные пользовательские данные и источники.

## 6. Правило обновления

После каждого этапа обязательно обновляются:

- `docs/CURRENT-STATE.md`;
- этот файл;
- `docs/DEVELOPMENT-HISTORY.md`;
- `docs/reviews/FABLE-RECOMMENDATIONS.md`;
- README, если изменились публичные URL, архитектура или запуск;
- ADR, если принято архитектурное решение.
