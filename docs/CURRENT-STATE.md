# Health Compass — текущее состояние

Дата: 2026-07-10  
Основная ветка: `main`  
Repository HEAD после HC-012b: `ccc033127b6f9755cc7ea16f2cc2893a8bce2e7a`  
Production URL: `https://health.funti.cc`  
Production deployment HC-012b: не выполнен

## Что уже работает в production

- FastAPI backend и React/Vite frontend;
- PostgreSQL + Alembic;
- прямой Google OAuth 2.0 / OIDC;
- Email Magic Links через Brevo;
- локальные PostgreSQL sessions и logout;
- users, identities, workspaces, profiles и permissions;
- FORCE ROW LEVEL SECURITY и tenant isolation;
- Basic Health Profile Slice 1;
- consent gate для медицинских данных;
- история веса, provenance, append-only audit и contextual readiness;
- автоматическое определение IANA timezone с ручной корректировкой;
- безопасный account linking и duplicate-resolution foundation из HC-025/026/027.

Точный production HEAD и Alembic revision должны быть повторно зафиксированы VPS-агентом перед следующим rollout. Merge в `main` сам по себе production не изменил.

## Auth и identity

Auth MVP завершён и принят.

Подтверждённые инварианты:

- Google login и Email Magic Link ведут через собственный backend;
- logout отзывает локальную сессию;
- повторное использование magic link отклоняется;
- cross-user API возвращает `404`;
- совпадение verified email само по себе не объединяет аккаунты;
- новые дубли не создаются молча;
- существующие дубли разбираются через контролируемый HC-026 flow;
- TOTP HC-028 остаётся optional и не блокирует дальнейшую продуктовую работу.

## HC-012b Clinical Context

Статус кода: `MERGED TO MAIN / NOT DEPLOYED`.

Реализовано:

- conditions;
- allergies and intolerances;
- medications;
- supplements;
- clinical safety flags;
- явное различие «не заполнено» и «подтверждено отсутствие»;
- summary endpoint;
- list/create/update/void API;
- optimistic concurrency;
- owner/edit write;
- view/analyze read-only;
- outsider invisible;
- consent проверяется у владельца профиля;
- append-only audit;
- void вместо физического DELETE;
- voided-записи неизменяемы;
- app-role может создавать только `manual + confirmed` записи;
- `document + needs_review` зарезервирован для будущего OCR/import flow;
- HC-026 duplicate assessment учитывает любую Clinical Context history;
- nutrition safety flag `nutrition_calorie_feedback_suppressed` подготовлен для будущего HC-032;
- mobile-friendly UI встроен в `/app/profile`.

Миграции HC-012b:

```text
0037 — Clinical Context schema and RLS
0038 — HC-026 duplicate activity integration
0039 — explicit clinical review state
0040 — write hardening and immutable voided rows
```

Финальный PR: `#13`  
Merge commit: `ccc033127b6f9755cc7ea16f2cc2893a8bce2e7a`

## Проверки HC-012b

Финальный CI run `#205` завершён успешно:

- backend compile;
- Ruff;
- backend unit tests;
- frontend lint;
- frontend tests;
- frontend build;
- PostgreSQL migration cycle;
- FORCE RLS assertions;
- owner/edit/view/analyze/outsider matrix;
- no-DELETE assertions;
- warm-data `54001` regression;
- HC-026 regression;
- provenance spoofing rejection;
- immutable voided-row regression;
- explicit reviewed-empty RLS test.

Production DB в автоматических тестах не использовалась.

## Nutrition Photo MVP

Утверждён как PHASE-05.5 после Labs core.

Канонический документ:

```text
docs/NUTRITION-PHOTO-MVP.md
```

Принятые инварианты:

- `capture/raw → machine analysis → human confirmation → normalized fact`;
- AI-результат не является фактом без подтверждения;
- диапазон калорий вместо ложной точности;
- обязательные provenance и `ai_runs`;
- consent `external_llm`;
- единый AI gateway;
- wellbeing stop-list;
- nutrition-таблицы не входят в HC-012b.

## Следующий этап

Ближайший операционный шаг:

```text
controlled production rollout HC-012b
```

Runbook:

```text
docs/HC-012B-ROLLOUT.md
```

После принятого rollout и smoke tests:

1. зафиксировать production HEAD и Alembic `0040`;
2. обновить deployment history;
3. провести ручную проверку Clinical Context UI на мобильном устройстве;
4. устранить обнаруженные UX-дефекты отдельным PR;
5. вернуться к PHASE-03/04 document upload and OCR review foundation;
6. затем реализовать Labs core;
7. после Labs core перейти к PHASE-05.5 Nutrition Photo MVP.

## Известные ограничения

- HC-012b ещё не развёрнут в production;
- OCR/import из документов не реализован;
- реальные загрузки документов ещё не реализованы;
- лабораторные показатели и их динамика ещё не реализованы;
- Oura и другие wearable-интеграции ещё не реализованы;
- Invitations и совместный доступ не завершены как пользовательский flow;
- AI-объяснения и doctor report не реализованы;
- clinical safety flag не создаётся автоматически из свободного текста;
- система не диагностирует заболевания и не рассчитывает дозы.

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

- подключение только к production-хосту Health Compass;
- backup;
- фиксация HEAD/Alembic before;
- получение конкретного commit;
- build, migrations, systemd и release symlink;
- smoke tests и rollback;
- не принимает архитектурных решений;
- не использует production DB для автоматических тестов;
- не выводит секреты.

## Stop conditions

Остановить rollout при:

- подключении не к production-хосту;
- несовпадении ожидаемого HEAD;
- грязном git worktree;
- неуспешном backup;
- неуспешной миграции;
- признаках cross-user leak;
- `5xx`, `54001`, `42501`, `permission denied` или Traceback;
- выводе секретов в отчёт.
