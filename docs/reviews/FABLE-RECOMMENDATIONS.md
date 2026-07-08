# Fable — реестр рекомендаций

Статусы: `ACCEPTED`, `VERIFIED`, `PLANNED`, `DEFERRED`, `REJECTED`, `SUPERSEDED`.

| Рекомендация | Статус | Реализация / решение |
|---|---|---|
| Отказаться от неявного owner bypass в RLS helper-функциях | VERIFIED | `0020`, `0021` |
| Выделить `health_compass_rls_definer NOLOGIN BYPASSRLS` | VERIFIED | production role + migrations |
| Использовать `search_path=''` и `row_security=off` | VERIFIED | функции проверены SQL-аудитом |
| Отозвать `PUBLIC EXECUTE` | VERIFIED | миграции и privilege checks |
| Закрыть self-grant owner на чужой profile | VERIFIED | policy + negative test |
| Закрыть self-add в чужой workspace | VERIFIED | policy + negative test |
| Добавить прямые self-select policies для RETURNING | VERIFIED | `0020` |
| Исправить identity lookup под FORCE RLS | VERIFIED | definer helper |
| Добавить users self-update policy | VERIFIED | `0020` |
| Устанавливать session hash context до AuthSession INSERT | VERIFIED | Google и email auth |
| Проверять RLS на «тёплых» данных | VERIFIED | интеграционный пакет, 22 PASS |
| Ввести инвариант-аудит владельцев policy helper-функций | PLANNED | автоматизировать в CI |
| Сделать scanner-safe magic links | PLANNED | landing page + POST confirmation |
| Реализовать invitations только вместе с RLS policies | DEFERRED | до PHASE-06 |
| Не увеличивать `max_stack_depth` как workaround | ACCEPTED | запрещено как решение рекурсии |
| Явно разделить роли coding и VPS agents | ACCEPTED | docs + runbook |
| Синхронизировать docs с фактическим кодом | IN PROGRESS | новый docs-контур |
| Маркировать demo health data и не смешивать с реальными | ACCEPTED | UI label; реальный импорт в PHASE-03/04 |
| Retrieval-grounded AI с обязательными evidence | PLANNED | PHASE-08 |
| Не допускать автоматических диагнозов | ACCEPTED | security invariant |

## Правило обработки новых ревью

После каждого нового ревью:

1. Каждое замечание получает строку в этом реестре.
2. Для принятого замечания создаётся задача, ADR или commit.
3. Статус `VERIFIED` возможен только после теста или production-проверки.
4. `REJECTED` требует письменного обоснования.
5. Изменения плана переносятся в `docs/PROJECT-PLAN.md`.
