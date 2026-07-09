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

Результат: production Google и email login работают, cross-user проверки пройдены.

## 2026-07 — перенос на поддомен

Портал перенесён с:

```text
https://funti.cc/health
```

на:

```text
https://health.funti.cc
```

Подтверждено:

- DNS `health.funti.cc → 172.245.108.154`;
- отдельный Let's Encrypt certificate;
- Apache VirtualHost и SPA fallback;
- backend и frontend используют пути от корня поддомена;
- старый `/health` отдаёт 301 на production-поддомен;
- Google callback: `https://health.funti.cc/api/auth/callback`.

## 2026-07 — Auth MVP завершён

Auth MVP объединён в `main` и выпущен как:

```text
v0.1.0-auth-mvp
```

Подтверждены:

- Google login;
- Email Magic Link;
- logout;
- повторный вход;
- повторное использование Magic Link;
- friendly invalid-link page;
- tenant isolation;
- cross-user API responses `404`;
- FORCE RLS;
- чистые production smoke tests и логи.

Архивная ветка `feat/identity-and-profile-access` и бывшая auth-ветка `feat/direct-google-and-email-auth` сохранены.

## 2026-07 — решение о Progressive Health Intake

Отказались от большой блокирующей анкеты до первого анализа.

Принятый путь:

```text
Login
→ минимальный onboarding
→ Empty Dashboard / первое полезное действие
→ добровольное заполнение Health Profile
→ контекстные вопросы при необходимости
→ подтверждённый импорт фактов из документов
```

Зафиксированы инварианты:

- медицинская анкета не блокирует активацию;
- большинство полей опциональны;
- каждое поле объясняет назначение;
- OCR и AI не меняют профиль без подтверждения;
- intake не является самодиагностикой;
- временные совпадения не объявляются причинностью.

PHASE-02.5 поставлена перед PHASE-03 и поглощает прежнюю задачу HC-012.

## 2026-07 — Slice 1 Basic Health Profile

Подготовлена спецификация:

```text
docs/BASIC-HEALTH-PROFILE-SLICE-1.md
```

Фактический аудит кода показал, что таблица `health_compass.health_profiles` уже существует. Поэтому Slice 1 расширил её, а не создавал второй профиль поверх существующего.

Реализовано:

- миграция `0022`;
- `height_cm`, `timezone`, `updated_at` в существующем профиле;
- история веса в `body_measurements`;
- минимальная consent-модель;
- append-only audit;
- `app_can_edit_profile(uuid)`;
- owner/edit write access, view/analyze read-only;
- FORCE RLS и column-level privileges;
- profile PATCH API;
- endpoints истории веса и void;
- экран `/app/profile`;
- autosave основных полей;
- contextual readiness без health score;
- soft validation;
- cross-user matrix и регресс `54001`.

PR #5 прошёл полный CI и был слит squash-merge в `main`.

Production deployment Slice 1:

- commit `bea8bd448ad6f6ada60c1a7f8b7aca5eebd12af7`;
- Alembic `0022 (head)`;
- backup `/opt/health-compass/backups/health_compass_20260709T122531Z.sql.gz`;
- frontend release `/opt/health-compass/releases/main-20260709T122807Z`;
- `/api/health`, `/`, `/app/profile` → 200;
- Google auth start → 307 на `accounts.google.com`;
- логи без ERROR, CRITICAL и Traceback.

Ручная проверка выявила UX-недочёт: timezone был показан как обязательное текстовое поле, что провоцировало ввод `+3`, хотя backend ожидает IANA timezone.

## 2026-07 — timezone UX и favicon

В PR #6 исправлено:

- timezone автоматически определяется браузером;
- сохраняется IANA-значение, например `Europe/Moscow`;
- сохранённое значение не перезаписывается при каждом открытии;
- есть ручная корректировка через отдельную ненавязчивую настройку;
- поле timezone удалено из основной формы;
- Lovable favicon заменён на иконку Health Compass;
- title и метаданные очищены от старых `HealthMonitor`/demo-формулировок.

PR #6 слит в `main`, production deployment принят владельцем.

Развёрнутый commit после UX-fix:

```text
77453af7c5cb6aae77ff4164069131737981f208
```

## 2026-07 — Slice 2 Clinical Context начат

Создана ветка:

```text
feat/clinical-context-slice-2
```

Добавлена спецификация:

```text
docs/CLINICAL-CONTEXT-SLICE-2.md
```

Планируется:

- хронические состояния;
- аллергии и непереносимости;
- лекарства;
- витамины, минералы и БАДы;
- active/inactive;
- дозировки, единицы, частота и даты;
- confirmation и provenance;
- audit;
- FORCE RLS;
- миграция `0023`;
- API, UI и cross-user tests.

На момент этой записи Slice 2 ещё не реализован и не развёрнут.

## 2026-07 — Fable Stage 3 и 3.5

Получены и приняты как target baseline материалы по продукту, UX, AI safety и детальной карте интерфейса.

Зафиксировано:

- Human-first MVP vertical slice: login → onboarding → upload → OCR review → lab results → metric dynamics → AI evidence → doctor report;
- отдельный future-ready Pet Health contour;
- Human/Pet visual and AI separation;
- desktop и mobile navigation;
- экранные состояния, action registry и component map;
- high-fidelity mockups как reference design;
- AI evidence, consent, prompt-injection и red-flag invariants;
- дополнительные функции: Attention Inbox, global search, bulk upload, OCR autosave, data freshness, session management, notifications и Offline Emergency Card.

Решения перенесены в:

- `docs/PRODUCT-UX-BASELINE.md`;
- `docs/AI-PRODUCT-SAFETY.md`;
- `docs/PROJECT-PLAN.md`;
- `docs/reviews/FABLE-RECOMMENDATIONS.md`;
- `docs/source-index/SOURCE-REGISTER.md`.

Эти материалы не считаются реализованным функционалом без кода, API, миграций и тестов.
