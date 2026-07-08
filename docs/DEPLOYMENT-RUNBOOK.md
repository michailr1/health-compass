# Health Compass — production deployment runbook

Целевой URL: `https://health.funti.cc`  
Backend: `127.0.0.1:8100`  
Reverse proxy: Apache 2

## Ответственность

VPS-агент не пишет продуктовый код и не создаёт миграции. Он разворачивает только заранее проверенный commit SHA и возвращает фактические результаты.

## До деплоя

1. Проверить чистый `git status`.
2. Получить ожидаемый commit SHA.
3. Сделать backup production PostgreSQL перед миграциями.
4. Проверить backup через `pg_restore --list`.
5. Выполнить backend compile, Ruff и pytest.
6. Выполнить frontend `npm ci` и `npm run build`.
7. Не выводить `.env`, пароли, token values и database URLs.

## Порядок релиза

1. Pull конкретного HEAD.
2. Alembic `current`, `heads`, `upgrade head`, `current`.
3. Restart backend.
4. Создать новую frontend release-директорию.
5. Атомарно переключить symlink.
6. Reload Apache.
7. Smoke tests.
8. Ручные auth tests.

## Поддомен

Production environment:

```env
FRONTEND_URL=https://health.funti.cc/app
OIDC_REDIRECT_URI=https://health.funti.cc/api/auth/callback
MAGIC_LINK_CONSUME_URL=https://health.funti.cc/api/auth/email/consume
```

Backend запускается без legacy `--root-path /health/api`.

Apache:

- `/api/` proxy на `http://127.0.0.1:8100/`;
- `/` отдаёт frontend;
- SPA fallback на `/index.html`;
- отдельный TLS certificate для `health.funti.cc`.

## Smoke tests

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

## Security regression

- два Google-пользователя входят отдельно;
- email identity повторно использует тот же user id;
- пользователь A не видит данные B;
- self-grant к чужому profile/workspace блокируется;
- в логах отсутствуют `54001`, `42501`, `permission denied`, traceback и 5xx.

## Rollback

Frontend rollback: вернуть symlink на предыдущую release-директорию и reload Apache.

Backend rollback допускается только если миграции совместимы назад. Автоматический Alembic downgrade запрещён без отдельного анализа.

При cross-user leak сервис переводится в maintenance; доступность не важнее изоляции медицинских данных.

## После релиза

- записать deployed SHA;
- обновить `CURRENT-STATE.md` и `DEVELOPMENT-HISTORY.md`;
- сохранить HTTP-коды и результаты auth smoke;
- после подтверждения нового поддомена включить redirect со старого `/health`;
- после стабилизации создать PR в `main` и release tag.
