# Health Compass

Health Compass — многопользовательский веб-портал для хранения, обработки и отображения персональных данных о здоровье.

Проект находится в активной разработке. Текущая рабочая ветка:

```text
feat/direct-google-and-email-auth
```

Архивная ветка с прежней интеграцией через Authentik:

```text
feat/identity-and-profile-access
```

Архивную ветку не удалять: она сохраняется только как история предыдущей архитектуры.

## Текущая архитектура

### Backend

- FastAPI;
- Python 3.12+;
- SQLAlchemy 2;
- Alembic;
- PostgreSQL;
- PostgreSQL Row-Level Security;
- серверные сессии в PostgreSQL.

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

Для MVP используется собственная локальная модель пользователей без внешнего IAM:

- прямой Google OAuth 2.0 / OpenID Connect;
- Email Magic Links;
- локальные пользователи и identities;
- серверные session cookies;
- собственные роли, workspaces и profiles;
- PostgreSQL RLS для изоляции данных.

В проекте не используются:

- Authentik;
- Keycloak;
- внешний IAM;
- mock-аутентификация в production.

Локальный пользователь не определяется по email. Внешняя identity определяется парой:

```text
provider + subject
```

Для Google используется подтверждённый `sub`. Совпадение email между разными identity не должно автоматически объединять аккаунты.

## Безопасность

Основные принципы:

1. Security first.
2. Fail-closed конфигурация production.
3. Разделение runtime- и migrator-доступа к PostgreSQL.
4. `FORCE ROW LEVEL SECURITY` на защищённых таблицах.
5. Контекст пользователя и сессии устанавливается внутри транзакции запроса.
6. Секреты хранятся только на сервере и не попадают в Git.
7. Dev-auth разрешён только в локальном development-окружении.
8. Никаких mock-решений в production.

## Состояние реализации

На текущем этапе реализованы или подготовлены:

- прямой Google OIDC flow;
- PKCE S256, `state` и `nonce`;
- проверка issuer, audience, `azp`, expiry и `email_verified`;
- локальные PostgreSQL-сессии;
- локальный logout с отзывом сессии;
- Email Magic Link backend flow;
- миграции PostgreSQL до текущего Alembic head;
- усиленные RLS-политики;
- unit-тесты конфигурации и OIDC;
- базовый lint-контур.

До первого MVP ещё требуется:

- завершить production deployment прямого Google OIDC;
- провести реальный end-to-end вход через Google;
- настроить SMTP и проверить Email Magic Links;
- провести интеграционный RLS-тест минимум для двух пользователей;
- удалить оставшиеся упоминания и конфигурацию Authentik;
- подготовить первого реального пользователя.

## Структура репозитория

```text
backend/
  app/                 FastAPI-приложение
  alembic/             миграции PostgreSQL
  tests/               backend-тесты

src/
  components/          UI-компоненты
  context/             frontend context
  pages/               страницы приложения
  services/            API-клиенты и frontend-сервисы
```

## Локальный запуск frontend

Требуется Node.js 20–22 и npm 10.

```bash
npm install
npm run dev
```

Проверки frontend:

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
```

Настройте environment на основе локальной конфигурации проекта, затем:

```bash
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8100
```

Проверки backend:

```bash
.venv/bin/python -m compileall -q app alembic tests
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests
```

Интеграционные тесты PostgreSQL должны использовать отдельную БД с именем, заканчивающимся на `_test`.

## Production

Текущий целевой сервер Health Compass:

```text
funti.cc
```

`de.funti.cc` не является production-сервером Health Compass.

Публичный URL:

```text
https://funti.cc/health/
```

Google OAuth callback:

```text
https://funti.cc/health/api/auth/callback
```

Backend systemd service:

```text
health-compass-api.service
```

Production environment:

```text
/etc/health-compass/backend.env
```

Значения `OIDC_CLIENT_SECRET`, SMTP-паролей, database credentials, session tokens и других секретов запрещено сохранять в репозитории или выводить в логи.

## Медицинский дисклеймер

Health Compass не является медицинским изделием и не заменяет консультацию врача. Любые выводы и рекомендации должны рассматриваться как информационные материалы, а не как диагноз или назначение лечения.
