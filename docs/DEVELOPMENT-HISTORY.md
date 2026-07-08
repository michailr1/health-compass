# Health Compass — история разработки

## 2026-07 — отказ от Authentik

Первоначальная архитектура использовала Authentik/OIDC. После ревью принято решение полностью отказаться от Authentik для MVP.

Новая модель:

- direct Google OAuth 2.0 / OIDC;
- Email Magic Links;
- локальные users/identities/sessions;
- собственные workspaces, profiles и permissions;
- PostgreSQL RLS.

Архивная ветка `feat/identity-and-profile-access` сохранена и не должна удаляться.

## 2026-07 — Google OIDC

Реализованы:

- discovery;
- PKCE S256;
- state и nonce;
- проверка issuer, audience, azp, expiry и email_verified;
- локальный logout;
- `prompt=select_account` для явного выбора Google-аккаунта.

Production-вход подтверждён двумя пользователями.

## 2026-07 — Email Magic Links

Реализованы:

- request/consume flow;
- одноразовый hash token;
- локальная session после consume;
- Brevo SMTP relay;
- подтверждённый sender `health@funti.cc`.

Ручная SMTP-ссылка с `token=test456` была отклонена валидатором как слишком короткая. Это подтвердило, что тестовое SMTP-письмо не заменяет production magic-link flow. Полный flow через `/auth/email/request` впоследствии проверен успешно.

## 2026-07 — RLS incident SQLSTATE 54001

Симптом:

- первый Google callback завершался `500`;
- PostgreSQL: `StatementTooComplex`, SQLSTATE `54001`, stack depth exceeded;
- ошибка проявлялась на `INSERT profile_permissions ... RETURNING`.

Root cause:

- helper-функции `SECURITY DEFINER` принадлежали migrator;
- после `FORCE ROW LEVEL SECURITY` владелец таблиц больше не обходил RLS;
- функции попадали под политики, которые сами их вызывали;
- возникали бесконечные циклы profile/workspace access.

Дополнительно Fable обнаружил:

- self-grant owner на чужой profile;
- self-add в чужой workspace;
- риск дубликатов identity user;
- отсутствие users UPDATE policy;
- необходимость session hash context для `AuthSession INSERT ... RETURNING`.

Исправления:

- `0020_break_rls_recursion_and_close_escalations.py`;
- `0021_fix_rls_context_function_ownership.py`;
- роль `health_compass_rls_definer NOLOGIN BYPASSRLS`;
- фиксированные function settings;
- revoke PUBLIC;
- negative policies/tests;
- session context перед AuthSession insert.

Результат: `22 PASS, 0 FAIL`; production Google и email login работают, cross-user проверки пройдены.

## 2026-07 — демонстрационные данные

Каждый новый пользователь получает отдельные workspace/profile/dashboard records, но стартовые показатели пока одинаковые. Решение: временно оставить демоданные до появления реального импорта, обязательно маркируя их как демонстрационные.

## 2026-07 — перенос на поддомен

Принято решение перенести портал с:

`https://funti.cc/health`

на:

`https://health.funti.cc`

DNS и новый Google redirect URI добавлены. Код и production deployment ещё должны быть переведены на root-path поддомена. Старый URL сохраняется до успешной проверки и затем переводится на redirect.
