# Health Compass — реестр источников

Этот файл связывает исходные материалы, внешние ревью и живую документацию репозитория.

## Стратегические материалы

| Источник | Назначение | Каноническое отражение |
|---|---|---|
| `01-health-compass-master-plan.pdf` | полный мастер-план продукта | `docs/PROJECT-PLAN.md` |
| `03-implementation-roadmap.xlsx` | этапы, зависимости и сроки | `docs/PROJECT-PLAN.md` |
| `04-health-compass-vision-and-roadmap.pptx` | продуктовая концепция и roadmap | `docs/PROJECT-PLAN.md` |
| `14-unit-economics.xlsx` | экономика и сценарии монетизации | будущий product/economics plan |
| `START-HERE.md` | навигация по комплекту | этот реестр и README |
| `health-compass-master-plan.zip` | полный архив исходных документов | reference archive |

## Fable Stage 3 — Product, UX and AI

| Источник | Назначение | Каноническое отражение |
|---|---|---|
| `03-product-specification.md` / PDF | продуктовая спецификация | `PROJECT-PLAN.md`, `PRODUCT-UX-BASELINE.md` |
| `03-information-architecture.md` | информационная архитектура | `PRODUCT-UX-BASELINE.md` |
| `03-user-flows.md` | ключевые пользовательские сценарии | `PRODUCT-UX-BASELINE.md` |
| `03-design-system.md` | цвета, типографика, компоненты и accessibility | `PRODUCT-UX-BASELINE.md` |
| `03-ai-product-and-safety.md` | AI-функции, safety и transparency | `AI-PRODUCT-SAFETY.md` |
| `03-human-health-modules.xlsx` | карта Human Health модулей | `PROJECT-PLAN.md`, product backlog |
| `03-pet-health-modules.xlsx` | карта Pet Health модулей | `PROJECT-PLAN.md`, future Pet contour |
| `03-wireframes.pdf` | ранние wireframes | reference design archive |

## Fable Stage 3.5 — UI Blueprint

| Источник | Назначение | Каноническое отражение |
|---|---|---|
| `03_5-screen-map.md` | карта экранов и состояний | `PRODUCT-UX-BASELINE.md` |
| `03.5-action-registry.xlsx` | кнопки, меню, действия и API dependencies | implementation backlog |
| `03_5-navigation-and-menus.md` | desktop/mobile navigation | `PRODUCT-UX-BASELINE.md` |
| `03_5-component-map.md` | component baseline | `PRODUCT-UX-BASELINE.md` |
| `03.5-high-fidelity-mockups.pdf` | high-fidelity UX reference | reference design archive |
| `03_5-frontend-next-steps.md` | ближайший frontend roadmap | `PRODUCT-UX-BASELINE.md`, `PROJECT-PLAN.md` |

## Fable Stage 2.5 — Progressive Health Intake

| Источник | Назначение | Каноническое отражение |
|---|---|---|
| `02.5-health-intake-spec.md` | спецификация прогрессивного intake и UX-интеграции | `docs/PROGRESSIVE-HEALTH-INTAKE.md`, `PROJECT-PLAN.md` |
| `02.5-intake-fields.xlsx` | матрица полей IN-01…IN-16, privacy, provenance и точки сбора | `docs/PROGRESSIVE-HEALTH-INTAKE.md`, будущие API/data contracts |
| `02.5-intake-wireframes.pdf` | Health Profile, contextual prompt, OCR import и dashboard hint | `PRODUCT-UX-BASELINE.md`, reference design archive |

Принятые отклонения от исходных материалов:

- PHASE-02.5 не является блокирующей анкетой;
- для MVP используется одно поле «Пол» (`sex`), без разделения пола и гендера;
- этническая принадлежность не входит в обычный MVP intake и запрашивается только будущим конкретным валидированным правилом;
- основной UX полноты — contextual readiness, а не давление заполнить все поля;
- исходные XLSX/PDF остаются неизменяемыми reference artifacts, а принятые решения отражаются в Markdown baseline.

## Внешние ревью

| Источник | Темы | Каноническое отражение |
|---|---|---|
| `ревью Fable5.txt` | архитектура, продукт, безопасность, эксплуатация | plan, ADR, runbook, recommendation register |
| `2-Ревью-Fable5-Postgre-рекурсия.txt` | RLS recursion, FORCE RLS, escalation paths | `SECURITY-INVARIANTS.md`, migrations `0020–0021` |
| Fable 5 independent code review, 2026-07-11 | актуальный backend/frontend, RLS, auth, Clinical Context, CI | `docs/reviews/FABLE-5-INDEPENDENT-CODE-REVIEW-2026-07-11.md` |
| ChatGPT independent code review, 2026-07-11 | актуальный код, миграции, contracts, security и operations | `docs/reviews/CODE-REVIEW-CONSOLIDATED-2026-07-11.md` |

## Принятые результаты ревью 2026-07-11

| Документ | Назначение |
|---|---|
| `docs/reviews/CODE-REVIEW-CONSOLIDATED-2026-07-11.md` | единый verdict и полный реестр findings |
| `docs/reviews/FABLE-5-INDEPENDENT-CODE-REVIEW-2026-07-11.md` | сохранённый независимый источник Fable 5 |
| `docs/implementation/HC-015-CODE-REVIEW-REMEDIATION.md` | план исправлений и implementation contract |
| `docs/implementation/HC-015-PRODUCTION-ROLLOUT.md` | backup-first rollout runbook |
| `docs/implementation/HC-015-PRODUCTION-EVIDENCE-2026-07-11.md` | подтверждённое automated production evidence |
| `docs/reviews/FABLE-RECOMMENDATIONS.md` | статусы принятых рекомендаций |

## HC-015 implementation and rollout evidence

| Источник | Назначение |
|---|---|
| PR `#39`, application commit `c87723d7b4d0e4d2db9f1e0df4e936fbfd543346` | реализация и merge HC-015 slices A–F |
| Alembic migrations `0046`–`0048` | duplicate-activity sync, dictionary domain integrity, users column grants |
| `docs/implementation/HC-015-PRODUCTION-EVIDENCE-2026-07-11.md` | backup, migration, build, health, log и automated verification evidence |
| `backend/tests/test_route_table.py`, `test_clinical_context_http.py` | route ownership и HTTP contract |
| `backend/tests/test_duplicate_activity_schema_sync_postgres.py` | duplicate-resolution regression |
| `backend/tests/test_magic_link_scanner_safety_http.py`, `test_logout_http.py`, `test_logging_redaction.py`, `test_config.py` | auth and logging regression |
| `backend/tests/test_clinical_dictionary_integrity_postgres.py`, `test_clinical_dictionary_seed_upsert_postgres.py` | clinical dictionary integrity |
| `backend/tests/test_migration_cycle.py`, `.github/workflows/ci.yml` | migration and CI gates |
| `backend/tests/test_users_update_privileges_postgres.py` | users privilege hardening |
| `src/lib/api.test.ts`, `src/lib/utils.test.ts`, `src/components/*.test.ts` | frontend contracts |

## Safari Magic Link regression evidence

| Источник | Назначение |
|---|---|
| commit `8c09c02fa007cd5e5945c5a93b4913ce63868e68` | production hotfix для Safari-safe Origin handling |
| owner manual confirmation | iPhone Safari Magic Link flow работает после hotfix |

## HC-016 implementation and acceptance evidence

| Источник | Назначение |
|---|---|
| PR `#44`, merge commit `69b56f12c25457321b49c7412479f5aa4f238b86` | owner-controlled permanent clinical record erasure |
| migration `0049` | restricted definer-based erasure, audit scrubbing and tombstone contract |
| PR `#45`, merge commit `b8e868825f378195975e2729f3f36c21a1afa2d0` | approved removal of backup-retention sentence from UI warning |
| `docs/implementation/HC-016-CLINICAL-RECORD-ERASURE.md` | product, privacy, API, DB and verification contract |
| `docs/implementation/HC-016-PRODUCTION-ACCEPTANCE-2026-07-12.md` | owner manual production acceptance and explicit evidence boundary |
| owner manual confirmation, 2026-07-12 | production UI and HC-016 flows work as intended |

## Фактические источники

- Git commits и Pull Requests;
- Alembic migrations;
- automated tests;
- production SQL checks;
- Apache/systemd/Certbot state;
- deployment and incident reports;
- explicit owner manual acceptance.

## Правила

1. Исходные PDF/XLSX/PPTX не редактируются как живой план.
2. Все принятые изменения переносятся в Markdown-документы репозитория.
3. Внешняя рекомендация не считается реализованной без commit/test/production evidence.
4. Product/UX baseline не считается current state, пока нет кода, API и тестов.
5. При расхождении старого источника и фактической реализации отклонение фиксируется в `DEVELOPMENT-HISTORY.md`, ADR или каноническом baseline.
6. Секреты, персональные медицинские данные и токены не сохраняются в этом реестре.
7. Исходные артефакты Fable должны храниться в GitHub reference archive; чат/проект не является единственным долговременным хранилищем.
8. Независимое ревью хранится отдельно от консолидированного решения; accepted findings получают implementation task и status.
9. Manual acceptance подтверждает пользовательский результат, но не заменяет отсутствующие operational metrics; такие metrics нельзя восстанавливать предположениями.
