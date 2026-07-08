# Health Compass

Health Compass — многопользовательский веб-портал для хранения, обработки и отображения персональных данных о здоровье.

## Текущий статус

Рабочая ветка:

```text
feat/direct-google-and-email-auth
```

Целевой production URL:

```text
https://health.funti.cc
```

Текущий старый URL сохраняется только на период перехода:

```text
https://funti.cc/health
```

Архивная ветка прежней архитектуры через Authentik:

```text
feat/identity-and-profile-access
```

Архивную ветку не удалять.

## Каноническая документация

- [Основной план](docs/PROJECT-PLAN.md)
- [Текущее состояние](docs/CURRENT-STATE.md)
- [История разработки и инцидентов](docs/DEVELOPMENT-HISTORY.md)
- [Security invariants](docs/SECURITY-INVARIANTS.md)
- [Product & UX baseline](docs/PRODUCT-UX-BASELINE.md)
- [AI product and safety](docs/AI-PRODUCT-SAFETY.md)
- [Production deployment runbook](docs/DEPLOYMENT-RUNBOOK.md)
- [Рекомендации Fable](docs/reviews/FABLE-RECOMMENDATIONS.md)
- [Реестр источников](docs/source-index/SOURCE-REGISTER.md)

При расхождении документации с кодом приоритет имеют код, миграции, тесты и подтверждённое production-состояние. Документация должна быть обновлена после каждого релиза и архитектурного изменения.

## Архитектура

### Backend

- FastAPI;
- Python 3.12+;
- SQLAlchemy 2;
- Alembic;
- PostgreSQL;
- PostgreSQL Row-Level Security;
- локальные серверные сессии.

### Frontend

- React 18;
- TypeScript;
- Vite;
- TanStack Query;
- Tailwind CSS;
- shadcn/ui;
- React Router;
- Recharts.

### Аутентификация

Для MVP используется собственная identity/session модель:

- прямой Google OAuth 2.0 / OpenID Connect;
- PKCE S256, state, nonce и `prompt=select_account`;
- Email Magic Links через Brevo;
- локальные users, identities и sessions;
- собственные workspaces, profiles и permissions;
- PostgreSQL RLS для tenant isolation.

В MVP не используются Authentik, Keycloak или внешний IAM.

Google identity определяется парой:

```text
provider + subject
```

Email не является ключом автоматического объединения разных identity.

## Безопасность

- Security first и fail-closed production configuration.
- Runtime и migrator роли PostgreSQL разделены.
- Защищённые таблицы используют `FORCE ROW LEVEL SECURITY`.
- RLS helper-функции принадлежат выделенной роли `health_compass_rls_definer NOLOGIN BYPASSRLS`.
- `PUBLIC EXECUTE` для security-definer helpers запрещён.
- User/session context устанавливается внутри транзакции запроса.
- Dev auth разрешён только локально.
- Секреты не хранятся в Git и не выводятся в отчёты.

Подробности: [docs/SECURITY-INVARIANTS.md](docs/SECURITY-INVARIANTS.md).

## Реализовано

- Google OIDC login и локальный logout;
- Email Magic Link registration/login;
- PostgreSQL sessions;
- workspace/profile/dashboard bootstrap;
- multi-user RLS isolation;
- устранение рекурсии SQLSTATE `54001`;
- закрытие self-grant owner и self-add workspace escalation;
- интеграционный RLS пакет: `22 PASS, 0 FAIL`;
- отдельные демонстрационные dashboard records для каждого пользователя.

Медицинские показатели пока демонстрационные и должны явно обозначаться как такие до реализации реального импорта.

## Текущий этап

Перенос приложения с подкаталога `/health` на корень поддомена `health.funti.cc`.

Целевые адреса:

```text
https://health.funti.cc/
https://health.funti.cc/api/health
https://health.funti.cc/api/auth/callback
https://health.funti.cc/api/auth/email/consume
```

После полной проверки старый `/health` будет перенаправляться на новый поддомен. Затем рабочая ветка будет слита в `main`, а production начнёт разворачиваться из `main`.

Продуктовый и UI baseline этапов Fable 3/3.5 зафиксирован в документации как целевой дизайн и не считается реализованным до появления кода, API и тестов.

## Локальный запуск frontend

Требуется Node.js 20–22 и npm 10.

```bash
npm ci
npm run dev
```

Проверки:

```bash
npm run build
npm run lint
npm test
```

## Локальный запуск backend

Требуется Python 3.12+ и PostgreSQL.

```bash
cd backend
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8100
```

Проверки:

```bash
.venv/bin/python -m compileall -q app alembic tests
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
```

Интеграционные тесты PostgreSQL должны использовать отдельную БД с именем, заканчивающимся на `_test`.

## Production

Backend service:

```text
health-compass-api.service
```

Production environment:

```text
/etc/health-compass/backend.env
```

Target URLs:

```env
FRONTEND_URL=https://health.funti.cc/app
OIDC_REDIRECT_URI=https://health.funti.cc/api/auth/callback
MAGIC_LINK_CONSUME_URL=https://health.funti.cc/api/auth/email/consume
```

Значения OAuth secrets, SMTP credentials, database credentials, session tokens и иных секретов запрещено сохранять в репозитории или выводить в логи.

## Роли агентов

ChatGPT/coding role отвечает за архитектуру, код, миграции, тесты, ADR и документацию.

VPS-агент отвечает за backup, pull конкретного HEAD, build, migrations, Apache, systemd, Certbot, deployment, smoke tests и rollback. VPS-агент не пишет продуктовый код и не принимает архитектурных решений.

## Медицинский дисклеймер

Health Compass не является медицинским изделием и не заменяет консультацию врача. Любые выводы и рекомендации являются информационными материалами, а не диагнозом или назначением лечения.
