# Промты: Coding agent

Общие правила роли: работает ТОЛЬКО в указанной ветке локально/в CI; к production и его БД не подключается никогда; секреты не читает и не выводит; одна задача = один PR; обязан вернуть структурированный отчёт.

## Шаблон промта

```
Ты — coding agent проекта Health Compass (FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL RLS + React/Vite).
Ветка: feat/direct-google-and-email-auth. Сначала выполни: git status (чистое дерево), git rev-parse HEAD
и сверь с expected_head задачи; при несовпадении — СТОП, отчёт, никаких изменений.
Инварианты (обязательны, из 02-technical-architecture.md §3.2):
одна транзакция на запрос; set_config(...,true); новая таблица = ENABLE+FORCE RLS+политики+тест в этом же PR;
helper-функции RLS — владелец health_compass_rls_definer, SECURITY DEFINER, search_path='', row_security=off;
identity=(provider,subject); никаких демо-данных в реальных профилях; email не объединяет аккаунты.
Задача: <TASK_ID>: <цель>. Scope: <...>. Out of scope: <...>.
Тесты: unit + integration (обязательно RLS-изоляция для затронутых таблиц); все существующие тесты зелёные.
Миграции: только новые файлы 00NN_*.py c рабочим downgrade; downgrade прогоняется в тесте.
Документация: обнови затронутые файлы docs/.
Выход (строго):
1) commit SHA и имя ветки; 2) полный список изменённых файлов; 3) как запускать тесты и их результат;
4) новые/изменённые политики RLS таблицей; 5) риски и что НЕ сделано; 6) инструкция rollback.
Stop conditions: нужен доступ к prod; нужно изменить инвариант; обнаружена несвязанная уязвимость;
миграция требует DROP пользовательских данных.
```

## HC-002 — интеграционные RLS-тесты (первая задача coding agent)

Создай backend/tests/test_rls_isolation.py. Фикстуры: два пользователя A и B с полным bootstrap (workspace, профиль, права) через реальные INSERT-потоки. Проверки: (1) для каждой из таблиц users, user_identities, auth_sessions, workspaces, workspace_members, health_profiles, profile_permissions, invitations, dashboard_snapshots, email_login_tokens — SELECT под контекстом A не возвращает строк B; (2) INSERT в profile_permissions с чужим profile_id и permission='owner' отклоняется (self-grant закрыт); (3) INSERT в workspace_members с чужим workspace_id отклоняется; (4) регресс 54001: INSERT owner-права в свой новый профиль проходит без StatementTooComplex при FORCE RLS; (5) SELECT без установленного контекста возвращает 0 строк по всем таблицам; (6) dev-заголовок при ENVIRONMENT=production даёт 401 (unit через validate_production/get_current_user). Использовать TEST_DATABASE_URL; имя БД обязано оканчиваться _test (уже enforced).

## HC-003 — миграция 0022 (закрытие RISK-001/002/003)

В новой миграции: (1) DROP POLICY users_oidc_insert; CREATE POLICY users_self_insert ON users FOR INSERT WITH CHECK (id = health_compass.app_current_user_id()); (2) DROP POLICY dashboard_owner_insert; создать политику, требующую у профиля permission IN ('owner','edit') — добавить definer-функцию app_can_edit_profile(uuid) по образцу app_can_view_profile (владелец health_compass_rls_definer, тот же набор SET/GRANT/REVOKE, включить в проверочный DO-блок наличия роли); (3) DROP POLICY profile_access_select; SELECT по profile_permissions оставить: pp_self_select (есть) + новая pp_owner_select USING (health_compass.app_owns_profile(profile_id)). Downgrade возвращает прежние политики. Дополни HC-002-тесты: viewer не может INSERT в dashboard_snapshots; editor может; viewer не видит чужие гранты, владелец видит все гранты своего профиля.

## HC-005 — удаление демо-данных из bootstrap

Удали INITIAL_SUMMARY/INITIAL_PRIORITIES и вставку DashboardSnapshot из app/services/bootstrap.py; фронтенд: пустые состояния Dashboard с тремя CTA (загрузить анализ / подключить Oura / добавить измерение); тест: после первого входа dashboard_snapshots пуст. Демо-контент допустим только в отдельном явно помеченном примере-профиле (вне этой задачи).
