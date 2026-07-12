# Health Compass — канонический план проекта

Версия: 1.5  
Дата: 2026-07-12  
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

Канонические review и implementation documents:

- `docs/reviews/CODE-REVIEW-CONSOLIDATED-2026-07-11.md`;
- `docs/reviews/FABLE-5-INDEPENDENT-CODE-REVIEW-2026-07-11.md`;
- `docs/implementation/HC-015-CODE-REVIEW-REMEDIATION.md`;
- `docs/implementation/HC-015-PRODUCTION-EVIDENCE-2026-07-11.md`;
- `docs/implementation/HC-016-CLINICAL-RECORD-ERASURE.md`;
- `docs/implementation/HC-016-PRODUCTION-ACCEPTANCE-2026-07-12.md`.

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
- Destructive medical-data operations используют least privilege, explicit confirmation и optimistic concurrency.

## 4. Текущее production state

Production URL:

```text
https://health.funti.cc
```

На 2026-07-12:

- main HEAD: `b8e868825f378195975e2729f3f36c21a1afa2d0`;
- последний approved rollout target: `b8e868825f378195975e2729f3f36c21a1afa2d0`;
- production Alembic target: `0049`;
- Clinical Dictionaries: 69 concepts, 107 aliases;
- HC-015: deployed, automated verified, owner smoke confirmed;
- Safari Magic Link regression: fixed and manually confirmed on iPhone Safari;
- HC-016: merged and manually accepted in production;
- engineering verdict: `READY FOR NEXT PRODUCT PHASE / FOLLOW-UPS REMAIN`.

Детальный VPS-отчёт HC-016 не скопирован в репозиторий. Поэтому отсутствующие operational values не восстанавливаются предположениями.

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

Статус: `COMPLETED / FOLLOW-UP HARDENING NON-BLOCKING`

Реализовано:

- Google OIDC с PKCE, state и nonce;
- Email Magic Links через Brevo;
- scanner-safe GET interstitial и explicit POST consume;
- POST logout с Origin protection;
- PostgreSQL sessions;
- workspace/profile bootstrap;
- FORCE RLS;
- отдельный `health_compass_rls_definer`;
- устранение RLS recursion;
- закрытие self-grant owner и self-add workspace;
- cross-user negative checks;
- friendly invalid/replayed link states;
- safe structured logging и query redaction;
- fail-safe production account-linking configuration;
- Safari-compatible Magic Link Origin handling.

Non-blocking follow-ups:

- OIDC discovery/JWKS caching;
- переход с deprecated `authlib.jose` на `joserfc`;
- cleanup неиспользуемой CORS configuration.

### PHASE-02.5 — Progressive Health Intake

Статус: `CORE SLICES DEPLOYED`

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
- height, automatically detected timezone;
- weight history;
- consent;
- provenance и audit;
- contextual readiness;
- `/app/profile`;
- owner/edit/view/analyze access matrix.

#### Slice 2 — Clinical Context

Статус: `DEPLOYED / REMEDIATED / OWNER-CONTROLLED ERASURE ADDED`

- conditions and symptoms;
- allergies and intolerances;
- medications;
- supplements;
- review states;
- active/history lifecycle;
- dose, frequency and dates;
- consent, provenance, audit и void;
- typeahead and free-text fallback;
- Clinical Dictionaries v2;
- optimistic concurrency for destructive changes;
- separate **Убрать из профиля** and **Удалить навсегда** actions.

#### Slice 3 — Contextual Intake

Статус: `FOUNDATION DEPLOYED`

- сохранить в profile;
- использовать только для analysis;
- отложить;
- объяснить purpose;
- append-only intake decisions.

#### Slice 4 — Documents/OCR transition

Статус: `CURRENT NEXT PRODUCT SLICE`

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

Статус: `DEPLOYED / REMEDIATED`

Реализованы:

- HC-025 symmetric account linking;
- HC-026 controlled duplicate resolution;
- HC-027 prevention of silent duplicate creation;
- step-up identity removal;
- запрет удаления последней identity;
- meaningful-activity assessment с учётом `profile_clinical_reviews` и `profile_intake_decisions`.

### PHASE-02.7 — HC-015 Code Review Remediation

Статус: `COMPLETED / DEPLOYED / AUTOMATED VERIFIED`

Закрыты блокирующие findings двух независимых reviews:

1. Clinical Context route cleanup.
2. Duplicate resolution schema synchronization — migration `0046`.
3. Magic Link/logout/account-linking/logging hardening.
4. Clinical dictionary integrity — migration `0047`.
5. Narrow users grants — migration `0048`.
6. Full lint/typecheck and migration-cycle CI.
7. Concurrency and frontend API contract fixes.
8. Controlled backup-first production rollout.

Production application commit HC-015:

```text
c87723d7b4d0e4d2db9f1e0df4e936fbfd543346
```

Canonical evidence:

```text
docs/implementation/HC-015-PRODUCTION-EVIDENCE-2026-07-11.md
```

### PHASE-02.8 — HC-016 Clinical Record Erasure

Статус: `COMPLETED / MERGED / PRODUCTION MANUALLY ACCEPTED`

Реализовано:

- owner-only permanent erasure;
- explicit irreversible confirmation;
- `expected_updated_at` concurrency guard;
- erasure after consent withdrawal;
- no direct runtime DELETE on clinical tables;
- restricted `SECURITY DEFINER` function;
- atomic removal of value-bearing audit events;
- content-free `clinical_record.erased` tombstone;
- migration `0049`;
- corrected user warning without backup-retention sentence.

Canonical documents:

```text
docs/implementation/HC-016-CLINICAL-RECORD-ERASURE.md
docs/implementation/HC-016-PRODUCTION-ACCEPTANCE-2026-07-12.md
```

### PHASE-03 — Human Documents, OCR и Labs

Статус: `CURRENT PLANNING / NOT IMPLEMENTED`

Первый vertical slice:

```text
Login
→ Minimal Onboarding
→ Empty Dashboard
→ Upload Analysis
→ Processing
→ OCR Review
→ User Confirmation
→ Lab Results
→ Metric Dynamics
→ Contextual Intake
```

Состав foundation:

- PDF/image upload;
- secure object storage boundary;
- processing queue;
- OCR confidence и human confirmation;
- patient matching;
- provenance per value;
- lab results;
- reference ranges;
- metric dynamics;
- document and extracted-data deletion lifecycle;
- doctor report data foundation.

До реального импорта разрешены только явно помеченные demo data.

Перед implementation необходимо утвердить:

- file upload threat model;
- content-type and size limits;
- malware/scanner strategy;
- storage encryption and access model;
- RLS/object-storage mapping;
- provenance contract;
- OCR human-review contract;
- raw/normalized/derived deletion lifecycle.

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

Статус: `FOUNDATION STARTED / BROADER SCOPE PLANNED`

Уже реализовано:

- consent foundation;
- clinical provenance and audit;
- soft removal/void;
- owner-controlled permanent erasure отдельных Clinical Context records.

Остаётся:

- consent center;
- active sessions;
- export;
- delete profile/user;
- retention policy;
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

1. Зафиксировать HC-016 production acceptance в canonical docs — текущий docs PR.
2. Подготовить PHASE-03 architecture slice без product code.
3. Утвердить upload/storage threat model и data lifecycle.
4. Спроектировать минимальную schema для documents, processing jobs, extracted observations и provenance.
5. Зафиксировать access matrix и RLS before migration numbering.
6. Подготовить UI states: Upload, Processing, Failed, OCR Review, Confirmed.
7. Реализовать первый узкий vertical slice на demo/test documents.
8. Только после security review разрешить controlled production rollout.

Non-blocking technical follow-ups допускаются отдельными маленькими PR:

- revoke unnecessary PUBLIC EXECUTE у обычных trigger functions;
- `joserfc` migration;
- dictionary search indexes;
- OIDC discovery/JWKS caching;
- CORS config cleanup.

## 7. Rollout gates для PHASE-03

Rollout запрещён, если:

- upload допускает неограниченный размер или неподдерживаемые content types;
- object storage key не связан с tenant/profile boundary;
- raw document доступен без owner/profile authorization;
- OCR values становятся clinical facts без explicit confirmation;
- provenance теряется между document, extracted candidate и confirmed observation;
- deletion lifecycle не покрывает raw, extracted и normalized data;
- CI выполнен не на exact deployed SHA;
- миграции имеют несколько heads;
- backup не подтверждён;
- в logs появляются tokens, document contents или medical values;
- обнаружен cross-user access.

## 8. Правило обновления

После этапа или review обновляются:

- `docs/CURRENT-STATE.md`;
- `docs/PROJECT-PLAN.md`;
- `docs/DEVELOPMENT-HISTORY.md` или отдельный dated evidence document;
- `docs/reviews/FABLE-RECOMMENDATIONS.md`, если меняется статус рекомендаций;
- `docs/source-index/SOURCE-REGISTER.md`;
- implementation document соответствующей HC-задачи;
- `docs/SECURITY-INVARIANTS.md`, если меняются security rules;
- product/UX/intake/AI baselines, если меняются соответствующие решения;
- README, если меняются public URL, architecture или local run;
- ADR, если принято новое архитектурное решение.

Статус `VERIFIED` допускается только после test, merge и/или production evidence, соответствующего формулировке статуса. Manual acceptance не заменяет отсутствующие operational metrics.
