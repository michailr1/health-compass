# Health Compass — production deployment runbook

Целевой production-сервер: `funti.cc`  
Production IP: `172.245.108.154`  
Целевой URL: `https://health.funti.cc`  
Backend: `127.0.0.1:8100`  
Reverse proxy: Apache 2

## Ответственность

VPS-агент не пишет продуктовый код и не создаёт миграции. Он разворачивает только заранее проверенный commit SHA и возвращает фактические результаты.

## Критически важное правило целевого сервера

Все серверные действия по Health Compass выполняются только после удалённого подключения к production-серверу:

```text
Hostname: funti.cc
Expected public IP: 172.245.108.154
Repository: /opt/health-compass/repo
```

В начале каждой задачи VPS-агенту необходимо явно написать:

```text
Подключись к production-серверу funti.cc (172.245.108.154) и выполняй все команды только на нём.
Не выполняй команды на локальной машине агента, его собственном VPS или другом сервере.
```

Перед любыми изменениями агент обязан подтвердить целевой сервер:

```bash
hostname -f || hostname
ip -4 addr show
getent hosts funti.cc
pwd
```

Если `funti.cc` не резолвится в `172.245.108.154`, репозиторий `/opt/health-compass/repo` отсутствует или есть сомнение, что подключение выполнено к нужному серверу, агент должен остановиться без изменений.

## До деплоя

Все пункты ниже выполняются на production-сервере `funti.cc` (`172.245.108.154`), если явно не указано иное.

1. Подтвердить hostname/IP и наличие `/opt/health-compass/repo`.
2. Проверить чистый `git status` в `/opt/health-compass/repo`.
3. Получить ожидаемый commit SHA.
4. Сделать backup production PostgreSQL перед миграциями.
5. Проверить backup через `pg_restore --list`.
6. Выполнить backend compile, Ruff и pytest в `/opt/health-compass/repo/backend`.
7. Выполнить frontend `npm ci` и `npm run build` в `/opt/health-compass/repo`.
8. Не выводить `.env`, пароли, token values и database URLs.

## Порядок релиза

Все пункты ниже выполняются на production-сервере `funti.cc`.

1. Pull конкретного HEAD.
2. Alembic `current`, `heads`, `upgrade head`, `current`.
3. Restart backend.
4. Создать новую frontend release-директорию.
5. Атомарно переключить symlink.
6. Reload Apache.
7. Smoke tests.
8. Ручные auth tests выполняются владельцем в браузере.

## Поддомен

Production environment настраивается на `funti.cc` в production env-файле:

```env
FRONTEND_URL=https://health.funti.cc/app
OIDC_REDIRECT_URI=https://health.funti.cc/api/auth/callback
MAGIC_LINK_CONSUME_URL=https://health.funti.cc/api/auth/email/consume
```

Backend запускается без legacy `--root-path /health/api`.

Apache настраивается на `funti.cc`:

- `/api/` proxy на `http://127.0.0.1:8100/`;
- `/` отдаёт frontend;
- SPA fallback на `/index.html`;
- отдельный TLS certificate для `health.funti.cc`.

DNS-запись создаётся в панели DNS, а Google callback добавляется в Google Cloud Console.

## Smoke tests

HTTP-команды выполняются на production-сервере `funti.cc`:

- `/` → 200;
- `/login` → 200;
- `/app` без сессии → frontend/login flow;
- `/api/health` → 200;
- `/api/auth/provider/google` → 307;
- Google redirect содержит новый callback и `prompt=select_account`;
- email request → 202;
- magic link consume → 303;
- logout отзывает session и удаляет cookie;
- direct refresh `/app/oura`, `/app/genetics`, `/app/plan` не даёт 404.

Ручные Google/email login, logout и direct refresh проверяются в браузере.

## Security regression

SQL и backend проверки выполняются на production-сервере `funti.cc`. Пользовательские login-сценарии выполняются в браузере.

- два Google-пользователя входят отдельно;
- email identity повторно использует тот же user id;
- пользователь A не видит данные B;
- self-grant к чужому profile/workspace блокируется;
- в логах отсутствуют `54001`, `42501`, `permission denied`, traceback и 5xx.

## Rollback

Rollback выполняется на production-сервере `funti.cc`.

Frontend rollback: вернуть symlink на предыдущую release-директорию и reload Apache.

Backend rollback допускается только если миграции совместимы назад. Автоматический Alembic downgrade запрещён без отдельного анализа.

При cross-user leak сервис переводится в maintenance; доступность не важнее изоляции медицинских данных.

## После релиза

- на `funti.cc` записать deployed SHA;
- в GitHub обновить `CURRENT-STATE.md` и `DEVELOPMENT-HISTORY.md`;
- сохранить HTTP-коды и результаты auth smoke;
- после подтверждения нового поддомена включить redirect со старого `/health` на `funti.cc`;
- после стабилизации создать PR в `main` и release tag в GitHub.
