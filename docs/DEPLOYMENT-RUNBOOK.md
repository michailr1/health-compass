# Health Compass — production deployment runbook

Целевой production-сервер: `funti.cc`  
Production IP: `172.245.108.154`  
Целевой URL: `https://health.funti.cc`  
Backend: `127.0.0.1:8100`  
Reverse proxy: Apache 2  
Production frontend symlink: `/opt/health-compass/current-subdomain`

## Ответственность

VPS-агент не пишет продуктовый код и не создаёт миграции. Он разворачивает только заранее проверенный commit SHA и возвращает фактические результаты.

VPS-агент также не должен:

- редактировать файлы репозитория;
- создавать commit, push, branch, PR или merge;
- изменять GitHub;
- самостоятельно менять архитектуру PostgreSQL-ролей;
- печатать `.env`, пароли, токены, ключи или database URLs.

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
3. Получить ожидаемый exact commit SHA и доказать, что он достижим из `origin/main`.
4. Зафиксировать `HEAD_BEFORE`, текущую Alembic revision, backend unit и frontend symlink target.
5. Подтвердить через Apache config, что `health.funti.cc` обслуживается из `/opt/health-compass/current-subdomain`.
6. Сделать backup production PostgreSQL перед миграциями.
7. Проверить backup через `pg_restore --list`, записать размер и checksum.
8. Выполнить backend compile, Ruff и pytest в `/opt/health-compass/repo/backend`.
9. Выполнить frontend `npm ci`, lint, typecheck, tests и `npm run build` в `/opt/health-compass/repo`.
10. Не выводить `.env`, пароли, token values, encryption keys и database URLs.

## Порядок релиза

Все пункты ниже выполняются на production-сервере `funti.cc`.

1. Fetch конкретного target SHA без изменений GitHub.
2. Проверить clean tree и exact SHA.
3. Alembic `current`, `heads`, `upgrade head`, `current` через существующий migrator environment.
4. Restart существующего backend unit.
5. Дождаться local health `127.0.0.1:8100/health → 200`.
6. Создать новую immutable frontend release-директорию.
7. Скопировать в неё exact target build output.
8. Атомарно переключить именно `/opt/health-compass/current-subdomain`.
9. Проверить `apachectl configtest`.
10. Reload Apache.
11. Через HTTPS проверить production `index.html` и реально подключённый JS asset нового release.
12. Выполнить smoke tests.
13. Ручные auth tests выполняются владельцем в браузере.

`/opt/health-compass/current` может существовать, но не считается serving path для `health.funti.cc`, пока Apache config не докажет обратное.

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
- `/` отдаёт frontend из `/opt/health-compass/current-subdomain`;
- SPA fallback на `/index.html`;
- отдельный TLS certificate для `health.funti.cc`.

DNS-запись создаётся в панели DNS, а Google callback добавляется в Google Cloud Console.

## HC-017 Phase 1

Для первого production rollout HC-017 B–E2 действует отдельный план:

```text
docs/implementation/HC-017-B-E2-CONTROLLED-PRODUCTION-ROLLOUT.md
```

Обязательная настройка Phase 1:

```text
DOCUMENT_UPLOAD_ENABLED=false
```

Phase 1 не включает provision scanner/renderer/reconciler/OCR services и не выполняет полный document/OCR/Labs pipeline. Текущий backend намеренно запрещает `DOCUMENT_UPLOAD_ENABLED=true` вне development до отдельного контролируемого разрешения.

## Smoke tests

HTTP-команды выполняются на production-сервере `funti.cc`:

- `/` → 200;
- `/login` → 200;
- `/app` без сессии → frontend/login flow;
- `/api/health` → 200;
- `/api/auth/provider/google` → 307;
- Google redirect содержит callback `https://health.funti.cc/api/auth/callback` и `prompt=select_account`;
- email request → 202;
- magic link consume → 303 без вывода токена;
- logout отзывает session и удаляет cookie;
- direct refresh `/app/oura`, `/app/genetics`, `/app/plan` и новых document/Lab routes не даёт 404;
- production `index.html` подключает JS bundle нового release;
- JS/CSS assets нового release доступны без 404;
- `DOCUMENT_UPLOAD_ENABLED=false` подтверждено без печати env-файла;
- нет неожиданных 5xx.

Ручные Google/email login, logout и direct refresh проверяются владельцем в браузере.

## Security regression

SQL и backend проверки выполняются на production-сервере `funti.cc`. Пользовательские login-сценарии выполняются в браузере.

- два Google-пользователя входят отдельно;
- email identity повторно использует тот же user id;
- пользователь A не видит данные B;
- self-grant к чужому profile/workspace блокируется;
- Alembic имеет ровно один head;
- runtime и worker PostgreSQL roles сохраняют ожидаемый `NOBYPASSRLS`;
- worker roles не имеют широких direct table mutation grants;
- PUBLIC execute на restricted functions отозван;
- в свежих логах отсутствуют `54001`, `42501`, неожиданные `permission denied`, traceback и 5xx;
- в логах нет токенов, document/OCR content, medical values или secret values.

## Rollback

Rollback выполняется на production-сервере `funti.cc`.

Frontend rollback: вернуть `/opt/health-compass/current-subdomain` на предыдущую release-директорию, выполнить Apache config test и reload, затем подтвердить production bundle через HTTPS.

Backend rollback допускается только если предыдущий backend совместим с уже применённой схемой. Автоматический Alembic downgrade запрещён без отдельного анализа.

Если миграции уже применены и совместимость предыдущего backend не доказана, безопаснее оставить новый backend при `DOCUMENT_UPLOAD_ENABLED=false` или восстановить verified backup только по отдельному решению владельца.

При cross-user leak сервис переводится в maintenance; доступность не важнее изоляции медицинских данных.

## После релиза

VPS-агент только возвращает фактический отчёт. Он не обновляет GitHub.

Отчёт должен содержать:

- deployed exact SHA;
- backup path, size, checksum и verify result;
- Alembic before/heads/after;
- backend unit и status;
- frontend release path;
- `current-subdomain` before/after;
- production bundle before/after и asset HTTP status;
- HTTP/security smoke results;
- свежие sanitized log findings;
- подтверждение, что секреты не выводились.

После получения отчёта основной development agent обновляет `CURRENT-STATE.md`, `DEVELOPMENT-HISTORY.md`, production evidence и при необходимости создаёт release tag в GitHub.
