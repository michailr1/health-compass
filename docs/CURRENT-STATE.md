# Health Compass — текущее состояние

Дата: 2026-07-09  
Основная ветка: `main`  
Production URL: `https://health.funti.cc`  
Старый URL: `https://funti.cc/health` → 301 на production-поддомен  
Развёрнутый commit: `77453af7c5cb6aae77ff4164069131737981f208`  
Alembic revision: `0022 (head)`

## Что работает

- FastAPI backend и React/Vite frontend.
- PostgreSQL + Alembic.
- Прямой Google OAuth 2.0 / OIDC.
- Email Magic Links через Brevo.
- Friendly page для использованной или просроченной magic link.
- Локальные PostgreSQL sessions и logout с отзывом сессии.
- Собственные users, identities, workspaces, profiles и permissions.
- FORCE ROW LEVEL SECURITY и tenant isolation.
- Production-поддомен `health.funti.cc` через HTTPS и отдельный Apache VirtualHost.
- Progressive Health Intake, Slice 1 — Basic Health Profile.

## Auth MVP

Auth MVP завершён и принят.

Подтверждено:

- Google login: PASS;
- Email Magic Link: PASS;
- logout и повторный вход: PASS;
- повторное использование magic link отклоняется: PASS;
- friendly invalid-link page: PASS;
- tenant isolation между двумя пользователями: PASS;
- пользователь A не читает dashboard/profile пользователя B;
- пользователь B не читает dashboard/profile пользователя A;
- чужие ресурсы через API возвращают `404`.

Production release auth MVP: `v0.1.0-auth-mvp`.

## PHASE-02.5 Slice 1 — Basic Health Profile

Реализовано и развёрнуто:

- экран `/app/profile`;
- имя профиля;
- дата рождения;
- поле `sex` со значениями `male`, `female`, `not_specified`;
- рост в сантиметрах;
- история веса через `body_measurements`;
- consent gate для медицинских данных;
- contextual readiness без health score;
- provenance;
- append-only audit;
- soft validation необычных значений;
- аннулирование ошибочного измерения без физического удаления;
- RLS и cross-user negative tests;
- регресс-тест SQLSTATE `54001`;
- автоматическое определение IANA timezone браузером;
- ручная корректировка timezone через ненавязчивую настройку;
- собственный favicon и актуальные метаданные Health Compass.

Часовой пояс нужен для корректного отнесения сна, тренировок, измерений и импортированных событий к локальным суткам. Он не является обязательным ручным полем основной формы.

## Последний production deployment

Подтверждено на `funti.cc` (`172.245.108.154`):

- HEAD `77453af7c5cb6aae77ff4164069131737981f208`;
- Alembic `0022 (head)`;
- backend service active;
- frontend release переключён через `/opt/health-compass/current-subdomain`;
- `/api/health` → 200;
- `/` → 200;
- `/app/profile` → 200;
- Google start endpoint → 307 на `accounts.google.com`;
- favicon и title обновлены;
- timezone UI работает;
- свежие логи без ERROR, CRITICAL и Traceback.

Backup перед deployment Slice 1:

```text
/opt/health-compass/backups/health_compass_20260709T122531Z.sql.gz
```

## Тесты Slice 1

Перед merge и deployment подтверждены:

- backend compile;
- Ruff;
- backend unit tests;
- frontend lint;
- frontend tests;
- production frontend build;
- PostgreSQL migration cycle `0021 → 0022 → 0021 → 0022`;
- FORCE RLS scan;
- cross-user matrix owner/edit/view/analyze/outsider;
- отсутствие PUBLIC EXECUTE на definer helpers.

Production DB для автоматических тестов не используется.

## Текущая разработка

Начат PHASE-02.5 Slice 2 — Clinical Context.

Рабочая ветка:

```text
feat/clinical-context-slice-2
```

Спецификация:

```text
docs/CLINICAL-CONTEXT-SLICE-2.md
```

План Slice 2:

- хронические состояния;
- аллергии и непереносимости;
- лекарства;
- витамины, минералы и БАДы;
- дозировка, единица, частота, даты и active/inactive;
- provenance и confirmation;
- audit;
- FORCE RLS;
- migration `0023`;
- API, UI и cross-user tests.

## Известные ограничения

- Реальные загрузки документов и OCR ещё не реализованы.
- Лабораторные показатели и их динамика ещё не реализованы.
- Интеграции Oura и других wearable-источников ещё не реализованы.
- Invitations и совместный доступ пока не готовы как законченный пользовательский flow.
- Contextual Intake Slice 3 ещё не реализован.
- AI-объяснения и doctor report пока не реализованы.

## Google Cloud Console

Действующий callback:

```text
https://health.funti.cc/api/auth/callback
```

Старый callback можно удалить вручную после дополнительной проверки:

```text
https://funti.cc/health/api/auth/callback
```

## Роли

### ChatGPT / coding role

- архитектура;
- data model и API contracts;
- продуктовый код;
- миграции, RLS и тесты;
- frontend;
- документация;
- точные задачи VPS-агенту.

### VPS-агент

- подключение только к `funti.cc` (`172.245.108.154`);
- backup, git pull конкретного HEAD, build, migrations, Apache, systemd, smoke tests и rollback;
- не принимает архитектурных решений;
- не пишет продуктовый код без отдельной точной задачи;
- не использует production DB для тестов;
- не выводит секреты.

## Stop conditions

Остановить релиз при:

- подключении не к `funti.cc`;
- несовпадении ожидаемого HEAD;
- грязном git worktree;
- неуспешном backup;
- неуспешной миграции;
- признаках cross-user leak;
- 5xx, `54001`, `42501`, `permission denied` или Traceback;
- выводе секретов в отчёт.
