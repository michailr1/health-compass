# HC-025 — техническая спецификация link-on-login

Дата: 2026-07-09  
Статус: `CODE AUDITED / IMPLEMENTATION IN PROGRESS`  
Ветка: `feat/account-linking-mvp`

## 1. Фактическое состояние кода

Аудит выполнен по текущим файлам:

- `backend/app/api/routes/auth.py`;
- `backend/app/api/routes/email_auth.py`;
- `backend/app/services/bootstrap.py`;
- `backend/app/models/user.py`;
- `backend/alembic/versions/0019_email_magic_links.py`;
- `backend/alembic/versions/0022_add_basic_health_profile_and_measurements.py`.

### Google callback

Текущий алгоритм:

1. валидирует state, nonce, PKCE и Google ID token;
2. ищет identity только по `(provider='google', subject=sub)`;
3. если identity отсутствует, немедленно создаёт новый `User` и `UserIdentity`;
4. вызывает `ensure_personal_workspace`;
5. создаёт session.

Следствие: существующий Email Magic Link user с тем же verified email не находится и получает второй user/workspace/profile.

Также повторный Google-вход сейчас безусловно присваивает `user.email = Google email`. Это должно быть прекращено: обычный вход не меняет канонический email пользователя.

### Email Magic Link consume

Текущий алгоритм:

1. consume одноразового login-token возвращает email;
2. ищет identity только по `(provider='email', subject=normalized_email)`;
3. если identity отсутствует, немедленно создаёт новый `User` и `UserIdentity`;
4. вызывает `ensure_personal_workspace`;
5. создаёт session.

Следствие: существующий Google user с тем же verified email не находится и получает второй user/workspace/profile.

Также повторный email-вход сейчас безусловно присваивает `user.email = email`. Это должно быть прекращено.

### Bootstrap

`ensure_personal_workspace` создаёт workspace и health profile, если у user нет membership. Поэтому link-on-login обязан остановить новый-user branch до создания user и до вызова bootstrap.

Во время аудита обнаружена отдельная регрессия: bootstrap всё ещё содержал синтетические медицинские данные и Factor V Leiden. Она устранена отдельным коммитом в этой ветке. Новый профиль теперь создаётся пустым.

## 2. Архитектурное решение

HC-025 вводит двухшаговую pre-bootstrap state machine.

Ни совпадение email, ни первый успешно пройденный provider не создают новый user, если обнаружен кандидат другого provider.

Состояния intent:

```text
pending_confirmation
→ completed
→ declined
→ expired
→ cancelled
```

Типы flow:

```text
google_first_email_existing
email_first_google_existing
settings_add_google
settings_add_email
```

## 3. Модель данных

Новая таблица `health_compass.account_link_intents`:

- `id uuid`;
- `flow_type varchar(64)`;
- `status varchar(32)`;
- `normalized_email varchar(320)`;
- `candidate_user_id uuid`;
- `initiating_provider varchar(64)`;
- `initiating_subject varchar(255)`;
- `required_provider varchar(64)`;
- `required_subject varchar(255) null`;
- `initiating_claims jsonb null`;
- `browser_binding_hash varchar(128)`;
- `state_hash varchar(128) null`;
- `nonce_hash varchar(128) null`;
- `pkce_verifier_hash varchar(128) null`;
- `created_at`, `expires_at`, `completed_at`, `declined_at`;
- `created_ip`, `user_agent`;
- `failure_count`;
- `version integer` для optimistic concurrency.

Секреты и raw-токены в БД не сохраняются. Cookies содержат случайные значения; в БД сохраняются только hashes.

Таблица получает `ENABLE ROW LEVEL SECURITY` и `FORCE ROW LEVEL SECURITY` в той же миграции. Прямых DML-grants приложению на таблицу нет. Pre-auth операции выполняются через узкие SECURITY DEFINER functions с владельцем `health_compass_rls_definer`, фиксированным `search_path`, `row_security=off`, revoked PUBLIC и EXECUTE только для `health_compass_app`.

## 4. Lookup кандидата по verified email

Нужны скалярные helpers:

- `app_count_verified_email_users(normalized_email text) returns integer`;
- `app_lookup_single_verified_email_user(normalized_email text) returns uuid`.

Функции считают только active users, у которых есть подтверждённая identity:

- Email provider: `subject = normalized_email` и claims `email_verified=true`;
- Google provider: normalized claims email совпадает и `email_verified=true`.

Логика:

- count = 0 → обычный bootstrap нового user;
- count = 1 → HC-025 link-on-login;
- count > 1 → HC-026 existing-duplicates flow;
- уже существующая `(provider, subject)` identity → обычный login без linking.

Helpers не возвращают email, profile или другие пользовательские данные.

## 5. Google-first → Email-second

После consume обычного Email Magic Link:

1. email identity отсутствует;
2. verified-email lookup находит ровно одного Google user;
3. создаётся intent `email_first_google_existing` в смысле текущего инициатора email и required provider Google;
4. user/workspace/profile не создаются;
5. frontend получает redirect `/auth/link-account?intent=...`;
6. пользователь нажимает «Подтвердить через Google»;
7. отдельный Google authorization start создаёт state/nonce/PKCE для purpose `account_link`;
8. callback проверяет browser binding, intent status/expiry, state/nonce/PKCE, Google `sub`, verified email и candidate user;
9. транзакционно создаётся email identity у candidate user;
10. intent становится completed;
11. создаётся session candidate user;
12. отправляется security notification.

## 6. Email-first → Google-second

После Google callback:

1. Google identity отсутствует;
2. verified-email lookup находит ровно одного Email user;
3. создаётся intent `google_first_email_existing` в смысле текущего инициатора Google и required provider Email;
4. user/workspace/profile не создаются;
5. отправляется специальная ссылка purpose `link_email`;
6. frontend показывает экран ожидания подтверждения;
7. consume `link_email` проверяет hash, purpose, expiry, browser binding и intent;
8. транзакционно создаётся Google identity у candidate user;
9. intent становится completed;
10. создаётся session candidate user;
11. отправляется security notification.

Обычный login-token нельзя использовать вместо `link_email`, а `link_email` нельзя использовать для обычного входа.

## 7. Endpoint contract

Планируемые endpoints:

- `GET /api/auth/provider/google` — обычный Google login;
- `GET /api/auth/link/google/start?intent_id=...` — Google confirmation для linking;
- `GET /api/auth/callback` — различает login/link purpose через подписанный cookie + intent;
- `POST /api/auth/email/request` — обычный login link;
- `POST /api/auth/link/email/request` — link_email request;
- `GET /api/auth/email/consume` — текущий login consume, позже scanner-safe POST;
- `GET /api/auth/link/email/consume` — отдельный link_email consume;
- `GET /api/auth/link/intents/{id}` — безопасный статус для текущего browser binding;
- `POST /api/auth/link/intents/{id}/decline`;
- `POST /api/auth/link/intents/{id}/create-separate-account` — только после decline и повторного явного подтверждения;
- `GET /api/auth/identities` — список способов входа текущего user;
- `DELETE /api/auth/identities/{identity_id}` — позже, с запретом удаления последней identity и step-up.

Названия могут быть скорректированы при реализации, но purpose separation и state machine обязательны.

## 8. Canonical email

Обычные callback/consume больше не выполняют:

```python
user.email = provider_email
```

Правило MVP:

- `users.email` сохраняется как канонический контактный адрес;
- provider emails хранятся в identity claims/subject;
- смена канонического email — отдельная подтверждаемая операция;
- linking не перезаписывает канонический email автоматически.

## 9. Concurrency и идемпотентность

- unique `(provider, subject)` остаётся главным барьером перехвата identity;
- completion блокирует intent row `FOR UPDATE`;
- повторный callback/consume после completed возвращает существующий результат без второй identity/session mutation;
- конкурентная попытка link чужой identity завершается conflict и audit failure;
- intent version или status condition предотвращает lost update;
- session создаётся только после успешного linking или осознанного separate-account path.

## 10. Audit и notifications

События:

- `identity.link_started`;
- `identity.link_completed`;
- `identity.link_declined`;
- `identity.link_failed`;
- `identity.separate_account_confirmed`;
- позже HC-026: `identity.transferred`, `user.absorbed`.

Audit не содержит raw token, authorization code, PKCE verifier, cookie value или полный claims payload.

После успешного linking отправляются уведомления на доступные подтверждённые адреса.

## 11. Feature flag и rollback

Настройка:

```text
ACCOUNT_LINKING_ENABLED=false|true
```

Rollback приложения выключает новый flow, но не разрывает уже созданные identities. Миграция может оставаться применённой. Downgrade допустим только до появления production intents/links либо после явной проверки данных.

При выключенном flag до полного релиза нельзя возвращаться к молчаливому созданию дублей: безопасный fallback — остановить вход с объяснимой ошибкой, если найден verified-email candidate другого provider.

## 12. Обязательные тесты

### Unit

- normalize email одинаков для обоих потоков;
- purpose separation;
- hash verification;
- state machine transitions;
- expiry;
- canonical email не перезаписывается.

### Integration PostgreSQL

- таблица имеет ENABLE + FORCE RLS;
- PUBLIC не имеет EXECUTE на helpers;
- app role не читает intent table напрямую;
- scalar lookup count 0/1/2+;
- unique provider/subject;
- concurrent completion создаёт одну identity;
- отсутствие RLS context fail-closed;
- regression `54001`.

### API/E2E

- Google-first → Email-second → Google confirmation → один user/workspace/profile;
- Email-first → Google-second → link_email confirmation → один user/workspace/profile;
- до confirmation отсутствуют новые user/workspace/profile;
- wrong Google sub rejected;
- unverified Google email rejected;
- login token used as link token rejected;
- link token used as login token rejected;
- state/nonce/PKCE/browser-binding mismatch rejected;
- expired/replayed intent rejected or idempotently completed;
- decline does not create account;
- separate account requires additional explicit confirmation;
- existing duplicate routes to HC-026;
- ordinary repeat login remains unchanged;
- both identities subsequently resolve to the same user_id.

## 13. Implementation order

1. Remove synthetic bootstrap medical data — completed in feature branch.
2. Add migration `0023_account_linking_intents.py` and model.
3. Add scalar verified-email lookup helpers and tests.
4. Stop unconditional `user.email` overwrite.
5. Extract common session creation helper.
6. Implement intent service and purpose-specific token handling.
7. Integrate Google callback.
8. Integrate Email consume.
9. Add frontend confirmation screen.
10. Add settings «Способы входа».
11. Full CI and security review.
12. Merge only after green tests; deployment separately after explicit approval.
