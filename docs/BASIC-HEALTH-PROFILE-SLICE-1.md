# Health Compass — Basic Health Profile, Slice 1

Версия: 1.0  
Дата: 2026-07-09  
Статус: approved technical specification / implementation pending  
Фаза: PHASE-02.5 Progressive Health Intake  
Базовый migration head: `0021`  
Планируемая миграция: `0022_add_basic_health_profile_and_measurements.py`

## 1. Назначение

Slice 1 создаёт минимальный, добровольно заполняемый паспорт здоровья и историю веса до реализации Documents/OCR.

Цель — дать будущим лабораторным референсам, расчёту ИМТ, timeline и AI минимальный подтверждённый контекст, не превращая onboarding в блокирующую медицинскую анкету.

Slice 1 не является диагностикой и не делает медицинских выводов.

## 2. Источники истины

Приоритет:

1. фактический код, миграции и тесты `main`;
2. подтверждённое production-состояние релиза `v0.1.0-auth-mvp`;
3. `docs/SECURITY-INVARIANTS.md`;
4. этот документ и `docs/PROGRESSIVE-HEALTH-INTAKE.md`;
5. внешние baseline-материалы и ревью Fable.

Фактическая схема уже содержит `health_compass.health_profiles`. Новая таблица с тем же именем не создаётся.

## 3. Scope

### 3.1 Входит в Slice 1

- редактирование имени профиля;
- дата рождения;
- поле `sex`;
- рост;
- часовой пояс профиля;
- история веса;
- минимальный consent gate до записи медицинских данных;
- provenance для новых значений;
- append-only аудит;
- contextual readiness;
- Health Profile screen;
- autosave стабильных полей профиля;
- RLS и cross-user negative tests;
- soft validation необычных значений.

### 3.2 Не входит

- состояния, аллергии, лекарства, витамины, минералы и БАДы — Slice 2;
- `IntakePromptCard` и analysis-only context — Slice 3;
- Documents/OCR — Slice 4 и следующие фазы;
- питание, сон, спорт, wearable ingestion и genetics;
- давление и составные vitals;
- семейный анамнез;
- автоматическая диагностика;
- автоматическое изменение профиля из OCR или AI;
- пользовательский выбор imperial/metric units.

## 4. Принятые решения

### 4.1 Существующий профиль расширяется

Используется существующая таблица:

```text
health_compass.health_profiles
```

Существующие поля:

- `id`;
- `workspace_id`;
- `owner_user_id`;
- `display_name`;
- `date_of_birth`;
- `sex`;
- `created_at`.

Новые стабильные поля добавляются в неё. Отдельная таблица `health_profiles` не создаётся.

### 4.2 Пол

Backend field остаётся `sex`.

Допустимые значения:

```text
male
female
not_specified
NULL
```

Пользовательский label: «Пол».

Поле опционально и применяется только там, где выбор лабораторного референса требует этого контекста. Пол и гендер в MVP не разделяются.

### 4.3 Канонические единицы

В БД:

- рост — сантиметры;
- вес — килограммы.

Конверсия единиц выполняется на API/UI-границе в будущей версии. `preferred_units` не является медицинским атрибутом профиля и не входит в Slice 1.

### 4.4 Вес — история, а не перезаписываемое поле

Вес не добавляется колонкой `health_profiles.weight`.

Каждое измерение является отдельной записью `body_measurements`.

### 4.5 Исправление измерений

Физический DELETE не используется.

Ошибочная запись помечается voided, после чего при необходимости создаётся новая запись. Исходное значение остаётся доступным для аудита.

### 4.6 Readiness — не health score

Система показывает готовность для конкретных функций:

- возрастные референсы;
- референсы с учётом пола;
- расчёт ИМТ;
- корректное локальное время событий.

Она не показывает оценку здоровья и не делает медицинских выводов.

## 5. Модель данных

## 5.1 Изменения `health_profiles`

Добавить:

| Колонка | Тип | Null | Правило |
|---|---|---:|---|
| `height_cm` | `numeric(5,2)` | yes | `> 0` |
| `timezone` | `varchar(64)` | yes | IANA timezone, проверяется API |
| `updated_at` | `timestamptz` | no | default `now()` |

Добавить CHECK для `sex`:

```sql
sex IS NULL OR sex IN ('male', 'female', 'not_specified')
```

Перед добавлением CHECK миграция должна fail-fast проверить существующие значения и не преобразовывать их молча.

Не изменяются через Profile PATCH:

- `id`;
- `workspace_id`;
- `owner_user_id`;
- `created_at`.

## 5.2 `body_measurements`

```text
id                    uuid primary key
profile_id            uuid not null
measurement_type      varchar(32) not null
value                 numeric(12,4) not null
unit                  varchar(16) not null
measured_at           timestamptz not null
source_type           varchar(32) not null
confirmation_status   varchar(32) not null
created_by_user_id    uuid not null
created_at            timestamptz not null default now()
voided_at             timestamptz null
voided_by_user_id     uuid null
void_reason           varchar(500) null
```

Foreign keys:

- `profile_id → health_profiles.id`;
- `created_by_user_id → users.id`;
- `voided_by_user_id → users.id`.

Slice 1 constraints:

```text
measurement_type = weight
unit = kg
source_type = manual
confirmation_status = confirmed
value > 0
```

`source_document_id` не добавляется до появления Documents pipeline и реальной referential integrity.

Индекс:

```sql
CREATE INDEX ...
ON health_compass.body_measurements
(profile_id, measurement_type, measured_at DESC)
WHERE voided_at IS NULL;
```

## 5.3 `profile_audit_events`

```text
id              uuid primary key
profile_id      uuid not null
actor_user_id   uuid not null
entity_type     varchar(64) not null
entity_id       uuid not null
action          varchar(64) not null
changed_fields  jsonb not null
request_id      varchar(128) null
occurred_at     timestamptz not null default now()
```

Foreign keys:

- `profile_id → health_profiles.id`;
- `actor_user_id → users.id`.

Допустимые события Slice 1:

```text
profile.updated
body_measurement.created
body_measurement.voided
```

Таблица append-only:

- разрешены SELECT и INSERT;
- UPDATE и DELETE runtime-роли не выдаются;
- медицинское значение веса не дублируется в audit event без необходимости.

Индекс:

```sql
CREATE INDEX ...
ON health_compass.profile_audit_events
(profile_id, occurred_at DESC);
```

## 5.4 Минимальный consent gate

Создать `user_consents`:

```text
id                uuid primary key
user_id           uuid not null
consent_type      varchar(64) not null
document_version  varchar(32) not null
accepted_at       timestamptz not null
revoked_at        timestamptz null
created_at        timestamptz not null default now()
```

Slice 1 consent type:

```text
health_data_processing
```

Медицинские поля и измерения нельзя сохранять без активного consent.

Изменение только `display_name` не требует нового health-data consent.

Полный consent center, экспорт и lifecycle согласий реализуются в отдельной фазе.

## 6. Provenance

Для новых измерений provenance фиксируется полями:

- `source_type = manual`;
- `confirmation_status = confirmed`;
- `created_by_user_id`;
- `created_at`.

Для стабильных полей профиля источник фиксируется audit event. В Slice 1 источник всегда `manual`.

Будущие значения:

```text
document
device
import
```

не реализуются до соответствующих модулей.

## 7. RLS и permissions

## 7.1 Новый helper

Создать:

```sql
health_compass.app_can_edit_profile(target_profile_id uuid)
```

Возвращает `true`, если текущий пользователь:

- является `health_profiles.owner_user_id`;
- либо имеет permission `owner` или `edit`.

`view` и `analyze` не дают права записи.

Функция:

- `LANGUAGE sql`;
- `STABLE`;
- `SECURITY DEFINER`;
- `SET search_path = ''`;
- `SET row_security = off`;
- owner: `health_compass_rls_definer`;
- `REVOKE ALL ... FROM PUBLIC`;
- `GRANT EXECUTE ... TO health_compass_app`.

## 7.2 `health_profiles`

SELECT продолжает использовать существующую модель доступа.

Добавить UPDATE policy:

```sql
USING (health_compass.app_can_edit_profile(id))
WITH CHECK (health_compass.app_can_edit_profile(id))
```

Runtime-роли выдаётся column-level UPDATE только на:

- `display_name`;
- `date_of_birth`;
- `sex`;
- `height_cm`;
- `timezone`;
- `updated_at`.

## 7.3 `body_measurements`

SELECT:

```sql
USING (health_compass.app_can_view_profile(profile_id))
```

INSERT:

```sql
WITH CHECK (
  created_by_user_id = health_compass.app_current_user_id()
  AND health_compass.app_can_edit_profile(profile_id)
)
```

UPDATE разрешён только для void-колонок и только пользователю с edit-доступом.

DELETE policy отсутствует.

## 7.4 `profile_audit_events`

SELECT:

```sql
USING (health_compass.app_can_view_profile(profile_id))
```

INSERT:

```sql
WITH CHECK (
  actor_user_id = health_compass.app_current_user_id()
  AND health_compass.app_can_edit_profile(profile_id)
)
```

UPDATE/DELETE отсутствуют.

## 7.5 `user_consents`

Пользователь читает и создаёт только собственные consent-записи.

Отзыв согласия выполняется контролируемой операцией UPDATE собственной записи. Чужие consent-записи недоступны.

## 7.6 Обязательные инварианты миграции

В той же миграции для каждой новой таблицы:

```text
ENABLE ROW LEVEL SECURITY
FORCE ROW LEVEL SECURITY
policies
runtime grants
indexes
```

Новая таблица пользовательских данных не может существовать между миграциями без FORCE RLS и политик.

## 8. API contracts

## 8.1 Получение профиля

```http
GET /profiles/{profile_id}
```

Ответ расширяется:

```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "owner_user_id": "uuid",
  "display_name": "Михаил",
  "date_of_birth": "1985-01-01",
  "sex": "male",
  "height_cm": 188.0,
  "timezone": "Europe/Paris",
  "readiness": {
    "age_references": true,
    "sex_specific_references": true,
    "bmi": true,
    "local_time_context": true,
    "missing_fields": []
  }
}
```

Чужой или недоступный UUID возвращает `404`, не `403`.

## 8.2 Редактирование профиля

```http
PATCH /profiles/{profile_id}
```

Request:

```json
{
  "display_name": "Михаил",
  "date_of_birth": "1985-01-01",
  "sex": "male",
  "height_cm": 188.0,
  "timezone": "Europe/Paris"
}
```

PATCH semantics:

- поле отсутствует — не изменять;
- `null` — очистить опциональное поле;
- значение — проверить и сохранить.

Медицинские поля требуют активного consent.

## 8.3 История измерений

```http
GET /profiles/{profile_id}/body-measurements?type=weight
```

По умолчанию возвращаются только active/non-voided записи, сортировка:

```text
measured_at DESC, created_at DESC
```

Для audit/debug отдельный параметр `include_voided=true` доступен только пользователю с edit-доступом.

## 8.4 Добавление веса

```http
POST /profiles/{profile_id}/body-measurements
```

Request:

```json
{
  "measurement_type": "weight",
  "value": 98.0,
  "unit": "kg",
  "measured_at": "2026-07-09T08:00:00+02:00",
  "confirm_unusual_value": false
}
```

## 8.5 Аннулирование измерения

```http
POST /profiles/{profile_id}/body-measurements/{measurement_id}/void
```

Request:

```json
{
  "reason": "Ошибка ввода"
}
```

Повторный void должен быть идемпотентным либо возвращать контролируемый `409` — выбрать один вариант и закрепить тестом. Рекомендуется идемпотентный ответ.

## 8.6 Consent

```http
GET  /consents/health-data-processing
POST /consents/health-data-processing/accept
POST /consents/health-data-processing/revoke
```

Accept request содержит `document_version`.

## 9. Readiness rules

```text
age_references:
  date_of_birth != null

sex_specific_references:
  sex in [male, female]

bmi:
  height_cm != null
  and exists active weight measurement

local_time_context:
  timezone != null
```

`not_specified` не блокирует портал. Оно означает отсутствие конкретного полового контекста для функций, которым он нужен.

## 10. Validation

## 10.1 Hard validation

Отклонять:

- дату рождения в будущем;
- `height_cm <= 0`;
- `weight <= 0`;
- NaN/Infinity;
- неизвестную единицу;
- неизвестный `measurement_type`;
- невалидную IANA timezone;
- неизвестное значение `sex`;
- `measured_at` в невалидном формате.

## 10.2 Soft validation

Необычные значения не объявляются медицински неправильными. UI просит подтвердить возможную опечатку или единицу.

Примеры:

```text
Рост 18 см выглядит необычно. Проверьте значение и единицы.
Вес 980 кг выглядит необычно. Сохранить значение?
```

Backend требует `confirm_unusual_value=true`, если значение попало в заранее определённый технический warning range.

Пороги должны называться input sanity thresholds, а не медицинскими нормами.

## 11. Транзакции

Один HTTP request — одна DB transaction с transaction-local RLS context.

PATCH профиля:

```text
set RLS context
→ verify consent when medical fields change
→ SELECT profile
→ UPDATE allowlisted fields
→ INSERT audit event
→ COMMIT
```

Добавление веса:

```text
set RLS context
→ verify consent
→ INSERT body_measurement
→ INSERT audit event
→ COMMIT
```

Void:

```text
set RLS context
→ SELECT measurement
→ UPDATE void columns
→ INSERT audit event
→ COMMIT
```

Промежуточный commit запрещён, потому что он сбрасывает transaction-local RLS context.

## 12. Frontend

## 12.1 Route

```text
/app/profile
```

Текущий пользователь в Slice 1 имеет один bootstrap-профиль. Активный `profile_id` берётся из `/profiles`.

Поддержка переключения нескольких профилей проектируется отдельно.

## 12.2 Entry points

Desktop:

- кликабельная карточка пользователя в нижней части sidebar;
- в будущем — группа «Профиль».

Mobile:

- кликабельное имя/иконка пользователя в top bar;
- в будущем — раздел «Ещё».

Седьмой пункт в текущую bottom navigation не добавляется.

## 12.3 Экран

Секции:

1. Основные сведения.
2. Contextual readiness.
3. Вес.
4. Источники и история изменений.
5. Privacy/consent summary.

Компоненты Slice 1:

- `HealthProfilePage`;
- `HealthProfileForm`;
- `ProfileReadinessCard`;
- `WeightEntryForm`;
- `WeightHistoryList`;
- `WeightTrendChart`;
- `WhyWeAskPopover`;
- `ConsentGate`;
- `AutosaveStatus`.

`IntakePromptCard` не входит в Slice 1.

## 12.4 Autosave

Autosave применяется только к стабильным полям профиля:

- debounce 600–1000 мс;
- отправляются только изменённые поля;
- состояния: «Сохраняется», «Сохранено», «Ошибка сохранения»;
- сетевой сбой не должен молча терять введённые данные.

Вес не autosave. Пользователь явно нажимает «Добавить измерение».

## 12.5 UX wording

Не использовать:

- «Ваше здоровье 70/100»;
- красный incompleteness score;
- диагнозоподобные формулировки.

Использовать:

```text
Готово для возрастных референсов
Для расчёта ИМТ добавьте рост и хотя бы одно измерение веса
```

## 13. Backend implementation map

Планируемые изменения:

```text
backend/alembic/versions/0022_add_basic_health_profile_and_measurements.py
backend/app/models/profile.py
backend/app/models/body_measurement.py
backend/app/models/profile_audit_event.py
backend/app/models/consent.py
backend/app/schemas/identity.py
backend/app/schemas/health_profile.py
backend/app/api/routes/identity.py
backend/app/api/routes/body_measurements.py
backend/app/api/routes/consents.py
backend/app/services/health_profile.py
backend/app/services/body_measurements.py
backend/app/services/consents.py
backend/tests/test_health_profile_api.py
backend/tests/test_health_profile_rls.py
backend/tests/test_body_measurements.py
backend/tests/test_consents.py
```

Точное расположение может быть скорректировано под фактическую структуру без изменения API и security invariants.

## 14. Frontend implementation map

```text
src/pages/HealthProfile.tsx
src/components/health-profile/HealthProfileForm.tsx
src/components/health-profile/ProfileReadinessCard.tsx
src/components/health-profile/WeightEntryForm.tsx
src/components/health-profile/WeightHistoryList.tsx
src/components/health-profile/WeightTrendChart.tsx
src/components/health-profile/WhyWeAskPopover.tsx
src/components/health-profile/AutosaveStatus.tsx
src/api/healthProfile.ts
src/types/healthProfile.ts
```

Обновить:

```text
src/App.tsx
src/components/AppLayout.tsx
```

## 15. Тестовая матрица

### 15.1 Migration

- `0021 → 0022`;
- `0022 → 0021`;
- повторный `0021 → 0022`;
- production DB никогда не используется;
- существующие profiles/permissions сохраняются;
- неизвестное существующее значение `sex` вызывает fail-fast.

### 15.2 RLS

Два пользователя A/B и существующие warm rows:

- A читает свой профиль и веса;
- B читает свой профиль и веса;
- A не читает `body_measurements` B;
- A не читает audit B;
- A не создаёт вес для B;
- A не void-ит вес B;
- `view` и `analyze` читают, но не пишут;
- `edit` и `owner` пишут;
- без `app.current_user_id` SELECT возвращает 0 строк;
- без контекста INSERT/UPDATE отклоняются;
- запросы не вызывают SQLSTATE `54001`;
- новые таблицы имеют `relrowsecurity=true` и `relforcerowsecurity=true`;
- PUBLIC не имеет EXECUTE на `app_can_edit_profile`.

### 15.3 API

- чужой UUID возвращает `404`;
- PATCH не принимает ownership/workspace/system fields;
- PATCH различает omitted/null/value;
- medical PATCH без consent отклоняется;
- display name можно менять независимо;
- weight без consent отклоняется;
- soft warning требует подтверждения;
- void сохраняет исходную запись;
- audit event создаётся в той же транзакции;
- rollback откатывает и data change, и audit event.

### 15.4 Frontend

- route защищён auth guard;
- загрузка existing profile;
- autosave debounce;
- error/retry state;
- consent gate;
- unusual value confirmation;
- empty weight state;
- history и chart после 2+ точек;
- mobile layout;
- отсутствие health score.

## 16. Acceptance criteria

Slice 1 готов к review, когда:

- реализована миграция `0022`;
- все новые таблицы созданы с ENABLE+FORCE RLS и policies в одной миграции;
- существующий `health_profiles` расширен без потери production-данных;
- owner/edit могут менять разрешённые поля;
- view/analyze не могут менять данные;
- вес хранится историей;
- ошибочная запись voided, а не удаляется;
- audit append-only;
- consent gate блокирует запись медицинских данных без согласия;
- API возвращает `404` для чужих ресурсов;
- readiness не является медицинской оценкой;
- backend compileall, Ruff и pytest проходят;
- frontend build, lint и tests проходят;
- migration up/down тестируется на отдельной test DB;
- cross-user tests и regression `54001` проходят;
- review завершён до deployment;
- deployment выполняется только отдельной командой.

## 17. Порядок реализации

1. Создать feature-ветку от актуального `main`.
2. Реализовать migration `0022` и DB tests.
3. Реализовать ORM и service layer.
4. Реализовать API contracts.
5. Реализовать backend RLS/API tests.
6. Реализовать frontend route и components.
7. Реализовать frontend tests.
8. Обновить каноническую документацию.
9. Провести code/security review.
10. Только после отдельного решения подготовить production deployment task.

## 18. Deployment restriction

Этот документ не является разрешением на deployment.

VPS-агент не пишет продуктовый код и не принимает архитектурных решений. Он получает отдельную точную задачу только после merge/review/test gate.