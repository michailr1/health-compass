# HC-012b — Clinical Context / Slice 2

Статус: `APPROVED FOR IMPLEMENTATION`  
Основание: аудит актуального `main`, Alembic head `0036`  
Предлагаемая feature-ветка: `feat/clinical-context-slice-2`  
Production rollout: только после зелёного CI, review и отдельного решения

## 1. Цель

Добавить структурированный клинический контекст профиля без обязательной большой анкеты:

- состояния и диагнозы, сообщённые пользователем;
- аллергии и непереносимости;
- лекарства;
- витамины, минералы и БАДы;
- клинические safety-флаги, необходимые для ограничения будущих рекомендаций.

Данные вводятся добровольно, могут быть пропущены и не используются для автоматической диагностики или расчёта доз.

## 2. Что уже существует и переиспользуется

HC-012b опирается на существующие механизмы Slice 1:

- `health_compass.health_profiles` как корневая сущность;
- `app_can_view_profile(uuid)` для чтения;
- `app_can_edit_profile(uuid)` для записи;
- `user_consents` и consent `health_data_processing`;
- `profile_audit_events` как единый append-only audit trail;
- permission matrix owner/edit/analyze/view;
- одна транзакция на HTTP-запрос;
- cross-user ресурсы через API возвращают `404`;
- ENABLE/FORCE RLS, policies и grants создаются в той же миграции, что таблица.

Отдельный consent для ручного Clinical Context в Slice 2 не создаётся. Используется действующий `health_data_processing`. Consent `external_llm` понадобится позже и не входит в HC-012b.

## 3. Решение по модели данных

Используются отдельные типизированные таблицы, а не одна polymorphic JSON-таблица.

Причины:

- разные инварианты и обязательные поля;
- отдельные индексы и ограничения;
- понятные API-контракты;
- безопасное развитие OCR/import;
- меньше риска невалидных комбинаций полей;
- проще RLS, аудит и удаление данных.

### 3.1 `profile_conditions`

Поля:

- `id uuid`;
- `profile_id uuid`;
- `display_name varchar(255)` — пользовательское или подтверждённое название;
- `code_system varchar(64) null`;
- `code varchar(128) null`;
- `clinical_status varchar(32)` — `active | resolved | inactive | unknown`;
- `onset_date date null`;
- `resolved_date date null`;
- `notes text null` с разумным лимитом;
- `source_type varchar(32)` — для Slice 2 только `manual`; `document` резервируется для подтверждённого OCR;
- `confirmation_status varchar(32)` — `confirmed | needs_review`;
- `created_by_user_id uuid`;
- `created_at`, `updated_at`;
- `voided_at`, `voided_by_user_id`, `void_reason`.

Инварианты:

- пустое имя запрещено;
- `resolved_date >= onset_date`, если обе даты заданы;
- `clinical_status=resolved` требует `resolved_date` либо явного подтверждения «дата неизвестна» на уровне API;
- manual-запись сразу `confirmed`;
- физическое DELETE через пользовательский API не используется.

### 3.2 `profile_allergies`

Поля:

- `id`, `profile_id`;
- `substance_name varchar(255)`;
- optional `code_system`, `code`;
- `allergy_type varchar(32)` — `allergy | intolerance | unknown`;
- `reaction varchar(500) null`;
- `severity varchar(32) null` — `mild | moderate | severe | unknown`;
- `clinical_status varchar(32)` — `active | inactive | resolved | unknown`;
- provenance, confirmation, actor, timestamps и void-поля как выше.

Инварианты:

- severity не вычисляется автоматически;
- отсутствие severity допустимо;
- портал не делает вывод об анафилаксии из свободного текста.

### 3.3 `profile_medications`

Поля:

- `id`, `profile_id`;
- `display_name varchar(255)`;
- optional `code_system`, `code`;
- `status varchar(32)` — `active | completed | paused | stopped | unknown`;
- `dose_value numeric(12,4) null`;
- `dose_unit varchar(32) null`;
- `frequency_text varchar(255) null`;
- `route varchar(64) null`;
- `start_date date null`;
- `end_date date null`;
- `reason_text varchar(500) null`;
- provenance, confirmation, actor, timestamps и void-поля.

Инварианты:

- если задано `dose_value`, обязательна `dose_unit`;
- `dose_value > 0`;
- `end_date >= start_date`;
- система хранит введённую дозу, но не рассчитывает и не рекомендует её;
- необычные значения дают мягкое предупреждение и требуют явного подтверждения, но не заменяются автоматически.

### 3.4 `profile_supplements`

Структура аналогична medications, но отдельная таблица и отдельный тип сущности.

Дополнительное поле:

- `supplement_type varchar(32)` — `vitamin | mineral | herbal | sports | other | unknown`.

Причина разделения: разные UX, справочники, safety-правила и будущая аналитика.

### 3.5 `profile_clinical_safety_flags`

Минимальная отдельная таблица для явных, подтверждённых ограничений будущих функций.

Поля:

- `id`, `profile_id`;
- `flag_type varchar(64)`;
- `status varchar(32)` — `active | inactive`;
- `source_entity_type varchar(64) null`;
- `source_entity_id uuid null`;
- `confirmation_status varchar(32)`;
- `created_by_user_id`, timestamps и void-поля.

Для HC-012b разрешённый `flag_type`:

- `nutrition_calorie_feedback_suppressed`.

Правила:

- флаг не создаётся по свободному тексту автоматически;
- он появляется только после явного выбора/подтверждения пользователя или в будущем после подтверждённого импорта;
- HC-032 обязан проверять активный флаг до формирования любого calorie/weight feedback;
- отсутствие флага не означает отсутствие заболевания.

## 4. Provenance и confirmation

Каждая clinical-сущность содержит:

- `source_type`;
- optional `source_document_id` только после появления document pipeline;
- `confirmation_status`;
- `created_by_user_id`;
- timestamps;
- audit event.

Slice 2 поддерживает `manual + confirmed`.

Значения `document + needs_review/confirmed` резервируются в схеме и API-контрактах, но создание таких записей не реализуется до OCR Review.

AI/OCR-предложение никогда не становится нормализованным clinical fact без подтверждения пользователя.

## 5. Изменения существующего audit trail

`profile_audit_events` переиспользуется. Миграция расширяет разрешённые действия:

- `condition.created`;
- `condition.updated`;
- `condition.voided`;
- `allergy.created`;
- `allergy.updated`;
- `allergy.voided`;
- `medication.created`;
- `medication.updated`;
- `medication.voided`;
- `supplement.created`;
- `supplement.updated`;
- `supplement.voided`;
- `clinical_safety_flag.created`;
- `clinical_safety_flag.updated`;
- `clinical_safety_flag.voided`.

`changed_fields` хранит old/new только для изменённых полей. Секреты и внешние токены там отсутствуют.

Audit остаётся append-only: app-role получает SELECT/INSERT, но не UPDATE/DELETE.

## 6. RLS и privileges

Для каждой новой таблицы в migration `0037`:

- `ENABLE ROW LEVEL SECURITY`;
- `FORCE ROW LEVEL SECURITY`;
- SELECT policy через `app_can_view_profile(profile_id)`;
- INSERT policy: actor=current user и `app_can_edit_profile(profile_id)`;
- UPDATE policy только для owner/edit;
- column-level UPDATE grants только на разрешённые поля;
- void вместо DELETE;
- PUBLIC privileges отсутствуют;
- app-role не получает DELETE;
- viewer/analyze видят данные, но не меняют их;
- outsider получает 0 строк на SQL-уровне и `404` через API.

Для UPDATE требуется защита от изменения `profile_id`, `created_by_user_id`, `created_at` и исходного provenance без специального import flow.

## 7. Consent gate

Создание, изменение и void clinical-сущности требует активного `health_data_processing` consent.

Чтение уже сохранённых данных после отзыва consent:

- остаётся доступным пользователю для экспорта/удаления и прозрачности;
- новые записи и изменения блокируются `409`;
- автоматическая обработка и AI-функции не запускаются.

Полное удаление/retention будет реализовано в lifecycle-фазе.

## 8. API

Базовый шаблон:

```text
GET    /profiles/{profile_id}/conditions
POST   /profiles/{profile_id}/conditions
PATCH  /profiles/{profile_id}/conditions/{id}
POST   /profiles/{profile_id}/conditions/{id}/void
```

Аналогично:

- `/allergies`;
- `/medications`;
- `/supplements`;
- `/clinical-safety-flags`.

Правила:

- list по умолчанию возвращает только неаннулированные записи;
- `include_voided=true` доступен владельцу/редактору и read-only ролям, если профиль видим;
- чужой profile/entity — `404`;
- отсутствие consent на write — `409`;
- optimistic concurrency: `updated_at` или version передаётся в PATCH; конфликт — `409`;
- idempotency key для POST желательно добавить сразу либо явно отложить и задокументировать;
- API не принимает `created_by_user_id`, actor или confirmation от клиента без серверной проверки.

## 9. Frontend

Маршрут остаётся в контуре `/app/profile` с секцией «Клинический контекст» или отдельным вложенным экраном `/app/profile/clinical-context`.

MVP UI:

- четыре карточки: Состояния, Аллергии, Лекарства, Добавки;
- число активных записей;
- понятный empty state;
- кнопка добавления;
- активные и завершённые/неактивные записи разделены;
- быстрый перевод active → completed/resolved/stopped;
- редактирование и «Удалить из актуальных» через void с причиной;
- пояснение, зачем данные нужны;
- «Не сейчас» без снижения health score;
- safety-флаг не выставляется скрыто: требуется отдельное подтверждение.

Никакой большой обязательной анкеты и никаких синтетических medical examples в реальном профиле.

## 10. HC-026 duplicate assessment

Это блокирующее сопутствующее изменение migration `0037`.

`app_duplicate_user_activity(uuid)` должен учитывать:

- `profile_conditions`;
- `profile_allergies`;
- `profile_medications`;
- `profile_supplements`;
- `profile_clinical_safety_flags`;
- связанные новые audit events.

Любая строка, включая voided history, считается meaningful activity. Пользователь с Clinical Context не может быть автоматически поглощён как пустой bootstrap-user.

Функция остаётся SECURITY DEFINER, недоступной app-role напрямую; публичный pair assessment сохраняет текущую модель доступа.

## 11. Nutrition compatibility

HC-012b создаёт клинический и safety-контекст, но не nutrition-сущности.

Не создаются:

- `meal_capture`;
- `meal_analysis`;
- `meal`;
- `meal_item`;
- internal food catalog;
- `meal_type` в production DB.

Фиксируется общий паттерн:

```text
raw/capture
→ machine proposal
→ human confirmation
→ normalized confirmed fact
```

Будущий HC-032 проверяет `nutrition_calorie_feedback_suppressed` до генерации рекомендаций.

## 12. Migration plan

Предлагаемая миграция: `0037_add_clinical_context.py`.

Порядок внутри upgrade:

1. precondition для `health_compass_rls_definer`;
2. создание таблиц и CHECK/FK constraints;
3. индексы;
4. ENABLE/FORCE RLS;
5. policies;
6. grants и column-level UPDATE;
7. расширение audit action constraint;
8. `CREATE OR REPLACE app_duplicate_user_activity` с новыми счётчиками;
9. ownership/EXECUTE invariants;
10. migration assertions/tests.

Downgrade обязан быть реальным и не оставлять policies/functions/grants. Перед downgrade из production требуется отдельная проверка отсутствия данных или backup; автоматический downgrade с потерей clinical data запрещён операционным runbook.

## 13. Tests

Обязательные группы:

### Schema/validation

- пустые названия отклоняются;
- date ordering;
- dose/unit consistency;
- allowed enums;
- void field consistency;
- source/confirmation combinations.

### RLS matrix

Для owner/edit/view/analyze/outsider:

- SELECT;
- INSERT;
- PATCH;
- void;
- подмена `profile_id`;
- direct SQL DELETE;
- отсутствие GUC context;
- регресс `54001` на тёплых данных.

### Consent

- write без consent → `409`;
- write после accept → success;
- write после revoke → `409`;
- read после revoke остаётся доступным.

### Audit

- create/update/void создают отдельные события;
- audit нельзя изменить или удалить app-role;
- actor/request_id выставляются сервером.

### Duplicate resolution

- пользователь с любой clinical-строкой `is_empty=false`;
- voided clinical history тоже блокирует absorption;
- чистый bootstrap-user остаётся eligible;
- pair assessment не доступен постороннему user context.

### API

- cross-user `404`;
- view/analyze write → `404`;
- optimistic concurrency conflict;
- list active/history;
- malformed UUID и invalid enum.

### Frontend

- empty states;
- active/history grouping;
- consent gate;
- мягкие validation warnings;
- safety-флаг требует явного подтверждения;
- отсутствие synthetic medical data.

## 14. Не входит в HC-012b

- OCR/import из документов;
- автоматическое распознавание лекарств;
- медицинские справочники как обязательная зависимость;
- drug interaction checker;
- рекомендации доз;
- диагнозы;
- family history;
- emergency card;
- nutrition diary;
- AI assistant;
- автоматическое создание safety-флагов по тексту;
- физическое удаление clinical history пользователем.

## 15. Последовательность реализации

```text
specification
→ branch feat/clinical-context-slice-2 from current main
→ migration 0037 + DB/RLS tests
→ ORM models + schemas
→ services + API
→ duplicate-assessment regression
→ frontend
→ full CI
→ security/product review
→ PR
→ separate rollout decision
```

## 16. Definition of Done

- все четыре clinical-раздела работают;
- active/history состояния поддерживаются;
- consent обязателен для write;
- provenance/confirmation сохранены;
- audit append-only;
- FORCE RLS и permission matrix проверены реальным PostgreSQL;
- HC-026 не считает заполненный профиль пустым;
- safety-флаг доступен будущему HC-032;
- нет автоматической диагностики или расчёта доз;
- нет synthetic medical data;
- backend/frontend CI зелёный;
- production не изменён до отдельного rollout.
