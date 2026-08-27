# Coding Prompt — HC-019 Finalization and Post-Merge Sequencing

## Context

Repository: `michailr1/health-compass`  
Base branch: `main`  
Дата постановки: 2026-08-27  
Основание: `docs/reviews/FABLE-5-CODE-REVISION-2026-08-27.md` (вердикт `HEALTHY / CONTINUE PLAN`)  
Принятые UX-решения владельца: `docs/PRODUCT-UX-BASELINE.md` §3 (owner review 2026-07-13)  
Спецификация задачи: `docs/implementation/HC-019-NAVIGATION-AND-EMPTY-STATE-UX.md`

Фактическое состояние на момент постановки:

```text
repository application baseline: c7dcae4da3860f6f73224f639be78424c6f3fa63
repository Alembic head: 0062 (единственный, линейный)
production application: fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75
production Alembic: 0058
DOCUMENT_UPLOAD_ENABLED=false
scanner/renderer/reconciler/OCR services: не запущены
```

HC-019 **уже реализован** в draft PR `#71`:

```text
branch: feat/hc-019-navigation-empty-state
head: e7aaedfa7167bf94dbd7e094201ada440d772ba1
CI: run 29243892485 — все три job зелёные на exact head
mergeable_state: clean
diff: 17 файлов, +913 / −451
```

Задача — **не переписывать HC-019 заново**, а довести существующий PR до merge
и подготовить следующий шаг.

## Safety constraints

- Не выполнять production deployment.
- Не включать `DOCUMENT_UPLOAD_ENABLED` и не запускать workers.
- Не менять backend-код, миграции и HC-017 security contract в рамках HC-019.
- Не создавать новых Alembic revision в этой задаче.
- Не делать force-push в `main`.
- Не добавлять secrets и не выводить значения переменных окружения.
- Если head PR `#71` изменится — CI обязан быть зелёным на новом exact head.

## Часть 1 (обязательная) — довести HC-019 до merge

1. Проверить актуальный `main` и убедиться, что PR `#71` не устарел; при
   необходимости rebase/merge `main` в ветку и дождаться зелёного CI на новом head.
2. Выполнить independent diff review PR `#71` против принятых решений
   `PRODUCT-UX-BASELINE.md` §3. Проверить по существу:
   - основная навигация ровно пять пунктов (`Главная · История · Добавить ·
     Ассистент · Ещё`) и на mobile, и на desktop;
   - `Документы` представлены пользователю как `Анализы`, пустое состояние
     объясняет что загружать, зачем и что будет дальше;
   - вкладки `Oura` в основной навигации нет; есть домен `Сон`, устройства
     подключаются внутри `Источников`; `/app/oura` остаётся refresh-совместимым;
   - `Подключить источник` не показывается, пока нет реальной интеграции;
     CTA пустого дашборда выполним;
   - в пользовательском тексте отсутствуют слова `карантин`, упоминания путей
     хранения и raw source labels;
   - demo/mock данные не выдаются за данные профиля.
3. Выполнить ручной browser smoke на локальной сборке (не на production):
   мобильная и десктопная навигация, активные состояния, переходы в `Ещё`,
   пустой дашборд, страница `Анализы` при выключенной загрузке, прямое
   обновление страницы по каждому маршруту, включая legacy `/app/oura`.
4. Снять draft, получить решение владельца о merge, выполнить merge.
5. Зафиксировать evidence: `docs/changes/2026-XX-XX-hc-019-merged.md`,
   обновить `docs/CURRENT-STATE.md` и `docs/PROJECT-PLAN.md`
   (`HC-019 MERGED / CI VERIFIED / NOT DEPLOYED`).

Статус `DEPLOYED` не ставить: HC-019 попадёт в production только вместе с
отдельным rollout-решением.

## Часть 2 (обязательная, отдельными PR) — процессная гигиена

1. Закрыть устаревшие PR с комментарием, без merge:
   - `#25` HC-013 session management — база предшествует HC-015, код
     нерелевантен; задача реализуется заново с актуального `main`;
   - `#17` docs frontend symlink — содержимое перекрыто актуальным runbook.
2. Подготовить отдельный small hardening PR (`REV-01`/`REV-02` из ревизии),
   одной новой линейной миграцией от фактического head:
   - удалить либо полностью отозвать права на неиспользуемые legacy-таблицы
     `0001`: `audit_events`, `processing_jobs`, `service_metadata`
     (у них нет RLS, но есть CRUD grant у app-роли; кодом они не используются —
     проверить это перед удалением и удалить также мёртвые SQLAlchemy-модели);
   - выровнять `search_path=''` для `app_issue_email_login_token` и
     `app_consume_email_login_token` из `0019`;
   - добавить негативные privilege-тесты и расширить проверки в
     `tests/test_migration_cycle.py`;
   - downgrade должен быть настоящим, без ложного revision state.

Этот PR не смешивать с HC-019.

## Часть 3 (решение владельца, не выполнять без прямого указания)

После merge HC-019 подготовить **предложение** по controlled backup-first
rollout HC-017 E3 (`0059–0062`), чтобы repository и production снова совпали:
план, backup, порядок `migration → backend → frontend → smoke`, критерии
отката. Само развёртывание выполняется только по отдельному явному решению
владельца и силами VPS-agent.

Далее по плану: операционная приёмка конвейера документов (`PROJECT-PLAN` §9),
Slice F Metric Dynamics, HC-018.

## Stop conditions

Остановиться и не завершать задачу, если:

- CI не зелёный на exact head, предлагаемом к merge;
- в основной навигации оказалось больше пяти пунктов;
- в пользовательском тексте остались `карантин`, storage paths или raw labels;
- любой CTA ведёт к действию, которое не может завершиться;
- HC-019 затронул backend, миграции или feature flags;
- появился второй Alembic head;
- обнаружено расхождение между документами и фактическим кодом.

## Финальный отчёт

Указать: ветку и final HEAD; какие PR закрыты/смержены; какие файлы и
документы изменены; результаты CI с номером run и exact SHA; результаты
ручного smoke; Alembic head до и после; статус
(`MERGED / CI VERIFIED / NOT DEPLOYED`); оставшиеся риски. Deployment status
указывать честно: production не изменялся.
