# HC-025 / HC-026 / HC-027 — итоговый статус

Дата завершения: 2026-07-09  
Production branch: `main`  
Production commit: `1f80932e74c4ddb03b8d4cd93bbcf70bb8cc0d20`  
Alembic head: `0036`  
Статус: `COMPLETED / DEPLOYED / VERIFIED`

## HC-025 — account linking

Реализовано и проверено в production:

- symmetric link-on-login для Google и Email Magic Link;
- pre-bootstrap interception без создания второго user/workspace/profile;
- `account_link_intents` и purpose-specific `link_email` tokens с ENABLE/FORCE RLS;
- browser binding, hash-only storage, TTL, rate limit, state/nonce/PKCE;
- transactional identity attachment в обоих направлениях;
- idempotent callback/consume с реальными `intent_id`, `user_id`, `replayed`;
- explicit decline без автоматического создания отдельного аккаунта;
- отдельный аккаунт только после второго явного подтверждения;
- audit и security notifications на verified addresses;
- authenticated API и UI «Способы входа»;
- settings flows `settings_add_google` и `settings_add_email`;
- запрет скрытой перезаписи `users.email`;
- step-up отключение identity через другой подключённый способ;
- hard guard последней identity;
- replay-safe removal intent;
- runtime PostgreSQL concurrency tests для linking и removal.

## HC-026 — устранение старых дублей

Реализовано и вручную проверено в production:

- консервативная оценка пары дублей;
- assessment доступен только для пары, содержащей текущий `app.current_user_id`;
- внутренний activity helper недоступен app-role;
- автоматическое поглощение допускается только для пустого bootstrap-user;
- значимые profile settings, dashboard snapshots, body measurements, audit events, consents и shared access блокируют автоматический merge;
- если оба аккаунта пусты, каноническим становится более старый;
- отдельные RLS-таблицы `duplicate_resolution_intents` и `duplicate_resolution_email_tokens`;
- отдельные purpose `resolve_duplicate_email` и `duplicate_resolution`;
- обязательное доказательство второй identity;
- повторный assessment непосредственно перед absorption;
- identities переносятся на canonical user;
- сессии absorbed user отзываются;
- удаляются только пустые workspace/profile absorbed user;
- медицинские данные не переносятся;
- completion идемпотентен;
- production-проверка подтвердила, что Google и Email Magic Link открывают один и тот же профиль.

## HC-027 — bootstrap integration

- Google callback и Email Magic Link consume проверяют verified email до bootstrap;
- один существующий candidate запускает HC-025;
- несколько существующих users направляются в HC-026;
- silent third account не создаётся;
- обычный вход по известной `(provider, subject)` identity остаётся прямым и идемпотентным;
- новый профиль создаётся пустым, без синтетических медицинских данных.

## Исправления после production rollout

- `0036`: исправлен переход `declined → cancelled` — `declined_at` очищается атомарно;
- отсутствующий `dashboard_snapshot` теперь отображается как нормальное onboarding-состояние, а не ошибка 404;
- карточка «Профиль здоровья» стала полностью кликабельной и визуально реагирует на hover/focus;
- меню показывает `health_profile.display_name`, а не техническое имя Email-аккаунта;
- мобильный header использует то же имя профиля.

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
→ 0036 clear declined_at during separate-account claim
```

## Quality gate

Пройдено:

- Python compile;
- Ruff;
- backend unit/static tests;
- frontend ESLint;
- frontend Vitest;
- frontend production build;
- исторический Alembic `0021 ↔ 0022` cycle;
- current-head `upgrade → downgrade -1 → upgrade` cycle;
- FORCE RLS и app-role direct-access checks;
- account-link concurrency;
- identity-removal concurrency;
- empty-duplicate absorption concurrency;
- regression tests для `0036`, пустого dashboard и имени профиля в меню;
- ручная production-проверка Google + Email Magic Link + HC-026.

## Production result

- direct Google OIDC работает;
- Email Magic Link работает;
- оба способа входа открывают один аккаунт и один профиль;
- старый пустой дубль корректно поглощён;
- новый пустой профиль отображается без dashboard error;
- интерфейс профиля исправлен;
- account-linking feature включён и работает штатно;
- блок HC-025 / HC-026 / HC-027 закрыт.

## Следующий этап

Вернуться к roadmap после identity foundation. Ближайший функциональный блок — Clinical Context / HC-012b и дальнейшее развитие медицинского профиля, затем источники данных и пользовательские wow-сценарии, включая питание по фотографии.
