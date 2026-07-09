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
| Retrieval-grounded AI с обязательными evidence | PLANNED | PHASE-08 + `AI-PRODUCT-SAFETY.md` |
| Не допускать автоматических диагнозов | ACCEPTED | security invariant |
| Human и Pet должны быть визуально и архитектурно разделены | ACCEPTED | `PRODUCT-UX-BASELINE.md` |
| Human accent `#0E7490`, Pet accent `#7C5CBF` | ACCEPTED | design baseline |
| PetHeader обязателен на pet-экранах | ACCEPTED | future Pet contour |
| OCR-результат не публикуется без human confirmation | ACCEPTED | PHASE-03 baseline |
| AI-ответ без `EvidenceBlock` не показывается | ACCEPTED | AI safety baseline |
| Красный используется только для подтверждённых red flags | ACCEPTED | UX + AI safety baseline |
| Mobile navigation должна содержать не более 5 пунктов | ACCEPTED | MVP navigation baseline |
| High-fidelity mockups используются как UX reference, а не current state | ACCEPTED | Stage 3.5 baseline |
| Attention Inbox | PLANNED | candidate after core MVP flow |
| Global Search | PLANNED | after document/metric indexing |
| Bulk upload | PLANNED | document ingestion queue |
| Autosave OCR draft | PLANNED | OCR review flow |
| Data freshness and sync indicators | PLANNED | PHASE-04/05 |
| Notification center без медицинских значений в product analytics | PLANNED | privacy-safe notifications |
| Session management and revoke | PLANNED | Settings |
| Offline Emergency Card | DEFERRED | post-MVP |
| Caregiver mode and profile transfer | DEFERRED | PHASE-06/09 |
| Первый MVP vertical slice: login → upload → OCR → labs → chart → AI evidence → doctor report | ACCEPTED | `PRODUCT-UX-BASELINE.md` |
| Не делать большую блокирующую health-анкету перед первым анализом | ACCEPTED | PHASE-02.5 progressive intake |
| Собирать health context прогрессивно и по необходимости | ACCEPTED | `PROGRESSIVE-HEALTH-INTAKE.md` |
| Сохранить активацию ≤ 5 минут и пустой dashboard с основным CTA | ACCEPTED | minimal onboarding baseline |
| Добавить отдельный экран Health Profile | PLANNED | `/p/:profileId/health-profile` |
| Добавить contextual intake prompt в момент интерпретации | PLANNED | `IntakePromptCard` |
| Импортировать состояния/аллергии/лекарства из OCR только с подтверждением | ACCEPTED | PHASE-03 invariant |
| Использовать provenance manual/document/device/import | ACCEPTED | data contract requirement |
| Показывать нейтральную полноту без тревожного красного | ACCEPTED | contextual readiness |
| Intake не должен превращаться в самодиагностику | ACCEPTED | AI/product safety invariant |
| Внешний LLM получает intake context только по согласию | ACCEPTED | consent requirement |
| Для MVP разделить пол и гендер | REJECTED | владелец принял одно поле «Пол»; усложнение только при доказанном клиническом сценарии |
| Для MVP использовать одно поле `sex` | ACCEPTED | `male`, `female`, `not_specified`; поле опционально |
| Включить этническую принадлежность в обычный intake | REJECTED | только будущий конкретный валидированный алгоритм; не входит в completeness |
| Хранить исходные Fable artifacts только в чате проекта | REJECTED | исходники должны быть в GitHub reference archive |

## Правило обработки новых ревью

После каждого нового ревью:

1. Каждое замечание получает строку в этом реестре.
2. Для принятого замечания создаётся задача, ADR или commit.
3. Статус `VERIFIED` возможен только после теста или production-проверки.
4. `REJECTED` требует письменного обоснования.
5. Изменения плана переносятся в `docs/PROJECT-PLAN.md`.
6. Product/UX-рекомендации переносятся в `docs/PRODUCT-UX-BASELINE.md`.
7. Intake-рекомендации переносятся в `docs/PROGRESSIVE-HEALTH-INTAKE.md`.
8. AI safety-рекомендации переносятся в `docs/AI-PRODUCT-SAFETY.md` и при необходимости в `SECURITY-INVARIANTS.md`.
