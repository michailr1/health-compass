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
- frontend-кнопка отправки специальной ссылки подтверждения.

## Не завершено

- Google confirmation flow для сценария Email-first → Google-second;
- отдельные link-purpose state/nonce/PKCE и callback completion;
- идемпотентная обработка повторного успешно завершённого callback/consume;
- decline и отдельное двойное подтверждение создания отдельного аккаунта;
- audit events и security notifications;
- UI «Способы входа» в настройках;
- HC-026 для существующих дублей;
- полный набор PostgreSQL/RLS/concurrency/API/frontend tests;
- локальный Ruff, pytest, frontend test/build и Alembic up/down cycle;
- CI review и deployment.

## Текущая migration chain

```text
0022
→ 0023 account_link_intents + verified-email lookup
→ 0024 narrow intent creation function
→ 0025 purpose-specific link_email tokens + completion
```

Миграции не применялись в production. Feature flag по умолчанию выключен.

## Следующий кодовый блок

1. `/api/auth/link/google/start`;
2. запись hash state/nonce/PKCE в intent;
3. Google callback с purpose `account_link`;
4. транзакционное добавление Email identity к существующему Google user;
5. идемпотентное завершение intent;
6. negative и concurrency tests.
