# HC-012b — Data Model & API Gap Plan

Статус: `PROPOSED IMPLEMENTATION PLAN`  
Дата: 2026-07-10  
База анализа: `main` at `1eafe48ac4c4ca08e6b12d6342a974192faac285`, Alembic head `0041`  
Канонический UX: `docs/CLINICAL-CONTEXT-INPUT-UX.md`  
Production: не изменяется этим документом

## 1. Цель

Определить минимальные изменения data model, API и frontend-контрактов, необходимые для реализации согласованного Clinical Context UX без потери существующих данных и без нарушения RLS, audit и provenance.

Этот документ не разрешает rollout. Он определяет план следующей feature-ветки.

## 2. Что уже поддерживается текущей моделью

Текущая реализация HC-012b уже содержит сильную основу:

- отдельные таблицы для conditions, allergies, medications, supplements и safety flags;
- ENABLE/FORCE RLS;
- manual/document provenance;
- confirmation status;
- append-only audit;
- void вместо физического DELETE;
- статусы active/resolved/inactive для conditions/allergies;
- статусы active/completed/paused/stopped для medications/supplements;
- даты начала/окончания;
- дозу, единицу и частоту;
- explicit clinical section review;
- confirmed-empty flow;
- cross-user isolation;
- отсутствие DELETE privilege после migration `0041`.

Следовательно, существующие clinical-таблицы не заменяются. Требуются расширения.

## 3. Gap matrix

| UX-требование | Текущее состояние | Gap | Решение |
|---|---|---|---|
| `unknown / deferred / confirmed_none / has_entries` | review state поддерживает не все четыре семантики явно | `deferred` отсутствует или не является first-class state; `has_entries` частично вычисляется | расширить review-state contract и хранить пользовательское решение |
| Симптом ≠ диагноз | condition имеет имя, code и status | нет явного kind | добавить `entry_kind` |
| «Как давно?» | есть optional `onset_date` | пользователь может знать только приблизительно | добавить onset precision/bucket |
| «Есть сейчас?» включая `Повторяется` | есть clinical_status | recurrent не выражается корректно | добавить `current_pattern` отдельно от lifecycle status |
| Свободный ввод | сохраняется display name | нет формализованного origin | добавить `term_origin` и не требовать canonical code |
| Global/Personal dictionaries | отсутствуют как отдельный контракт | typeahead нечем обслуживать стабильно | добавить dictionary search API; Personal строить из подтверждённых записей |
| AI Moderated Dictionary | AI сейчас не используется | нужно зарезервировать безопасный контракт | отдельная proposal-сущность позже, не в первой migration |
| Chips | frontend сейчас сохраняет простую строку | нет draft item contract | frontend draft model + create payload per chip |
| Возобновление лекарства = новый курс | модель допускает несколько строк | PATCH может реактивировать completed/stopped | запрет lifecycle transition обратно в active; POST нового курса |
| Why We Ask | текст частично есть | нет единого компонента/контракта | frontend component + canonical copy |
| «Не сейчас» | отсутствует как устойчивое решение | невозможно отличить от untouched | PATCH review-state to deferred |
| Идемпотентный POST | не закреплено как обязательное | double-tap может создать дубликат | Idempotency-Key или client_request_id |
| Черновик при сетевой ошибке | frontend-local | нет формального поведения | local draft state, без серверного clinical fact до Save |

## 4. Решение по review-state

### 4.1 Канонические значения

Для каждой секции хранится пользовательское состояние:

- `unknown`;
- `deferred`;
- `confirmed_none`.

`has_entries` не следует хранить независимо как изменяемый флаг. Оно вычисляется из наличия хотя бы одной неvoided или исторической clinical-записи в секции.

Причина: отдельное хранение `has_entries` создаёт риск рассинхронизации с таблицами сущностей.

### 4.2 Effective state

API возвращает:

```json
{
  "review_state": "unknown",
  "effective_state": "has_entries",
  "active_count": 1,
  "history_count": 2,
  "reviewed_at": "...",
  "reviewed_by_user_id": "..."
}
```

Правило вычисления:

1. если существуют записи, `effective_state=has_entries`;
2. иначе используется сохранённый `review_state`;
3. если review-state отсутствует, `effective_state=unknown`.

При добавлении первой записи:

- сохранённый `confirmed_none` или `deferred` снимается сервером;
- создаётся audit event;
- effective state становится `has_entries`.

При void последней записи:

- состояние не становится автоматически `confirmed_none`;
- возвращается `unknown`, если пользователь отдельно не подтвердил отсутствие записей.

### 4.3 Migration

Предпочтительно расширить существующую таблицу clinical review, а не создавать вторую.

Необходимые поля/ограничения:

- `review_state varchar(32)` with CHECK `unknown | deferred | confirmed_none`;
- `reviewed_at`;
- `reviewed_by_user_id`;
- optimistic concurrency (`updated_at` или version);
- UNIQUE `(profile_id, section_key)`;
- ENABLE/FORCE RLS;
- app-role без DELETE.

Если текущая таблица использует boolean `confirmed_empty`, migration преобразует:

- `true` → `confirmed_none`;
- `false`/NULL → `unknown`.

Boolean после миграции удаляется только после перевода backend/frontend и тестов.

## 5. Conditions: symptom versus diagnosis

### 5.1 Новое поле `entry_kind`

В `profile_conditions` добавить:

```text
entry_kind = condition | symptom | diagnosis | unknown
```

Семантика:

- `symptom` — наблюдение пользователя;
- `diagnosis` — диагноз, который пользователь явно сообщил как поставленный/подтверждённый;
- `condition` — нейтральное известное состояние без дополнительного утверждения о диагнозе;
- `unknown` — пользователь не знает классификацию.

UI не обязан показывать эти термины при первом вводе. Значение определяется только явным выбором или нейтральным безопасным default:

- свободно введённый симптомоподобный текст не классифицируется AI;
- default для неопределённого ручного ввода — `unknown` или `condition`, но не `diagnosis`;
- `diagnosis` никогда не выставляется автоматически.

Рекомендуемый безопасный default: `unknown`.

### 5.2 Approximate onset

Точная дата остаётся optional.

Добавить:

```text
onset_precision = exact_date | approximate_period | bucket | unknown
onset_bucket = recent | long_ago | unknown | null
onset_text = varchar(100) null
```

Правила:

- `exact_date` требует `onset_date`;
- `bucket` требует `onset_bucket`;
- `unknown` не требует даты;
- `onset_text` используется для пользовательской формулировки вроде «примерно два года назад», пока она не нормализована.

Не преобразовывать `recent/long_ago` в выдуманную дату.

### 5.3 Current pattern

Добавить отдельное поле:

```text
current_pattern = present | resolved | recurrent | unknown
```

Оно не заменяет `clinical_status`.

Разделение:

- `clinical_status` — lifecycle записи;
- `current_pattern` — фактический ответ пользователя «есть сейчас / прошло / повторяется / не знаю».

Mapping:

- `present` обычно совместим с `active`;
- `resolved` обычно совместим с `resolved`;
- `recurrent` остаётся active/inactive согласно выбранной серверной логике, но не теряет повторяемость;
- `unknown` не заставляет менять lifecycle status.

Backend валидирует противоречивые комбинации, но не ставит диагноз.

## 6. Dictionary and terminology model

### 6.1 Первая реализация без AI

Первый этап typeahead использует:

1. Global Dictionary;
2. Personal Dictionary;
3. действие свободного ввода.

AI Moderated Dictionary не включается в первый implementation slice.

### 6.2 Global Dictionary

Рекомендуемая таблица:

`clinical_dictionary_concepts`

Минимальные поля:

- `id uuid`;
- `domain` — `condition | allergy | medication | supplement`;
- `display_name`;
- `normalized_name`;
- `concept_kind` optional;
- `code_system` optional;
- `code` optional;
- `synonyms text[]` или отдельная synonym table;
- `locale`;
- `is_active`;
- timestamps.

Без profile_id и без пользовательского INSERT.

Пользовательский ввод никогда автоматически не добавляет строку в эту таблицу.

Для MVP допускается небольшой курируемый seed или provider-neutral набор. Медицинская полнота словаря не заявляется.

### 6.3 Personal Dictionary

Отдельная таблица на первом этапе не обязательна.

Personal suggestions можно вычислять из ранее подтверждённых записей текущего профиля:

- distinct display text;
- section/domain;
- частота использования;
- последнее использование;
- только видимые профилю данные через RLS.

Если позднее понадобится персональная synonym/history-модель, она вводится отдельно.

### 6.4 Origin fields в clinical records

Добавить или закрепить:

```text
term_origin = global_dictionary | personal_history | free_text | document | ai_proposal
canonical_concept_id uuid null
```

Правила:

- `free_text` допускает NULL canonical concept/code;
- global choice сохраняет concept id и snapshot display text;
- personal history не обязана указывать canonical concept;
- `ai_proposal` не разрешён как confirmed record без отдельного подтверждения;
- `display_name/substance_name` хранится всегда как snapshot, чтобы запись не менялась при обновлении словаря.

Не заменять существующие `code_system/code`; они остаются interoperability snapshot.

## 7. Typeahead API

### 7.1 Endpoint

```text
GET /profiles/{profile_id}/clinical-context/suggestions
```

Query:

```text
section=conditions|allergies|medications|supplements
q=<text>
limit=10
```

Response:

```json
{
  "items": [
    {
      "suggestion_id": "...",
      "source": "global_dictionary",
      "display_text": "Магний",
      "secondary_text": "Минеральная добавка",
      "concept_id": "...",
      "concept_kind": "supplement"
    }
  ],
  "allow_free_text": true,
  "free_text_label": "Добавить «магний цитрат»"
}
```

### 7.2 Security and privacy

- endpoint требует profile visibility;
- Personal Dictionary использует только записи указанного профиля;
- outsider получает `404`;
- запросы typeahead не пишутся в clinical facts;
- raw query не отправляется внешнему AI;
- логирование запроса минимизируется/санитайзится как health-adjacent data.

### 7.3 Ranking

Приоритет:

1. точное personal match;
2. точное global display/synonym match;
3. prefix match;
4. fuzzy match с консервативным threshold;
5. free-text action всегда доступен.

Не использовать ranking как медицинскую рекомендацию.

## 8. Create/update API contracts

### 8.1 Create payload

Каждый chip создаёт отдельный POST.

Пример condition:

```json
{
  "display_text": "Головная боль",
  "term_origin": "free_text",
  "canonical_concept_id": null,
  "entry_kind": "symptom",
  "onset_precision": "bucket",
  "onset_bucket": "recent",
  "current_pattern": "recurrent",
  "notes": null,
  "client_request_id": "uuid"
}
```

Сервер устанавливает:

- profile_id из URL;
- created_by_user_id из context;
- source_type;
- confirmation_status;
- timestamps;
- audit actor.

### 8.2 Idempotency

Обязательный вариант для MVP:

- `client_request_id uuid` с UNIQUE в пределах profile/entity type; либо
- стандартный `Idempotency-Key` с серверным storage.

Предпочтение: `client_request_id`, поскольку проще связать с offline/local draft и протестировать.

Повторный POST с тем же id и тем же payload возвращает исходный результат.

Повтор с тем же id и другим payload возвращает `409`.

### 8.3 PATCH

PATCH используется для исправления данных и допустимых lifecycle transitions.

Требования:

- version/updated_at обязателен;
- конфликт — `409`;
- immutable: profile_id, created_by_user_id, created_at, original provenance;
- смена canonical concept требует явного подтверждённого action, а не silent normalization;
- audit содержит только изменённые поля.

## 9. Medication and supplement course lifecycle

### 9.1 Запрещённая реактивация

Для записей со статусом:

- `completed`;
- `stopped`;
- voided

PATCH обратно в `active` запрещён.

Ответ:

```text
409 course_closed_create_new
```

UI показывает:

`Этот курс завершён. Создать новый курс приёма?`

### 9.2 Новый курс

Создание нового курса выполняется POST и создаёт новый id.

Optional future field:

```text
previous_course_id uuid null
```

В первой реализации поле полезно, но не обязательно. Оно не должно блокировать MVP.

### 9.3 Paused

`paused → active` допустим для того же курса, поскольку курс не завершён.

`completed/stopped → active` недопустим.

### 9.4 Dates

При завершении курса:

- end_date optional, если пользователь не знает дату;
- точная дата не выдумывается;
- status change фиксируется отдельным audit event.

## 10. Section review API

Рекомендуемый endpoint:

```text
PATCH /profiles/{profile_id}/clinical-context/sections/{section}/review
```

Payload:

```json
{
  "review_state": "deferred",
  "version": 3
}
```

Допустимые переходы:

- unknown → deferred;
- unknown → confirmed_none;
- deferred → unknown;
- deferred → confirmed_none;
- confirmed_none → unknown;
- confirmed_none → has_entries только косвенно через создание записи.

Клиент не отправляет `has_entries` как review state.

При попытке confirmed_none при существующих неvoided записях сервер возвращает `409 section_has_entries`.

## 11. Frontend state model

### 11.1 Draft chip

До сохранения frontend хранит:

```text
local_id
section
input_text
display_text
suggestion source
concept id optional
answers
validation errors
save state
client_request_id
```

Draft не считается clinical fact.

### 11.2 Save states

- `draft`;
- `saving`;
- `saved`;
- `error`.

При error:

- chip и ответы остаются;
- повторный Save использует тот же client_request_id;
- пользователь может изменить данные, тогда генерируется новый client_request_id.

### 11.3 Multiple chips

MVP может сохранять chips последовательно, но UI обязан показывать результат каждого элемента.

Предпочтительно не использовать один bulk endpoint до появления ясной транзакционной семантики частичных ошибок.

## 12. Migration plan

Следующая migration после production head `0041`: предполагаемо `0042`.

Перед созданием migration coding-agent обязан проверить актуальный Alembic head и изменить номер при необходимости.

### 12.1 Migration 0042 scope

Включить:

1. расширение clinical review state;
2. `entry_kind`, onset precision/bucket/text и current_pattern для conditions;
3. `term_origin` и optional canonical concept reference для четырёх entity tables;
4. idempotency field/index;
5. optional global dictionary tables и seed — только если словарь готов к review;
6. constraints и indexes;
7. ENABLE/FORCE RLS для новых таблиц;
8. privileges без DELETE;
9. audit action values для review-state/lifecycle;
10. HC-026 duplicate activity update для любых новых пользовательских таблиц.

### 12.2 Split recommendation

Чтобы снизить риск, предпочтительны две миграции:

- `0042`: record/review model extensions;
- `0043`: curated dictionary tables and seed.

Typeahead может быть реализован сначала на Personal Dictionary + небольшом in-repo static dictionary, но production-ready предпочтение — database-backed curated dictionary.

Статический frontend-only словарь не должен становиться источником канонических ids.

## 13. RLS and privilege requirements

Для каждой новой пользовательской таблицы:

- ENABLE RLS;
- FORCE RLS;
- SELECT через `app_can_view_profile(profile_id)`;
- INSERT/UPDATE через `app_can_edit_profile(profile_id)`;
- immutable actor/profile fields;
- PUBLIC revoked;
- app role без DELETE;
- cross-user SQL tests;
- regression 54001 test.

Global dictionary:

- содержит не пользовательские данные;
- app role получает SELECT only;
- INSERT/UPDATE только migrator/admin process;
- PUBLIC revoked;
- RLS не требуется, если таблица действительно не содержит tenant data; это исключение явно документируется.

## 14. Audit events

Добавить или закрепить:

- `clinical_section.review_deferred`;
- `clinical_section.review_unknown`;
- `clinical_section.confirmed_none`;
- `clinical_section.confirmed_none_cleared`;
- `condition.lifecycle_changed`;
- `medication.course_paused`;
- `medication.course_resumed`;
- `medication.course_completed`;
- `medication.course_stopped`;
- аналогичные supplement events;
- `clinical_term.mapping_confirmed` — только для будущего AI/manual remap.

Не логировать typeahead query как audit event.

## 15. Backward compatibility

Существующие записи:

- сохраняют id и историю;
- `entry_kind` backfill = `unknown`;
- `term_origin` backfill = `free_text`, если нет подтверждённого dictionary provenance;
- `current_pattern` backfill выводится только из явного status там, где это однозначно:
  - resolved → resolved;
  - остальное → unknown;
- onset precision:
  - onset_date present → exact_date;
  - иначе unknown;
- completed/stopped courses остаются закрытыми;
- существующие API response fields не удаляются в первой версии.

Нельзя backfill-ить `diagnosis` только по наличию code.

## 16. Tests

### 16.1 Data model

- CHECK constraints для всех новых enum-like fields;
- migration up/down;
- backfill existing rows;
- no DELETE privilege;
- FORCE RLS scanner;
- HC-026 activity учитывает новые user-owned rows.

### 16.2 Isolation

Для каждой новой user-owned table:

- owner/editor write;
- viewer/analyze read-only;
- outsider sees 0 SQL rows and API 404;
- no context fail-closed;
- no recursion/54001 on warm rows.

### 16.3 Review state

- untouched = unknown;
- deferred persists;
- confirmed_none only with no records;
- first record clears confirmed_none/deferred;
- voiding last record does not create confirmed_none;
- concurrent review update returns 409.

### 16.4 Symptom invariant

- free-text symptom remains symptom;
- no endpoint silently changes it to diagnosis;
- canonical suggestion cannot set diagnosis without explicit payload/confirmation;
- unknown remains valid.

### 16.5 Course lifecycle

- paused → active allowed;
- completed → active rejected;
- stopped → active rejected;
- new POST creates new id;
- repeated client_request_id is idempotent.

### 16.6 Typeahead

- profile isolation for personal suggestions;
- free-text always available;
- user text does not mutate global dictionary;
- no external AI call;
- stable ranking tests for exact/prefix matches.

### 16.7 Frontend/mobile

- chips wrap without horizontal overflow;
- iOS input font size avoids zoom;
- keyboard submit and combobox navigation;
- touch targets;
- error retains draft;
- screen-reader labels/status;
- `Не сейчас` has neutral presentation;
- no completion percentage.

## 17. Implementation slices

### Slice A — Review state foundation

- DB/API `unknown/deferred/confirmed_none`;
- effective `has_entries`;
- WhyWeAsk component;
- «Не сейчас»;
- tests.

### Slice B — Typeahead and chips

- suggestion API;
- Global/Personal sources;
- free-text action;
- frontend combobox/chips;
- idempotent create.

### Slice C — Conditions factual questions

- entry kind;
- approximate onset;
- current pattern;
- symptom/diagnosis invariant tests.

### Slice D — Course lifecycle

- medication/supplement transitions;
- closed-course reactivation guard;
- create-new-course UX;
- audit.

### Slice E — Mobile/accessibility hardening

- bottom sheet/inline behavior;
- focus management;
- keyboard and screen reader;
- real-device viewport review.

Каждый slice проходит backend/frontend tests. Production rollout рассматривается только после завершения всех обязательных slices и отдельного решения.

## 18. Decisions fixed by this plan

1. Существующие clinical tables сохраняются и расширяются.
2. `has_entries` вычисляется, а не хранится как независимый пользовательский флаг.
3. `deferred` хранится на backend.
4. Симптом/диагноз различаются явным полем; default не diagnosis.
5. Приблизительная давность не превращается в фиктивную дату.
6. Повторяемость хранится отдельно от lifecycle status.
7. Свободный ввод — полноценный безопасный путь.
8. Пользовательский ввод не пополняет Global Dictionary.
9. AI normalization не входит в первый implementation slice.
10. Completed/stopped medication course нельзя реактивировать.
11. Каждый новый приём после закрытого курса — новая запись.
12. POST должен быть идемпотентным.
13. Production не меняется до отдельного rollout.

## 19. Open implementation choices

До кода необходимо выбрать только технические детали, не меняющие продуктовые решения:

- exact schema/name текущей review table после аудита migration `0038–0040`;
- `client_request_id` против общего Idempotency-Key storage;
- PostgreSQL trigram/full-text implementation для dictionary search;
- включать ли curated Global Dictionary в `0043` или начать с ограниченного provider-neutral seed;
- хранить synonyms массивом или отдельной таблицей.

Эти выборы должен предложить coding-agent после аудита кода, но они не должны пересматривать инварианты канонического UX.

## 20. Definition of ready for coding

Задача готова к разработке, когда:

- `CLINICAL-CONTEXT-INPUT-UX.md` принят;
- этот gap plan принят;
- migration head повторно подтверждён;
- определены точные текущие review models/routes;
- составлен file-level implementation plan;
- новая feature-ветка создана от актуального main;
- production rollout явно исключён из coding prompt.
