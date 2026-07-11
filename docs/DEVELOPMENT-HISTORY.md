# Health Compass — история разработки

> Формат истории: каждый этап фиксируется точной датой `YYYY-MM-DD`. Если подтверждено время rollout или backup, оно указывается в UTC отдельной строкой. Заголовки только с месяцем больше не используются.

## 2026-07-06 — отказ от Authentik

Первоначальная архитектура использовала Authentik/OIDC. После ревью принято решение полностью отказаться от Authentik для MVP.

Новая модель:

- direct Google OAuth 2.0 / OIDC;
- Email Magic Links;
- локальные users/identities/sessions;
- собственные workspaces, profiles и permissions;
- PostgreSQL RLS.

Архивная ветка `feat/identity-and-profile-access` сохранена и не должна удаляться.

## 2026-07-07 — Google OIDC

Реализованы:

- discovery;
- PKCE S256;
- state и nonce;
- проверка issuer, audience, azp, expiry и email_verified;
- локальный logout;
- `prompt=select_account` для явного выбора Google-аккаунта.

Production-вход подтверждён двумя пользователями.

## 2026-07-07 — Email Magic Links

Реализованы:

- request/consume flow;
- одноразовый hash token;
- локальная session после consume;
- Brevo SMTP relay;
- подтверждённый sender `health@funti.cc`.

Ручная SMTP-ссылка с `token=test456` была отклонена валидатором как слишком короткая. Это подтвердило, что тестовое SMTP-письмо не заменяет production magic-link flow. Полный flow через `/auth/email/request` впоследствии проверен успешно.

## 2026-07-07 — RLS incident SQLSTATE 54001

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

## 2026-07-08 — перенос на поддомен

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

## 2026-07-08 — Auth MVP завершён

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

## 2026-07-08 — решение о Progressive Health Intake

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

## 2026-07-09 — Slice 1 Basic Health Profile

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
- backup `/opt/health-compass/backups/health_compass_20260709T122531Z.sql.gz` (`2026-07-09 12:25:31 UTC`);
- frontend release `/opt/health-compass/releases/main-20260709T122807Z` (`2026-07-09 12:28:07 UTC`);
- `/api/health`, `/`, `/app/profile` → 200;
- Google auth start → 307 на `accounts.google.com`;
- логи без ERROR, CRITICAL и Traceback.

Ручная проверка выявила UX-недочёт: timezone был показан как обязательное текстовое поле, что провоцировало ввод `+3`, хотя backend ожидает IANA timezone.

## 2026-07-09 — timezone UX и favicon

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

## 2026-07-09 — Slice 2 Clinical Context начат

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

## 2026-07-08 — Fable Stage 3 и 3.5

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

## 2026-07-09 — обнаружен дефект разных профилей при Google и Magic Link

Ручная проверка показала, что один человек при входе через Google и Email Magic Link может получить разные `user_id`, workspace и health profile, даже когда verified email совпадает.

Причина: identities ищутся по `(provider, subject)`, а совпадение email намеренно не используется для автоматического объединения. Это сохраняет security-инвариант, но без отдельного linking-flow приводит к молчаливому созданию дубля.

Принято решение вставить блокирующую PHASE-02.6 перед продолжением Slice 2:

- HC-025 — link-on-login и UI «Способы входа»;
- HC-026 — контролируемый разбор уже существующих дублей;
- HC-027 — запрет молчаливого создания новых дублей во всех bootstrap-путях;
- HC-028 — добровольная TOTP 2FA, не блокирующая возврат к Slice 2.

Slice 2 заморожен до завершения HC-025 и HC-026.

## 2026-07-09 — зафиксирован симметричный link-on-login

Каноническая спецификация:

```text
docs/ACCOUNT-LINKING-MVP.md
```

Приняты два симметричных сценария:

1. Google-first → Email-second: Magic Link подтверждает email, затем пользователь подтверждает существующий Google-аккаунт через Google OAuth. Новый user/workspace/profile до завершения linking не создаётся.
2. Email-first → Google-second: Google OAuth подтверждает Google identity, затем пользователь подтверждает существующий email-аккаунт специальной ссылкой с purpose `link_email`. Повторное подтверждение через Google не требуется.

Итог обоих сценариев:

```text
one user_id
├── google identity
└── email identity
```

Совпадение verified email только запускает предложение связать входы. Без подтверждения второго способа ничего не объединяется. Отказ от linking может привести к отдельному аккаунту только после явного подтверждения последствий.

Создана рабочая ветка:

```text
feat/account-linking-mvp
```

Следующий шаг: аудит фактических Google callback, Magic Link consume и bootstrap, затем реализация HC-025 по реальному коду.

## 2026-07-10 — HC-025 / HC-026 / HC-027 завершены в production

Подтверждено:

- Google и Email Magic Link открывают один аккаунт и один health profile;
- старый пустой дубль корректно поглощён;
- step-up removal не позволяет удалить последнюю identity;
- Alembic head `0036`;
- account linking включён в production;
- отсутствующий `dashboard_snapshot` отображается как onboarding-state, а не ошибка 404;
- меню показывает `health_profile.display_name`;
- карточка профиля полностью реагирует на hover и focus;
- CI и PostgreSQL concurrency tests зелёные.

Итоговый статус:

```text
HC-025 completed
HC-026 completed
HC-027 completed
production verified
```

## 2026-07-10 — Clinical Context и contextual intake развёрнуты

После account-linking remediation реализованы и развёрнуты следующие части PHASE-02.5:

- Clinical Context conditions, allergies, medications и supplements;
- explicit review states;
- typeahead и global/personal dictionary suggestions;
- optional clarifying questions;
- contextual intake decisions;
- profile questionnaire navigation;
- dashboard context coverage;
- mobile readability improvements;
- provenance, consent, append-only audit и void history;
- optimistic concurrency для update/review paths;
- FORCE RLS и owner/edit/view/analyze/outsider matrix.

Production Alembic достиг `0045 (head)`.

## 2026-07-10 — HC-014 Clinical Dictionaries v2

Развёрнут Russian-first dictionary foundation и исправлен importer, который первоначально конфликтовал с pre-existing concept UUID при совпадающем business key.

Принятый business key:

```text
(domain, normalized_text)
```

Исправленный importer:

- сохраняет существующий concept UUID;
- использует `RETURNING id`;
- привязывает aliases к фактическому database concept;
- остаётся идемпотентным.

Перед повторным apply создан backup:

```text
/opt/health-compass/backups/clinical_dictionary_before_seed_retry_20260710T224649Z.sql.gz
```

Финальное production state:

- 69 concepts;
- 107 aliases;
- 0 duplicate concept business keys;
- 0 duplicate aliases;
- 0 orphan aliases;
- все 66 reviewed business keys представлены;
- Alembic остался `0045`;
- backend остался healthy.

Production code после фикса и документации: `f3d7e8fedcdad5448abce5c74c1bdb698e5e82e6`.

## 2026-07-11 — два независимых code review

Актуальный repository HEAD `1a61f0307130e19fedeabd95218293d9a5075fe1` независимо проверен ChatGPT и Fable 5.

Оба review подтвердили сильную RLS/tenant-isolation foundation и не обнаружили подтверждённого Critical finding, cross-user leak или self-escalation.

Одновременно приняты блокирующие findings:

- overlapping Clinical Context summary/review routes;
- schema drift duplicate assessment/absorption относительно `profile_clinical_reviews` и `profile_intake_decisions`;
- scanner-unsafe Magic Link consume через GET;
- wrong-domain и stale `canonical_concept_id`;
- неполный frontend lint/typecheck gate;
- дополнительные concurrency, logging, migration и API-contract defects.

Итоговый engineering verdict:

```text
FIX BEFORE ROLLOUT
```

Создана блокирующая задача:

```text
HC-015 — Code Review Remediation
```

Канонические документы:

- `docs/reviews/CODE-REVIEW-CONSOLIDATED-2026-07-11.md`;
- `docs/reviews/FABLE-5-INDEPENDENT-CODE-REVIEW-2026-07-11.md`;
- `docs/implementation/HC-015-CODE-REVIEW-REMEDIATION.md`.

До завершения HC-015 новые product features и production code rollout остановлены. Следующий разрешённый шаг — реализация remediation в отдельной branch с полным CI, independent diff review и controlled backup-first rollout.

## 2026-07-11 — HC-015 implementation (branch, not merged)

После merge PR #38 (review evidence и HC-015 specification) все slices A–F
реализованы в implementation branch `claude/hc-015-code-review-remediation-noaeve`
от `main` `265eb0ef80ebd4af2073bd2168bf17be90562fe4`.

Ключевые изменения:

- один канонический владелец Clinical Context summary/review routes
  (`clinical_review`); legacy summary/review service и дублирующие create
  routes удалены; route-table uniqueness закреплён тестом;
- migration `0046`: `app_duplicate_user_activity` учитывает
  `profile_clinical_reviews` и `profile_intake_decisions`; absorption получил
  FK safety net (controlled `blocked` вместо необработанного FK violation);
- scanner-safe Email Magic Link: GET показывает нейтральную interstitial
  страницу, consume выполняется только явным POST; logout только POST с
  Origin-проверкой; production требует `ACCOUNT_LINKING_ENABLED=true`;
  логи переведены на настоящий JSON с request_id и redaction query strings;
- migration `0047`: domain-валидирующий словарный trigger (SQLSTATE
  HC422/HC404/HC409), атомарная очистка stale canonical mapping, безопасный
  repair существующих строк, отзыв прямого UPDATE на `canonical_concept_id`;
  alias seed upsert переведён на реальный business key;
- migration `0048`: узкий column-level UPDATE grant на `users`
  (только `display_name`, `updated_at`);
- CI: full-source `npm run lint`, новый `npm run typecheck`, изолированный
  migration-cycle test `upgrade head → downgrade base → upgrade head`
  с проверкой owners/grants/RLS/PUBLIC EXECUTE; исправлен сломанный
  downgrade `0006`;
- concurrency: `expected_updated_at` для void (409 на stale) и advisory-lock
  атомарность `confirmed_none` против конкурентного создания записи;
- frontend: единый разбор обоих документированных error envelopes с
  сохранением `request_id`, очистка dose, date-only без UTC-сдвига, ошибки
  complete-course в нужной карточке, сброс editor state, debounce и
  cancellation в typeahead.

Локальные результаты в CI-эквивалентном окружении: backend unit
106 passed; PostgreSQL integration/RLS 73 passed; migration cycle passed;
frontend lint 0 errors, typecheck clean, 43 tests passed, build успешен.

Alembic head branch: `0048` (линейный). Production не изменялся:
`f3d7e8fedcdad5448abce5c74c1bdb698e5e82e6`, Alembic `0045`.
Deployment status: `NOT DEPLOYED`. Далее — independent diff review,
merge с зелёным CI на exact PR SHA и controlled backup-first rollout.
