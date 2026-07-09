# HC-012b — audit starting point

Статус: `AUDIT IN PROGRESS`  
Основание: актуальный `main`, production Alembic head `0036`.

## Уже существующие опорные сущности

- `health_compass.health_profiles` содержит идентичность профиля, имя, дату рождения, пол, рост и timezone;
- `body_measurements` используется для исторических измерений веса;
- `user_consents` хранит versioned consent records;
- `profile_audit_events` — append-only audit для изменений медицинского профиля;
- права профиля используют owner/edit/analyze/view;
- запись разрешена owner/edit, view/analyze остаются read-only;
- cross-user API должен возвращать `404`;
- новые пользовательские таблицы обязаны получать ENABLE/FORCE RLS, политики и grants в той же миграции.

## Предварительный scope HC-012b

- состояния и диагнозы, сообщённые пользователем;
- аллергии и непереносимости;
- лекарства;
- витамины, минералы и БАДы;
- статус active/inactive;
- даты начала и окончания;
- дозировка, единица и частота;
- provenance manual/document;
- user confirmation;
- append-only audit;
- soft validation без расчёта или рекомендации доз;
- нейтральные empty states и явное «не заполнять сейчас».

## Nutrition compatibility

HC-012b не создаёт nutrition-таблицы. Он должен сохранить совместимость с будущей PHASE-05.5:

- clinical context предоставляет аллергии, состояния и safety-флаги для будущей персонализации;
- применяется общий паттерн `raw/machine proposal → human confirmation → normalized fact`;
- расстройства пищевого поведения и аналогичные safety-флаги должны быть представлены так, чтобы будущий HC-032 мог отключить калорийные/весовые рекомендации;
- физические `meal_capture`, `meal_analysis`, `meal`, `meal_item`, internal food ID и meal type создаются только в PHASE-05.5.

## Вопросы, которые должен закрыть полный аудит

1. Отдельные таблицы для каждого типа clinical context или единая polymorphic entity.
2. Как представлять coded/uncoded значения без преждевременной привязки к одному медицинскому справочнику.
3. Состав статусов и правила окончания курса/состояния.
4. Гранулярность provenance и confirmation.
5. Как использовать существующий `profile_audit_events` без дублирования аудита.
6. Какие поля считать значимой активностью для HC-026 duplicate assessment.
7. Полный API и frontend information architecture.
8. Migration number после текущего head `0036`.

Этот файл является промежуточной записью аудита, а не финальной технической спецификацией.
