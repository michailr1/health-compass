# Health Compass — security invariants

Эти правила обязательны для всех изменений. Их нельзя ослаблять без отдельного ADR, threat review и негативных тестов.

## Identity и sessions

- Для MVP используются только direct Google OIDC и Email Magic Links.
- Authentik, Keycloak и внешний IAM не возвращаются без нового ADR.
- Google identity определяется парой `provider + subject`, а не email.
- Email Magic Link одноразовый, ограничен по времени и хранится только в виде hash.
- GET Magic Link не имеет права поглощать token или создавать session; meaningful consume выполняется только после явного user action через POST.
- Tokens, cookies, authorization headers и raw auth query strings не попадают в logs, analytics и error pages.
- Серверная сессия хранится в PostgreSQL; browser получает HttpOnly Secure cookie.
- Logout изменяет state только через POST и отзывает локальную session.
- User/session RLS context устанавливается внутри транзакции запроса.
- Verified email само по себе не объединяет аккаунты.
- Production account-linking protection является fail-safe invariant, а не необязательным feature toggle.
- Последнюю identity пользователя удалить нельзя.

## PostgreSQL и RLS

- Все таблицы с пользовательскими и медицинскими данными: `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`.
- Runtime role: `health_compass_app` с `NOBYPASSRLS`.
- Migrator role не используется приложением.
- Helper-функции, которым необходим обход RLS, принадлежат только `health_compass_rls_definer NOLOGIN BYPASSRLS`.
- Такие функции возвращают только scalar boolean/uuid, используют статический SQL, `search_path=''` и `row_security=off`.
- `PUBLIC EXECUTE` на security-definer функции запрещён.
- Новая таблица не принимается без RLS policies и двухпользовательских негативных тестов.
- Запрещены политики, позволяющие пользователю самостоятельно выдать себе доступ к чужому profile/workspace.
- Bootstrap owner выполняется отдельными statements/flush; профиль и permission нельзя объединять в один statement без повторного анализа snapshot semantics.
- Column-level grants используются для identity-critical и system-managed полей; runtime role не получает широкий UPDATE без необходимости.
- Duplicate assessment обязан учитывать все profile-owned таблицы текущей схемы до destructive absorption.

## Tenant isolation tests

Минимальный обязательный набор:

- A видит свои workspace/profile/dashboard;
- A не видит данные B;
- A не может выдать себе owner на profile B;
- A не может добавить себя в workspace B;
- без user context SELECT возвращает 0 строк;
- повторный вход не создаёт дубликат user;
- INSERT с RETURNING проходит для profile, permission, snapshot и auth session;
- проверка проводится на «тёплых» данных, а не только при первом bootstrap;
- duplicate resolution с любыми meaningful profile rows не удаляет данные и не возвращает необработанный 500.

## Clinical data integrity

- `canonical_concept_id` соответствует domain конкретной clinical section.
- Изменение или очистка source `code`/`code_system` атомарно обновляет либо очищает canonical mapping.
- Derived canonical columns не должны напрямую изменяться клиентом без явного server contract.
- Review state `confirmed_none` нельзя сохранить, если в той же атомарной проверке существуют несовместимые записи.
- Void/update используют optimistic concurrency и возвращают controlled conflict для stale write.
- User-entered free text не переписывается молча каноническим понятием.
- Free-text fallback остаётся доступным при отсутствии dictionary match.

## Privacy и medical safety

- Демонстрационные данные должны быть явно помечены и не выдаваться за реальные данные пользователя.
- Никаких автоматических диагнозов, назначений или отмены лечения.
- Любая медицинская интерпретация имеет provenance и источник.
- AI-ответ без evidence запрещён после включения AI-контура.
- Retrieval фильтруется по `profile_id` до поиска.
- Аналитика и логи не содержат медицинских значений, токенов и секретов.
- Экспорт и удаление пользователя должны охватывать raw, normalized, derived data и embeddings.

## API и routing

- Один method/path pair имеет одного канонического владельца route.
- Нельзя полагаться на порядок `include_router` для выбора корректного API contract.
- Backend errors используют единый documented envelope и возвращают `request_id` без stack trace.
- State-changing GET routes запрещены, если нет отдельного ADR и компенсирующей защиты.

## CI и migrations

- Frontend CI выполняет full-source lint, TypeScript typecheck, tests и build.
- PostgreSQL CI проверяет migrations, RLS и privilege invariants.
- Для release-bound migration выполняется полный cycle `head → base → head` на отдельной test DB либо документируется безопасное исключение.
- `downgrade(): pass` запрещён, если после downgrade database state не соответствует объявленной revision.
- CI должен быть зелёным на exact commit SHA, который предлагается к deployment.

## Deployment

- Production deploy выполняется только из конкретного проверенного commit SHA.
- Перед миграцией — backup и проверка restore listing.
- Порядок: migration → backend → frontend → smoke.
- Автоматический downgrade запрещён после частично применённой или нетранзакционной миграции.
- Cross-user leak важнее доступности: при подтверждении сервис переводится в maintenance до исправления.
- Scanner GET, wrong-domain canonical mapping, duplicate-resolution 500 или token leakage являются stop conditions.
