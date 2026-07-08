# Health Compass — security invariants

Эти правила обязательны для всех изменений. Их нельзя ослаблять без отдельного ADR, threat review и негативных тестов.

## Identity и sessions

- Для MVP используются только direct Google OIDC и Email Magic Links.
- Authentik, Keycloak и внешний IAM не возвращаются без нового ADR.
- Google identity определяется парой `provider + subject`, а не email.
- Email Magic Link одноразовый, ограничен по времени и хранится только в виде hash.
- Серверная сессия хранится в PostgreSQL; browser получает HttpOnly Secure cookie.
- Logout отзывает локальную сессию.
- User/session RLS context устанавливается внутри транзакции запроса.

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

## Tenant isolation tests

Минимальный обязательный набор:

- A видит свои workspace/profile/dashboard;
- A не видит данные B;
- A не может выдать себе owner на profile B;
- A не может добавить себя в workspace B;
- без user context SELECT возвращает 0 строк;
- повторный вход не создаёт дубликат user;
- INSERT с RETURNING проходит для profile, permission, snapshot и auth session;
- проверка проводится на «тёплых» данных, а не только при первом bootstrap.

## Privacy и medical safety

- Демонстрационные данные должны быть явно помечены и не выдаваться за реальные данные пользователя.
- Никаких автоматических диагнозов, назначений или отмены лечения.
- Любая медицинская интерпретация имеет provenance и источник.
- AI-ответ без evidence запрещён после включения AI-контура.
- Retrieval фильтруется по `profile_id` до поиска.
- Аналитика и логи не содержат медицинских значений, токенов и секретов.
- Экспорт и удаление пользователя должны охватывать raw, normalized, derived data и embeddings.

## Deployment

- Production deploy выполняется только из конкретного проверенного commit SHA.
- Перед миграцией — backup и проверка restore listing.
- Порядок: migration → backend → frontend → smoke.
- Автоматический downgrade запрещён после частично применённой или нетранзакционной миграции.
- Cross-user leak важнее доступности: при подтверждении сервис переводится в maintenance до исправления.
