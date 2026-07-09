# HC-025 — статус реализации

Дата: 2026-07-09  
Ветка: `feat/account-linking-mvp`  
PR: `#7`  
Статус: `IN PROGRESS / DO NOT DEPLOY`

## Реализовано

- аудит Google callback, Email Magic Link consume и bootstrap;
- удаление синтетических медицинских данных из bootstrap;
- запрет скрытой перезаписи `users.email` при обычном входе;
- `account_link_intents` с ENABLE/FORCE RLS;
- scalar lookup кандидатов по verified email;
- browser binding, hash-only storage и feature flag;
- pre-bootstrap interception в обоих обычных auth-потоках;
- один verified-email candidate → link intent вместо нового user/workspace/profile;
- несколько candidate users → статус HC-026 вместо создания нового дубля;
- экран `/auth/link-account`;
- отдельная таблица `account_link_email_tokens`;
- жёсткий purpose `link_email`;
- отдельные issue/consume SECURITY DEFINER functions;
- TTL, одноразовость, rate limit и browser-binding check;
- транзакционное добавление Google identity к существующему Email user;
- блокировка token и intent через `FOR UPDATE`;
- проверка ownership конфликтующей `(provider, subject)` identity;
- создание сессии существующего пользователя только после успешного completion;
- frontend-кнопка отправки специальной ссылки подтверждения;
- endpoint `/api/auth/link/google/start`;
- отдельный OIDC purpose `account_link`;
- state/nonce/PKCE hashes записываются в intent до redirect к Google;
- Google callback различает обычный login и account-linking;
- browser binding доступен start и callback через общую HttpOnly cookie область `/api/auth`;
- подтверждённый Google `sub` обязан принадлежать candidate user;
- verified Google email обязан совпадать с intent email;
- транзакционное добавление Email identity к существующему Google user;
- повторный callback разрешён идемпотентно только при полном совпадении browser/state/nonce/PKCE bindings;
- после completion создаётся session существующего candidate user;
- отдельный endpoint отказа от linking;
- отказ меняет intent на `declined` и сам по себе не создаёт user/workspace/profile;
- separate-account разрешён только после decline и второго явного подтверждения;
- claim declined intent выполняется транзакционно с browser-binding check;
- отдельный user, identity, workspace и пустой profile создаются только после подтверждения `CREATE_SEPARATE_ACCOUNT`;
- audit helpers и события `identity.link_declined`, `identity.link_failed`, `identity.separate_account_confirmed`;
- frontend показывает последствия отдельного аккаунта и требует повторного подтверждения;
- обе completion-функции возвращают реальный `intent_id`, `user_id` и признак replay;
- successful completion audit пишется для обоих направлений linking;
- повторный `link_email` consume получает безопасный идемпотентный результат;
- после первого успешного linking отправляется security notification;
- ошибка отправки уведомления не откатывает linking и фиксируется отдельным audit-событием;
- API `GET /api/auth/identities` показывает подключённые способы входа без раскрытия provider subject;
- экран `/app/sign-in-methods` показывает Google и Email Magic Link, verified status и запрет удаления последнего способа;
- authenticated settings flow запускает тот же account-link intent через `/api/auth/link/settings/start`;
- settings flows `settings_add_google` и `settings_add_email` имеют отдельные purpose-aware completion branches;
- из desktop и mobile profile UI добавлена ссылка «Способы входа»;
- helper собирает все уникальные подтверждённые identity emails для последующих security notifications.

## Не завершено

- подключение рассылки уведомлений ко всем подтверждённым адресам вместо одного канонического;
- endpoint отключения identity со step-up и запретом последней identity;
- HC-026 для существующих дублей;
- полный набор PostgreSQL/RLS/concurrency/API/frontend tests;
- исправление downgrade implementation миграции `0029` до полного Alembic cycle;
- локальный Ruff, pytest, frontend test/build и Alembic up/down cycle;
- CI review и deployment.

## Текущая migration chain

```text
0022
→ 0023 account_link_intents + verified-email lookup
→ 0024 narrow intent creation function
→ 0025 purpose-specific link_email tokens + completion
→ 0026 Google link preparation + completion
→ 0027 decline + explicit separate-account + audit helpers
→ 0028 result-returning completion + replay context
→ 0029 purpose-aware settings completion
```

Миграции не применялись в production. Feature flag по умолчанию выключен.

## Следующий кодовый блок

1. завершить notification fan-out на все verified addresses;
2. добавить tests для identities API и settings flow;
3. исправить и проверить downgrade `0029`;
4. полный PostgreSQL/RLS/concurrency/API/frontend test matrix;
5. HC-026 для существующих дублей.
