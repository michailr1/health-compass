# Health Compass — текущее состояние

Дата: 2026-07-09  
Рабочая ветка: `feat/direct-google-and-email-auth`  
Production сейчас: `https://funti.cc/health`  
Целевой URL: `https://health.funti.cc`

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
- Два реальных пользователя входят через Google.
- Email-регистрация и повторный вход работают.

## Последние security-исправления

- миграция `0020`: устранение RLS-рекурсии и tenant escalation;
- миграция `0021`: исправление владельца и режима context helper-функций;
- отдельная роль `health_compass_rls_definer NOLOGIN BYPASSRLS`;
- `search_path=''`, `row_security=off`;
- `PUBLIC EXECUTE` отозван;
- session hash устанавливается перед `AuthSession INSERT ... RETURNING`;
- отрицательные тесты блокируют self-grant owner и self-add в чужой workspace.

Результат интеграционной проверки: `22 PASS, 0 FAIL`.

## Текущая задача

Перенос приложения с подкаталога:

```text
https://funti.cc/health
```

на отдельный поддомен:

```text
https://health.funti.cc
```

DNS A-запись и новый Google Authorized Redirect URI уже добавлены владельцем.

## Следующие действия

1. Изменить код для работы от корня поддомена.
2. Добавить тесты новых URL и cookie paths.
3. Передать VPS-агенту конкретный commit SHA для деплоя.
4. Выпустить TLS и создать отдельный Apache VirtualHost.
5. Проверить Google и email login на новом URL.
6. Включить редирект со старого `/health`.
7. Обновить README и production runbook.
8. Merge в `main` и тег `v0.1.0-auth-mvp`.

## Известные ограничения

- Медицинские показатели пока демонстрационные.
- Реальные загрузки анализов и интеграции устройств ещё не реализованы.
- Magic link сейчас потребляется GET-запросом; scanner-safe confirmation остаётся обязательной задачей.
- Invitations и совместный доступ пока не готовы.
- Production пока разворачивается из feature-ветки; после релиза источником истины должен стать `main`.

## Роли

### ChatGPT / coding role

- архитектура;
- продуктовый код;
- миграции и тесты;
- ADR и документация;
- формирование точного runbook.

### VPS-агент

- backup;
- pull конкретного HEAD;
- build/migrate/deploy;
- Apache, systemd, Certbot и environment;
- smoke-тесты, логи и rollback;
- не принимает архитектурных решений и не пишет продуктовый код.

## Stop conditions

Немедленно остановить релиз при:

- расхождении ожидаемого HEAD;
- неуспешной миграции;
- признаках cross-user leak;
- `54001`, `42501`, `permission denied`, traceback или 5xx в ключевых сценариях;
- несовпадении Google redirect URI;
- выводе секретов в журнал или отчёт.
