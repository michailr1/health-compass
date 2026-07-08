# Health Compass — текущее состояние

Дата: 2026-07-09  
Рабочая ветка: `feat/direct-google-and-email-auth`  
Production URL: `https://health.funti.cc`  
Старый переходный URL: `https://funti.cc/health`  
Развёрнутый commit: `4e7df2bdeb313cd788165c182b64ef83487720bc`

## Что работает

- FastAPI backend и React/Vite frontend.
- PostgreSQL + Alembic, текущий production head: `0021`.
- Прямой Google OIDC.
- Выбор Google-аккаунта через `prompt=select_account`.
- Email Magic Links через Brevo.
- Подтверждённый отправитель: `health@funti.cc`.
- Локальные серверные сессии в PostgreSQL.
- Logout с отзывом сессии.
- Workspace/profile/dashboard bootstrap.
- Демонстрационные данные создаются отдельно для каждого профиля и явно помечаются как демонстрационные.
- FORCE RLS и tenant isolation.
- Два реальных пользователя входят через Google на прежнем production flow.
- Email-регистрация и повторный вход работают на прежнем production flow.
- Новый поддомен `health.funti.cc` развёрнут с HTTPS, Apache VirtualHost и root-path frontend/API.
- Ручной Google login на `https://health.funti.cc/login` подтверждён владельцем.

## Развёртывание health.funti.cc

Подтверждено VPS-агентом на production-сервере `funti.cc` (`172.245.108.154`):

- deployed HEAD: `4e7df2bdeb313cd788165c182b64ef83487720bc`;
- legacy `/health` paths отсутствуют в исполняемом коде и bundle;
- `compileall`: OK;
- Ruff: all checks passed;
- frontend build: 2476 modules, 68 seconds;
- DNS: `health.funti.cc → 172.245.108.154`;
- TLS: Let's Encrypt;
- Apache configtest: Syntax OK;
- backend service: active;
- `/`, `/login`, `/api/health` возвращают 200;
- Google endpoint возвращает 307 с callback `https://health.funti.cc/api/auth/callback` и `prompt=select_account`;
- SPA routes `/app`, `/app/oura` и другие возвращают 200;
- старый `/health` пока продолжает возвращать 200;
- свежие логи не содержат 500, 503, 54001 или Traceback.

Backend pytest на VPS: `14 PASS, 4 FAIL`.

Из четырёх failures:

- три migration-теста не имеют тестового подключения к PostgreSQL в этом запуске;
- один health test ожидает старое поведение/path;
- failures признаны известными, но должны быть исправлены до формального release gate и merge в `main`.

## Google Cloud Console

Authorized redirect URI уже добавлен владельцем:

```text
https://health.funti.cc/api/auth/callback
```

Старый callback пока сохраняется:

```text
https://funti.cc/health/api/auth/callback
```

Сообщение VPS-агента о необходимости добавить новый URI является устаревшим чек-листом, а не открытой задачей.

## Ручная приёмка нового домена

Подтверждено владельцем:

- ссылка `https://health.funti.cc` открывается;
- Google login работает на новом поддомене.

Остаётся проверить:

1. Logout и повторный вход.
2. Email Magic Link request/consume на новом поддомене.
3. Одноразовость magic link.
4. Dashboard и маркировку демонстрационных данных.
5. Двухпользовательскую изоляцию на новом URL.

## Последние security-исправления

- миграция `0020`: устранение RLS-рекурсии и tenant escalation;
- миграция `0021`: исправление владельца и режима context helper-функций;
- отдельная роль `health_compass_rls_definer NOLOGIN BYPASSRLS`;
- `search_path=''`, `row_security=off`;
- `PUBLIC EXECUTE` отозван;
- session hash устанавливается перед `AuthSession INSERT ... RETURNING`;
- отрицательные тесты блокируют self-grant owner и self-add в чужой workspace.

Результат полного интеграционного RLS-прогона до переноса: `22 PASS, 0 FAIL`.

## Утверждённый target baseline

В документацию перенесены результаты Fable Stage 3 и 3.5:

- Product & UX baseline;
- AI product and safety baseline;
- Human-first MVP vertical slice;
- Human/Pet separation;
- navigation, screen states, component map и frontend order;
- дополнительные функции: Attention Inbox, search, bulk upload, autosave OCR, session management и другие.

Это целевой дизайн, а не реализованный функционал. Он не должен отображаться как current state без кода, API и тестов.

## Следующие действия

1. Исправить или корректно изолировать 4 pytest failures.
2. Завершить оставшиеся ручные auth/security проверки.
3. После ручной приёмки включить redirect со старого `/health`.
4. Создать PR `feat/direct-google-and-email-auth → main`.
5. Выпустить тег `v0.1.0-auth-mvp`.
6. Начать PHASE-03 с утверждения API contracts для первого Human-first vertical slice.

## Известные ограничения

- Медицинские показатели пока демонстрационные.
- Реальные загрузки анализов и интеграции устройств ещё не реализованы.
- Magic link сейчас потребляется GET-запросом; scanner-safe confirmation остаётся обязательной задачей.
- Invitations и совместный доступ пока не готовы.
- Product/UX и AI baseline утверждены только на уровне документации.
- Production пока развёрнут из feature-ветки; после релиза источником истины должен стать `main`.
- Текущий production SHA отстаёт от ветки только по документационным изменениям после `4e7df2...`.

## Роли

### ChatGPT / coding role

- архитектура;
- продуктовый код;
- миграции и тесты;
- ADR и документация;
- формирование точного runbook.

### VPS-агент

- подключение только к production-серверу `funti.cc` (`172.245.108.154`);
- backup;
- pull конкретного HEAD;
- build/migrate/deploy;
- Apache, systemd, Certbot и environment;
- smoke-тесты, логи и rollback;
- не принимает архитектурных решений и не пишет продуктовый код.

## Stop conditions

Немедленно остановить релиз при:

- подключении не к `funti.cc` (`172.245.108.154`);
- расхождении ожидаемого HEAD;
- неуспешной миграции;
- признаках cross-user leak;
- `54001`, `42501`, `permission denied`, traceback или 5xx в ключевых сценариях;
- несовпадении Google redirect URI;
- выводе секретов в журнал или отчёт.
