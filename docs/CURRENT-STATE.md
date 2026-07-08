# Health Compass — текущее состояние

Дата: 2026-07-09  
Рабочая ветка: `feat/direct-google-and-email-auth`  
Production URL: `https://health.funti.cc`  
Старый переходный URL: `https://funti.cc/health`  
Развёрнутый commit: `e3523ac03331d3c51e722a0fe54ee1a24a464141`

## Что работает

- FastAPI backend и React/Vite frontend.
- PostgreSQL + Alembic, production head `0021`.
- Прямой Google OIDC с `prompt=select_account`.
- Email Magic Links через Brevo.
- Friendly page для использованной или просроченной magic link.
- Локальные серверные сессии и logout с отзывом сессии.
- Workspace/profile/dashboard bootstrap.
- Демонстрационные данные создаются отдельно для каждого профиля и явно помечены.
- FORCE RLS и tenant isolation.
- Production-поддомен `health.funti.cc` работает через HTTPS и отдельный Apache VirtualHost.

## Подтверждённая приёмка

- Google login: PASS.
- Email Magic Link: PASS.
- Logout и повторный вход: PASS.
- Повторное использование magic link отклоняется: PASS.
- Friendly invalid-link page: PASS.
- Dashboard и маркировка демоданных: PASS.
- Tenant isolation между двумя пользователями: PASS.

Ручная cross-user проверка:

- у пользователей разные `user_id`, `profile_id`, `workspace_id`, `dashboard_id`;
- каждый видит один собственный профиль;
- B → dashboard A: 404;
- A → dashboard B: 404;
- чужие профили в `/api/profiles` отсутствуют.

## Последний production deployment

Подтверждено на `funti.cc` (`172.245.108.154`):

- HEAD `e3523ac03331d3c51e722a0fe54ee1a24a464141`;
- Git status clean;
- compileall: OK;
- Ruff: OK;
- pytest: `15 PASS, 11 SKIP, 0 FAIL`;
- frontend build: OK;
- frontend tests: `1 PASS`;
- systemd: active;
- Apache configtest: Syntax OK;
- `/api/health`, `/`, `/login`, `/auth-link?status=invalid`: 200;
- свежие логи без 500, 503, 54001, 42501, Traceback и permission denied.

Причины SKIP:

- тесты с БД требуют `TEST_DATABASE_*`;
- migration suite требует `TEST_DATABASE_MIGRATOR_URL`;
- production DB в тестах не используется.

## Google Cloud Console

Новый callback уже добавлен:

```text
https://health.funti.cc/api/auth/callback
```

Старый callback пока сохраняется:

```text
https://funti.cc/health/api/auth/callback
```

## Следующие действия

1. Включить redirect со старого `/health` на `https://health.funti.cc`.
2. Проверить redirect и rollback.
3. Создать PR `feat/direct-google-and-email-auth → main`.
4. Выпустить тег `v0.1.0-auth-mvp`.
5. Начать PHASE-03 с утверждения API contracts первого Human-first vertical slice.

## Известные ограничения

- Медицинские показатели пока демонстрационные.
- Реальные загрузки анализов и интеграции устройств ещё не реализованы.
- Magic link consume остаётся GET-based; scanner-safe confirmation требуется позже.
- Invitations и совместный доступ пока не готовы.
- Product/UX и AI baseline утверждены только на уровне документации.
- Production пока развёрнут из feature-ветки; после merge источником истины должен стать `main`.

## Роли

### ChatGPT / coding role

- архитектура;
- продуктовый код;
- миграции и тесты;
- ADR и документация;
- точные runbook-инструкции.

### VPS-агент

- подключение только к `funti.cc` (`172.245.108.154`);
- backup, build, deploy, Apache, systemd, Certbot, smoke tests и rollback;
- не пишет продуктовый код и не принимает архитектурных решений.

## Stop conditions

Остановить релиз при:

- подключении не к `funti.cc`;
- несовпадении HEAD;
- неуспешной миграции;
- признаках cross-user leak;
- 5xx, `54001`, `42501`, `permission denied` или Traceback;
- выводе секретов в отчёт.
