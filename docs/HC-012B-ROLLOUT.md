# HC-012b Clinical Context — production rollout

Статус: `ROLLOUT FULLY ACCEPTED`  
Код в production: `1eafe48ac4c4ca08e6b12d6342a974192faac285`  
Alembic: `0041 (head)`  
Production deployment: выполнен 2026-07-10

## Production frontend serving path

Для `https://health.funti.cc` Apache использует:

```text
DocumentRoot /opt/health-compass/current-subdomain
```

Поэтому frontend rollout обязан атомарно переключать именно:

```text
/opt/health-compass/current-subdomain
```

а не `/opt/health-compass/current`.

Перед принятием rollout необходимо подтвердить не только symlink, но и реально выдаваемый HTTP bundle:

1. получить production `index.html` через `curl`;
2. извлечь имя подключённого JS asset;
3. сравнить его с `index.html` нового release;
4. проверить JS asset по HTTP (`200`);
5. для функциональных rollout — проверить наличие ожидаемого маркерного текста или другого признака новой сборки.

`/opt/health-compass/current` может существовать параллельно, но не является serving path для `health.funti.cc`.

## Предварительные условия

- подключение только к production-хосту Health Compass;
- чистый git worktree;
- текущий production HEAD и Alembic revision зафиксированы в отчёте;
- создан и проверен PostgreSQL backup;
- роль `health_compass_rls_definer` существует как `NOLOGIN BYPASSRLS`;
- `health_compass_migrator` состоит в `health_compass_rls_definer`;
- свободное место и состояние backend/frontend проверены;
- Apache serving path для `health.funti.cc` подтверждён как `/opt/health-compass/current-subdomain`;
- секреты не выводятся в журнал или отчёт.

## Порядок rollout

1. Зафиксировать `HEAD_BEFORE`, текущую Alembic revision и target `/opt/health-compass/current-subdomain`.
2. Создать backup базы данных.
3. Получить конкретный target commit.
4. Установить backend-зависимости без изменения секретов.
5. Выполнить backend compile.
6. Собрать frontend в новый immutable release directory.
7. Выполнить необходимые Alembic migrations мигратором.
8. Проверить целевую Alembic revision.
9. Перезапустить backend и дождаться готовности, если backend изменён.
10. Переключить `/opt/health-compass/current-subdomain` только после успешной backend/migration проверки.
11. Через HTTP подтвердить, что production `index.html` подключает bundle нового release.
12. Выполнить smoke tests и security probes.
13. Наблюдать свежие логи минимум несколько минут.

## Обязательные smoke tests

- `/api/health` → `200`;
- `/` → `200`;
- `/app/profile` → `200`;
- production `index.html` подключает JS bundle нового release;
- JS/CSS assets нового release доступны без `404`;
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
- в логах отсутствуют `54001`, `42501`, неожиданные `permission denied`, `Traceback`, `ERROR`, `CRITICAL`.

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

При frontend-ошибке после переключения:

- вернуть `/opt/health-compass/current-subdomain` на предыдущий release;
- повторно проверить production `index.html` и HTTP assets;
- backend и базу не менять, если ошибка ограничена frontend.

При ошибке после применения миграций:

- сначала остановить rollout и сохранить логи;
- не выполнять автоматический downgrade с потерей clinical data;
- откат приложения выполнять с сохранением новой схемы либо через восстановление backup по отдельному решению.

## Stop conditions

Немедленно остановить rollout при:

- несовпадении production-хоста;
- грязном worktree;
- несовпадении ожидаемого commit;
- неуспешном backup;
- ошибке миграции;
- неготовом backend;
- Apache обслуживает не тот release, который указан в отчёте;
- production `index.html` подключает старый bundle;
- cross-user visibility;
- любом `5xx`, `54001`, `42501` или RLS bypass;
- утечке секрета в вывод.

## Отчёт VPS-агента

Отчёт должен содержать:

- backup path;
- `HEAD_BEFORE` и `HEAD_AFTER`;
- Alembic before/after;
- frontend release path;
- `current-subdomain` before/after;
- production bundle name before/after;
- HTTP asset verification;
- статусы systemd;
- результаты HTTP smoke tests;
- результаты Clinical Context permission probes;
- выдержку только из свежих логов без секретов;
- итог `ROLLOUT ACCEPTED` или точную stop condition.
