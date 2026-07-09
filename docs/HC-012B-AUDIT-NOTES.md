# HC-012b — audit result

Статус: `COMPLETED`  
Основание: актуальный `main`, production Alembic head `0036`.

Финальная техническая спецификация создана:

```text
docs/CLINICAL-CONTEXT-SLICE-2.md
```

## Подтверждённые опорные механизмы

- `health_compass.health_profiles` остаётся корневой сущностью профиля;
- `user_consents` переиспользуется для consent `health_data_processing`;
- `profile_audit_events` переиспользуется как append-only audit;
- `app_can_view_profile(uuid)` и `app_can_edit_profile(uuid)` задают permission matrix;
- owner/edit могут записывать, view/analyze только читают;
- cross-user API возвращает `404`;
- новые таблицы создаются вместе с ENABLE/FORCE RLS, policies и grants.

## Принятые решения

- отдельные типизированные таблицы для conditions, allergies, medications и supplements;
- отдельная минимальная таблица clinical safety flags;
- soft-delete/void вместо физического DELETE;
- manual records в Slice 2 создаются как confirmed;
- document/needs_review резервируются для будущего OCR flow;
- существующий audit constraint расширяется новыми действиями;
- migration `0037` обязана расширить HC-026 duplicate-user activity assessment;
- любая clinical history, включая voided, блокирует автоматическое поглощение как пустого пользователя;
- nutrition-таблицы в HC-012b не создаются;
- будущий HC-032 использует явный safety flag `nutrition_calorie_feedback_suppressed`, а не свободный текст.

## Следующий шаг

После принятия документационного PR создать `feat/clinical-context-slice-2` от актуального `main` и начать с migration `0037` и PostgreSQL RLS tests.
