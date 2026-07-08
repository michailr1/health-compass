# Health Compass — production deployment runbook

Целевой URL: `https://health.funti.cc`  
Backend: `127.0.0.1:8100`  
Reverse proxy: Apache 2

## Ответственность

VPS-агент не пишет продуктовый код и не создаёт миграции. Он разворачивает только заранее проверенный commit SHA и возвращает фактические результаты.

## Обязательное правило для инструкций

Каждый блок команд должен явно указывать место выполнения.

Допустимые пометки:

- **Выполнять на VPS** — команды Linux, Git, PostgreSQL, Apache, systemd, Certbot, build и deploy;
- **Выполнять локально на компьютере пользователя** — только когда это действительно требуется;
- **Выполнять в Google Cloud Console** — OAuth redirect URI и иные настройки Google;
- **Выполнять в панели DNS** — A/CNAME/TXT записи;
- **Выполнять в браузере** — ручные login/logout и UI-проверки.

Для команд на VPS дополнительно указывать рабочий каталог, например:

```text
Место выполнения: VPS
Рабочий каталог: /opt/health-compass/repo
```

Если команда требует `sudo`, это должно быть указано в самой команде. Нельзя оставлять агенту возможность угадывать, где выполнять шаг.

## До деплоя

Все пункты ниже выполняются **на VPS**, если явно не указано иное.

1. Проверить чистый `git status` в `/opt/health-compass/repo`.
2. Получить ожидаемый commit SHA.
3. Сделать backup production PostgreSQL перед миграциями.
4. Проверить backup через `pg_restore --list`.
5. Выполнить backend compile, Ruff и pytest в `/opt/health-compass/repo/backend`.
6. Выполнить frontend `npm ci` и `npm run build` в `/opt/health-compass/repo`.
7. Не выводить `.env`, пароли, token values и database URLs.

## Порядок релиза

Все пункты ниже выполняются **на VPS**.

1. Pull конкретного HEAD.
2. Alembic `current`, `heads`, `upgrade head`, `current`.
3. Restart backend.
4. Создать новую frontend release-директорию.
5. Атомарно переключить symlink.
6. Reload Apache.
7. Smoke tests.
8. Ручные auth tests выполняются **в браузере**.

## Поддомен

Production environment настраивается **на VPS** в production env-файле:

```env
FRONTEND_URL=https://health.funti.cc/app
OIDC_REDIRECT_URI=https://health.funti.cc/api/auth/callback
MAGIC_LINK_CONSUME_URL=https://health.funti.cc/api/auth/email/consume
```

Backend запускается без legacy `--root-path /health/api`.

Apache настраивается **на VPS**:

- `/api/` proxy на `http://127.0.0.1:8100/`;
- `/` отдаёт frontend;
- SPA fallback на `/index.html`;
- отдельный TLS certificate для `health.funti.cc`.

DNS-запись создаётся **в панели DNS**, а Google callback добавляется **в Google Cloud Console**.

## Smoke tests

HTTP-команды выполняются **на VPS**:

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

Ручные Google/email login, logout и direct refresh проверяются **в браузере**.

## Security regression

SQL и backend проверки выполняются **на VPS**. Пользовательские login-сценарии выполняются **в браузере**.

- два Google-пользователя входят отдельно;
- email identity повторно использует тот же user id;
- пользователь A не видит данные B;
- self-grant к чужому profile/workspace блокируется;
- в логах отсутствуют `54001`, `42501`, `permission denied`, traceback и 5xx.

## Rollback

Rollback выполняется **на VPS**.

Frontend rollback: вернуть symlink на предыдущую release-директорию и reload Apache.

Backend rollback допускается только если миграции совместимы назад. Автоматический Alembic downgrade запрещён без отдельного анализа.

При cross-user leak сервис переводится в maintenance; доступность не важнее изоляции медицинских данных.

## После релиза

- на VPS записать deployed SHA;
- в GitHub обновить `CURRENT-STATE.md` и `DEVELOPMENT-HISTORY.md`;
- сохранить HTTP-коды и результаты auth smoke;
- после подтверждения нового поддомена включить redirect со старого `/health` на VPS;
- после стабилизации создать PR в `main` и release tag в GitHub.
