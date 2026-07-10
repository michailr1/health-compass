# HC-012b Clinical Context — production rollout

Статус: `READY FOR CONTROLLED ROLLOUT`  
Код в `main`: `ccc033127b6f9755cc7ea16f2cc2893a8bce2e7a`  
Alembic target: `0040`  
Production deployment: не выполнен

## Предварительные условия

- подключение только к production-хосту Health Compass;
- чистый git worktree;
- текущий production HEAD и Alembic revision зафиксированы в отчёте;
- создан и проверен PostgreSQL backup;
- роль `health_compass_rls_definer` существует как `NOLOGIN BYPASSRLS`;
- `health_compass_migrator` состоит в `health_compass_rls_definer`;
- свободное место и состояние backend/frontend проверены;
- секреты не выводятся в журнал или отчёт.

## Порядок rollout

1. Зафиксировать `HEAD_BEFORE`, текущую Alembic revision и активный release symlink.
2. Создать backup базы данных.
3. Получить конкретный commit `ccc033127b6f9755cc7ea16f2cc2893a8bce2e7a`.
4. Установить backend-зависимости без изменения секретов.
5. Выполнить backend compile.
6. Собрать frontend в новый immutable release directory.
7. Выполнить `alembic upgrade head` мигратором.
8. Проверить Alembic revision `0040`.
9. Перезапустить backend и дождаться готовности.
10. Переключить frontend symlink только после успешной backend/migration проверки.
11. Выполнить smoke tests и security probes.
12. Наблюдать свежие логи минимум несколько минут.

## Обязательные smoke tests

- `/api/health` → `200`;
- `/` → `200`;
- `/app/profile` → `200`;
- существующий вход через Google работает;
- существующий вход через Magic Link работает;
- Clinical Context summary загружается;
- пользователь может добавить ручную condition/allergy/medication/supplement запись;
- пользователь может подтвердить пустой раздел;
- попытка подтвердить пустой раздел при активной записи отклоняется;
- view/analyze не могут менять Clinical Context;
- чужой профиль через API возвращает `404`;
- app-role не может выполнить DELETE;
- app-role не может записать `document/needs_review`;
- voided запись не изменяется повторно;
- в логах отсутствуют `54001`, `42501`, `permission denied`, `Traceback`, `ERROR`, `CRITICAL`.

## Проверка схемы после миграции

Должны существовать:

- `profile_conditions`;
- `profile_allergies`;
- `profile_medications`;
- `profile_supplements`;
- `profile_clinical_safety_flags`;
- `profile_clinical_reviews`.

Для каждой таблицы должны быть включены:

- `relrowsecurity = true`;
- `relforcerowsecurity = true`.

У `health_compass_app` не должно быть DELETE privileges на этих таблицах.

## Rollback

При ошибке до применения миграций:

- не переключать frontend release;
- вернуть прежний backend release/commit.

При ошибке после применения миграций:

- сначала остановить rollout и сохранить логи;
- не выполнять автоматический downgrade с потерей clinical data;
- если новые данные ещё не создавались, допускается контролируемый downgrade `0040 → 0036` после отдельной проверки;
- если данные уже создавались, откат приложения выполняется с сохранением новой схемы либо через восстановление backup по отдельному решению.

## Stop conditions

Немедленно остановить rollout при:

- несовпадении production-хоста;
- грязном worktree;
- несовпадении ожидаемого commit;
- неуспешном backup;
- ошибке миграции;
- неготовом backend;
- cross-user visibility;
- любом `5xx`, `54001`, `42501` или RLS bypass;
- утечке секрета в вывод.

## Отчёт VPS-агента

Отчёт должен содержать:

- backup path;
- `HEAD_BEFORE` и `HEAD_AFTER`;
- Alembic before/after;
- frontend release path и symlink target;
- статусы systemd;
- результаты HTTP smoke tests;
- результаты Clinical Context permission probes;
- выдержку только из свежих логов без секретов;
- итог `ROLLOUT ACCEPTED` или точную stop condition.
