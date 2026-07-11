# Health Compass — канонический план проекта

Версия: 1.4  
Дата: 2026-07-11  
Основная ветка: `main`

Этот документ — живой основной план проекта. Он обновляется после завершённых этапов, архитектурных решений, внешних ревью и production-проверок.

## 1. Цель

Создать многопользовательский защищённый портал персонального здоровья, который объединяет данные пользователя, лабораторные результаты, носимые устройства, медицинские документы и AI-помощника с обязательной опорой на источники и медицинские ограничения.

## 2. Источники плана

План сформирован на основе:

- `01-health-compass-master-plan.pdf`;
- `03-implementation-roadmap.xlsx`;
- `04-health-compass-vision-and-roadmap.pptx`;
- `14-unit-economics.xlsx`;
- `START-HERE.md`;
- Fable Stage 2.5, 3 и 3.5 artifacts;
- прежних Fable reviews по RLS, product и operations;
- двух независимых code review от 2026-07-11;
- фактического кода, миграций, tests и production evidence.

Канонические результаты review 2026-07-11:

- `docs/reviews/CODE-REVIEW-CONSOLIDATED-2026-07-11.md`;
- `docs/reviews/FABLE-5-INDEPENDENT-CODE-REVIEW-2026-07-11.md`;
- `docs/implementation/HC-015-CODE-REVIEW-REMEDIATION.md`.

При расхождении приоритет источников:

1. код, migrations и tests;
2. подтверждённое production state;
3. ADR и security invariants;
4. этот план и канонические Markdown documents;
5. исходные PDF/XLSX/PPTX и внешние reviews.

## 3. Принципы

- Security first.
- PostgreSQL и RLS как boundary изоляции пользователей.
- Никакого Authentik, Keycloak или внешнего IAM для MVP.
- Direct Google OIDC и Email Magic Links.
- Собственные users, identities, sessions, workspaces, profiles и permissions.
- Одна DB transaction на request для RLS context.
- Verified email само по себе не объединяет аккаунты.
- Медицинские данные требуют consent, provenance и audit.
- Free-text health input остаётся доступным и не переписывается молча.
- Никаких автоматических диагнозов, назначений или расчёта доз.
- OCR/AI данные не становятся подтверждённым фактом без user confirmation.
- Health intake прогрессивный и не блокирует первое полезное действие.
- Human и Pet contours разделены.
- Coding role меняет code; VPS-agent только разворачивает approved commit.
- Каждый rollout выполняется backup-first и фиксируется точным SHA.

## 4. Текущее production state

Production URL:

```text
https://health.funti.cc
```

На 2026-07-11:

- production code: `f3d7e8fedcdad5448abce5c74c1bdb698e5e82e6`;
- production Alembic: `0045 (head)`;
- main review baseline: `1a61f0307130e19fedeabd95218293d9a5075fe1`;
- Clinical Dictionaries: 69 concepts, 107 aliases;
- engineering verdict: `FIX BEFORE ROLLOUT`.

Подробное состояние: `docs/CURRENT-STATE.md`.

## 5. Этапы

### PHASE-01 — Базовая платформа и production

Статус: `COMPLETED`

Реализовано:

- FastAPI + React/Vite;
- PostgreSQL и Alembic;
- HTTPS production deployment;
- health checks, systemd, release symlink и rollback process;
- release `v0.1.0-auth-mvp`;
- production from exact commit SHA.

### PHASE-02 — Identity, sessions и tenant isolation

Статус: `COMPLETED / HARDENING CONTINUES IN HC-015`

Реализовано:

- Google OIDC с PKCE, state и nonce;
- Email Magic Links через Brevo;
- PostgreSQL sessions;
- workspace/profile bootstrap;
- FORCE RLS;
- отдельный `health_compass_rls_definer`;
- устранение RLS recursion;
- закрытие self-grant owner и self-add workspace;
- cross-user negative checks;
- friendly invalid/replayed link states.

Оставшееся hardening:

- scanner-safe Magic Link confirmation;
- POST logout;
- fail-safe production account-linking invariant;
- structured log redaction;
- full automated tenant/auth regression gate.

### PHASE-02.5 — Progressive Health Intake

Статус: `CORE SLICES DEPLOYED / REMEDIATION REQUIRED`

Принятый path:

```text
Login
→ minimal onboarding
→ Empty Dashboard / первое действие
→ добровольный Health Profile
→ Clinical Context
→ contextual intake prompts
→ подтверждённый импорт из документов
```

#### Slice 1 — Basic Health Profile

Статус: `DEPLOYED`

- name, date of birth, sex;
- height, timezone;
- weight history;
- consent;
- provenance и audit;
- contextual readiness;
- `/app/profile`;
- owner/edit/view/analyze access matrix.

#### Slice 2 — Clinical Context

Статус: `DEPLOYED / HC-015 FIXES REQUIRED`

- conditions and symptoms;
- allergies and intolerances;
- medications;
- supplements;
- review states;
- active/history lifecycle;
- dose, frequency and dates;
- consent, provenance, audit и void;
- typeahead and free-text fallback;
- Clinical Dictionaries v2.

Review findings требуют:

- одного владельца summary/review routes;
- atomic review-state transitions;
- optimistic concurrency для void;
- canonical concept domain integrity;
- frontend contract fixes.

#### Slice 3 — Contextual Intake

Статус: `FOUNDATION DEPLOYED`

- сохранить в profile;
- использовать только для analysis;
- отложить;
- объяснить purpose;
- append-only intake decisions.

Duplicate resolution должен учитывать intake decision rows в HC-015.

#### Slice 4 — Documents/OCR transition

Статус: `PLANNED AFTER HC-015`

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

### PHASE-02.6 — Account linking и duplicate resolution

Статус: `DEPLOYED / SCHEMA-SYNC FIX IN HC-015`

Реализованы:

- HC-025 symmetric account linking;
- HC-026 controlled duplicate resolution;
- HC-027 prevention of silent duplicate creation;
- step-up identity removal;
- запрет удаления последней identity.

HC-015 должен синхронизировать meaningful-activity assessment с `profile_clinical_reviews` и `profile_intake_decisions`.

### PHASE-02.7 — HC-015 Code Review Remediation

Статус: `CURRENT BLOCKING PHASE`

Goal: закрыть findings двух независимых reviews до новых feature migrations и production rollout.

Обязательные slices:

1. Clinical Context route cleanup.
2. Duplicate resolution schema synchronization.
3. Magic Link/logout/account-linking/logging hardening.
4. Clinical dictionary integrity migration.
5. Full lint/typecheck and migration-cycle CI.
6. Concurrency and frontend API contract fixes.
7. Independent diff review.
8. Controlled production rollout.

Канонический документ:

```text
docs/implementation/HC-015-CODE-REVIEW-REMEDIATION.md
```

Новые product features до завершения PHASE-02.7 не начинаются.

### PHASE-03 — Human Documents, OCR и Labs

Статус: `PLANNED / BLOCKED BY HC-015`

Первый vertical slice:

```text
Login
→ Minimal Onboarding
→ Empty Dashboard
→ Upload Analysis
→ Processing
→ OCR Review
→ Lab Results
→ Metric Dynamics
→ Contextual Intake
→ AI Explanation with Evidence
→ Doctor Report
```

Состав:

- PDF/image upload;
- processing queue;
- OCR confidence и human confirmation;
- patient matching;
- provenance per value;
- lab results;
- reference ranges;
- metric dynamics;
- doctor report data foundation.

До реального импорта разрешены только явно помеченные demo data.

### PHASE-04 — Источники данных и integrations

Статус: `PLANNED`

- Oura OAuth и sync;
- laboratory PDF/CSV;
- Apple Health / Health Connect по отдельному ADR;
- raw ingestion and normalization;
- idempotency and cursors;
- freshness and sync status;
- safe bulk upload.

### PHASE-05 — Timeline и analytics

Статус: `PLANNED`

- unified health timeline;
- trends сна, активности, веса и labs;
- personal baseline;
- significant-change detection;
- explainable priority cards;
- Attention Inbox;
- search.

### PHASE-05.5 — Nutrition Photo MVP

Статус: `PLANNED AFTER LABS CORE`

Canonical document:

```text
docs/NUTRITION-PHOTO-MVP.md
```

Invariants:

- raw capture → machine analysis → human confirmation → normalized fact;
- AI output не является fact без confirmation;
- calorie range вместо ложной точности;
- provenance и `ai_runs`;
- `external_llm` consent;
- wellbeing stop-list.

### PHASE-06 — Совместный доступ

Статус: `PLANNED`

- invitations;
- owner/edit/analyze/view;
- revoke;
- audit;
- RLS matrix;
- caregiver/profile transfer только после threat review.

### PHASE-07 — Privacy и data lifecycle

Статус: `PLANNED`

- consent center;
- active sessions;
- export;
- delete profile/user;
- retention;
- access audit;
- deletion raw/normalized/derived/embeddings;
- external LLM consent.

### PHASE-08 — AI Health Assistant

Статус: `PLANNED`

- retrieval-grounded answers;
- evidence/citations;
- Fact / Interpretation / Recommendation separation;
- red-flag routing;
- no diagnosis or dose calculation;
- `profile_id` retrieval filtering;
- privacy-minimized `ai_runs`;
- prompt-injection tests;
- versioned prompts and medical rules.

Implementation must comply with `docs/AI-PRODUCT-SAFETY.md`.

### PHASE-09 — Расширение продукта

Статус: `BACKLOG`

- family profiles;
- separate Pet Health model and retrieval;
- clinician/caregiver workflows;
- Offline Emergency Card;
- subscriptions and unit economics;
- mobile app/PWA.

## 6. Ближайший план

1. Принять docs PR с review evidence и HC-015 specification.
2. Создать implementation branch `fix/hc-015-code-review-remediation` от актуального `main`.
3. Выполнить HC-015 Slices A–F в зафиксированном порядке.
4. Не создавать parallel Alembic head; migration revision определяется только после проверки актуального head.
5. Запустить полный backend/frontend/PostgreSQL CI на exact PR SHA.
6. Провести independent diff review.
7. Merge только при отсутствии unresolved High findings.
8. Выполнить controlled backup-first production rollout.
9. Зафиксировать production HEAD/Alembic, smoke results и logs.
10. Изменить verdict на `ACCEPT WITH FOLLOW-UP` или `READY` только с evidence.
11. После HC-015 выполнить небольшой HC-014 alias expansion.
12. Затем вернуться к PHASE-03 Upload → OCR Review → Labs.

## 7. Rollout gate HC-015

Rollout запрещён, если:

- overlapping routes остаются;
- duplicate resolution может вернуть 500/FK violation;
- GET consumes Magic Link;
- wrong-domain/stale canonical mapping сохраняется;
- full-source lint или TypeScript check отсутствуют;
- migration cycle не подтверждён;
- CI выполнен не на exact deployed SHA;
- в logs появляются tokens, secrets или medical values;
- обнаружен cross-user leak.

## 8. Правило обновления

После этапа или review обновляются:

- `docs/CURRENT-STATE.md`;
- `docs/PROJECT-PLAN.md`;
- `docs/DEVELOPMENT-HISTORY.md`;
- `docs/reviews/FABLE-RECOMMENDATIONS.md`;
- `docs/source-index/SOURCE-REGISTER.md`;
- implementation document соответствующей HC-задачи;
- `docs/SECURITY-INVARIANTS.md`, если меняются security rules;
- product/UX/intake/AI baselines, если меняются соответствующие решения;
- README, если меняются public URL, architecture или local run;
- ADR, если принято новое архитектурное решение.

Статус `VERIFIED` допускается только после test, merge и/или production evidence, соответствующего формулировке статуса.
