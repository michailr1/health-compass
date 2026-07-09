# HC-025 / HC-026 — статус реализации

Дата: 2026-07-09  
Ветка: `feat/account-linking-mvp`  
PR: `#7`  
Статус: `IN PROGRESS / DO NOT DEPLOY`

## HC-025 реализовано

- symmetric link-on-login для Google и Email Magic Link;
- pre-bootstrap interception без создания второго user/workspace/profile;
- `account_link_intents` и purpose-specific `link_email` tokens с ENABLE/FORCE RLS;
- browser binding, hash-only storage, TTL, rate limit, state/nonce/PKCE;
- transactional identity attachment в обоих направлениях;
- idempotent callback/consume с реальными `intent_id`, `user_id`, `replayed`;
- explicit decline без создания аккаунта;
- отдельный аккаунт только после второго явного подтверждения;
- audit и security notifications на все verified addresses;
- authenticated API и UI «Способы входа»;
- settings flows `settings_add_google` и `settings_add_email`;
- запрет скрытой перезаписи `users.email`;
- удаление синтетических медицинских данных из bootstrap;
- step-up отключение identity через другой подключённый способ;
- отдельные purpose `identity_removal` и `remove_identity_email`;
- hard guard последней identity в UI и транзакционной SQL-функции;
- audit, notifications и replay-safe removal intent;
- PostgreSQL/RLS/static/unit/frontend/concurrency tests добавлены в код.

## HC-026 реализовано

- консервативная оценка существующей пары дублей;
- assessment доступен только для пары, содержащей текущий `app.current_user_id`;
- внутренний activity helper недоступен app-role;
- автоматическое поглощение допускается только для пустого bootstrap-user;
- значимыми считаются:
  - настройки профиля;
  - dashboard snapshots;
  - body measurements;
  - profile audit events;
  - user consents;
  - внешние/shared workspace memberships;
  - внешние/shared profile permissions;
- если оба аккаунта пусты, каноническим становится более старый;
- если данные есть в обоих профилях, автоматический merge блокируется;
- отдельные RLS-таблицы `duplicate_resolution_intents` и `duplicate_resolution_email_tokens`;
- отдельный email purpose `resolve_duplicate_email`;
- отдельный Google OIDC purpose `duplicate_resolution`;
- второй аккаунт подтверждается именно его отличающейся identity;
- перед absorption assessment выполняется повторно внутри той же транзакции;
- helper absorption недоступен app-role и вызывается только через completion-функции;
- identities пустого дубля переносятся на canonical user;
- сессии поглощаемого user отзываются;
- пустые workspace/profile поглощаемого user удаляются;
- медицинские записи не переносятся и общий data merge отсутствует;
- absorbed user удаляется;
- resolution intent сохраняется при удалении initiating/absorbed user через `ON DELETE SET NULL`;
- после completion создаётся новая сессия canonical user;
- email и Google completion идемпотентны;
- candidate lookup использует portable `array_agg(uuid)` вместо `min(uuid)` и не создаёт temp tables;
- добавлен PostgreSQL concurrency test полного absorption: один completion, один replay, один canonical user, две identities, отозванная сессия и удалённый пустой bootstrap-контур.

## Migration chain

```text
0022
→ 0023 account_link_intents + verified-email lookup
→ 0024 narrow intent creation function
→ 0025 purpose-specific link_email tokens + completion
→ 0026 Google link preparation + completion
→ 0027 decline + explicit separate-account + audit helpers
→ 0028 result-returning completion + replay + settings flows
→ 0029 step-up identity removal
→ 0030 conservative duplicate assessment
→ 0031 duplicate resolution intents + absorption
→ 0032 preserve intent when initiator is absorbed
→ 0033 restore protected initiator context during absorption
→ 0034 portable duplicate candidate lookup
```

Миграции не применялись в production. Feature flag по умолчанию выключен.

## Не завершено

- фактический запуск Ruff и pytest;
- фактический запуск frontend Vitest, lint и production build;
- фактический Alembic `upgrade → downgrade → upgrade` cycle на отдельной PostgreSQL БД;
- runtime integration tests step-up removal;
- исправление найденных тестами дефектов;
- CI и manual security review;
- merge и deployment.

## Следующий блок

1. запустить полный quality gate;
2. исправить все ошибки;
3. выполнить Alembic cycle и PostgreSQL integration/concurrency suite;
4. провести security review;
5. только после успешного gate подготовить PR к merge.
