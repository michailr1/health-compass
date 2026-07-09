# Health Compass — Account Linking MVP (PHASE-02.6)

Дата: 2026-07-09  
Статус: `SPECIFIED / IMPLEMENTATION PENDING`  
Рабочая ветка: `feat/account-linking-mvp`

## 1. Цель

Исключить молчаливое создание разных `user_id`, workspace и health profile, когда один человек использует Google OIDC и Email Magic Link с одним и тем же подтверждённым email.

Главный результат:

```text
one user_id
├── identity: google / provider subject
└── identity: email / normalized email
```

Совпадение verified email само по себе не объединяет аккаунты. Оно только запускает явный flow подтверждения владения вторым способом входа.

## 2. Основной принцип

Пользователь уже доказал владение способом, которым начал текущий вход. Для связывания он должен дополнительно доказать владение существующим аккаунтом вторым способом.

```text
текущий подтверждённый способ
+
подтверждение существующего второго способа
=
две identities у одного user_id
```

До завершения подтверждения:

- новый `user_id` не создаётся;
- новый workspace не создаётся;
- новый health profile не создаётся;
- существующий профиль не изменяется;
- создаётся только короткоживущее link-intent состояние.

## 3. Сценарий A — сначала Google, затем Magic Link

Исходное состояние:

```text
Google identity → user A → workspace A → profile A
```

Пользователь позже начинает вход по Email Magic Link с тем же verified email.

Порядок:

1. Magic Link подтверждает владение email.
2. Backend обнаруживает существующий Google-аккаунт с тем же verified email.
3. Bootstrap нового пользователя не запускается.
4. Показывается экран: «Найден существующий аккаунт. Подтвердите вход через Google, чтобы связать способы входа».
5. Пользователь проходит Google OAuth с `state`, `nonce` и PKCE, привязанными к link-intent.
6. Backend проверяет Google `sub`, issuer, audience, `email_verified` и совпадение ожидаемого аккаунта.
7. Email identity добавляется к `user A`.
8. Создаётся обычная сессия `user A`.
9. Открывается существующий `profile A`.

Итог:

```text
user A
├── google identity
└── email identity
```

## 4. Сценарий B — сначала Magic Link, затем Google

Исходное состояние:

```text
Email identity → user A → workspace A → profile A
```

Пользователь позже начинает вход через Google с тем же verified email.

Порядок:

1. Google OAuth подтверждает Google identity и verified email.
2. Backend обнаруживает существующий email-аккаунт.
3. Bootstrap нового пользователя не запускается.
4. Пользователю отправляется специальная ссылка с purpose `link_email`.
5. Показывается экран: «Подтвердите email, чтобы связать вход через Google с существующим аккаунтом».
6. Пользователь подтверждает ссылку `link_email`.
7. Backend проверяет, что токен относится к ожидаемому link-intent и не является обычным login-token.
8. Google identity добавляется к `user A`.
9. Создаётся обычная сессия `user A`.
10. Открывается существующий `profile A`.

Итог:

```text
user A
├── email identity
└── google identity
```

Дополнительное повторное подтверждение через Google не требуется: Google уже подтверждён текущим OAuth-входом. Подтверждается существующий email-аккаунт.

## 5. Сценарий из настроек «Способы входа»

Тот же механизм используется из уже авторизованной сессии:

- пользователь вошёл через Google → подключает Email Magic Link → подтверждает `link_email`;
- пользователь вошёл через Email Magic Link → подключает Google → проходит Google OAuth;
- свежая активная сессия доказывает владение текущим аккаунтом;
- подключаемый способ доказывается отдельно.

Нельзя отвязать последнюю identity.

## 6. Отказ от связывания

Пользователь может отказаться от link-flow.

Тогда система должна явно объяснить последствия и только после отдельного подтверждения позволить создать отдельный аккаунт.

Запрещено создавать отдельный аккаунт молча.

## 7. Существующие дубли — HC-026

Если обе identities уже принадлежат разным `user_id`:

- обычный HC-025 flow не переносит identity автоматически;
- пользователь должен подтвердить владение обоими способами;
- запускается HC-026;
- перенос разрешён только если поглощаемый user не содержит значимых данных;
- если данные есть в обоих профилях, автоматический merge запрещён.

## 8. Security requirements

Обязательно:

- отдельный purpose `link_email`; login-token не может использоваться для linking и наоборот;
- одноразовые короткоживущие link-intents;
- токены хранятся только в hash-виде;
- Google link-flow использует `state` + `nonce` + PKCE;
- link-intent привязан к ожидаемым provider, subject, email и инициирующей сессии/браузеру;
- защита от replay и session fixation;
- rate limiting по IP, email, user и intent;
- audit событий link.started, link.completed, link.declined, link.failed;
- уведомления на связанные адреса после успешного linking;
- обычный вход не перезаписывает канонический `user.email` без отдельного правила;
- чужая identity никогда не переносится только по совпадению email;
- конкурентные callback/consume завершаются идемпотентно;
- последнюю identity отвязать нельзя.

## 9. Acceptance criteria HC-025

- Google-first → Email-second не создаёт второй профиль и требует Google confirmation.
- Email-first → Google-second не создаёт второй профиль и требует `link_email` confirmation.
- После linking оба способа всегда возвращают один `user_id`, workspace и profile.
- До подтверждения второго способа bootstrap не создаёт user/workspace/profile.
- Совпадение email без второго доказательства ничего не объединяет.
- Отказ позволяет только осознанно создать отдельный аккаунт.
- Повторный linking идемпотентен.
- Подмена purpose/state/PKCE/subject отклоняется.
- Чужая identity не перехватывается.
- Existing duplicates направляются в HC-026.
- Все действия отражены в audit без утечки токенов и PII в логи.

## 10. Порядок реализации

1. Аудит фактических Google callback, Magic Link consume и bootstrap.
2. Модель link-intent и миграция.
3. Pre-bootstrap lookup по verified email без автоматического merge.
4. Google-first / Email-second flow.
5. Email-first / Google-second flow.
6. UI подтверждения link-on-login.
7. UI «Способы входа».
8. Security, concurrency и negative tests.
9. HC-026 для существующих дублей.
10. HC-027 — запрет молчаливого создания новых дублей во всех bootstrap-путях.
11. Обновление CURRENT-STATE, DEVELOPMENT-HISTORY и PROJECT-PLAN после merge и deployment.
