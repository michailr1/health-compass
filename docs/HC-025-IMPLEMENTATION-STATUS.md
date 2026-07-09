# HC-025 / HC-026 / HC-027 — статус реализации

Дата: 2026-07-09  
Ветка: `feat/account-linking-mvp`  
PR: `#7`  
Статус: `READY FOR REVIEW / NOT DEPLOYED`

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
- runtime PostgreSQL concurrency test удаления identity: один DELETE, один replay, последняя identity сохраняется.

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
- candidate lookup использует portable `array_agg(uuid)` и не создаёт temp tables;
- PostgreSQL concurrency test подтверждает один completion, один replay, один canonical user, две identities, отозванную сессию и удалённый пустой bootstrap-контур.

## HC-027 реализовано

- Google callback и Email Magic Link consume проверяют verified email до bootstrap;
- один существующий candidate запускает HC-025;
- несколько существующих users направляют в HC-026 вместо молчаливого создания третьего user;
- отказ от linking не создаёт отдельный аккаунт без второго явного подтверждения;
- обычный вход по уже известной `(provider, subject)` identity остаётся прямым и идемпотентным.

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
→ 0035 qualified identity-removal columns
```

Миграции не применялись в production. Feature flag по умолчанию выключен.

## Quality gate — пройден

- Python compile: success;
- Ruff: success;
- backend unit/static tests: success;
- frontend ESLint: success;
- frontend Vitest: success;
- frontend production build: success;
- исторический Alembic `0021 ↔ 0022` cycle: success;
- current-head `upgrade → downgrade -1 → upgrade`: success;
- FORCE RLS и app-role direct-access checks: success;
- account-link concurrency: success;
- identity-removal concurrency: success;
- empty-duplicate absorption concurrency: success;
- manual security review: blocker findings не обнаружены после исправления `0035`.

## До production

1. review и merge PR #7;
2. backup production БД;
3. проверить роль `health_compass_rls_definer` и migration preconditions;
4. применить миграции backend-first;
5. задеплоить backend с feature flag выключенным;
6. задеплоить frontend;
7. smoke-test обычного Google и Email входа;
8. включить feature flag;
9. выполнить e2e link-on-login, settings linking, removal и HC-026 на контролируемых тестовых аккаунтах;
10. при любом отклонении выключить feature flag и остановить rollout.
