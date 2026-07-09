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

| Источник | Темы | Отражение |
|---|---|---|
| `ревью Fable5.txt` | архитектура, продукт, безопасность, эксплуатация | plan, ADR, runbook, recommendation register |
| `2-Ревью-Fable5-Postgre-рекурсия.txt` | RLS recursion, FORCE RLS, escalation paths | `SECURITY-INVARIANTS.md`, migrations `0020–0021` |

## Фактические источники

- Git commits и Pull Requests;
- Alembic migrations;
- automated tests;
- production SQL checks;
- Apache/systemd/Certbot state;
- deployment and incident reports.

## Правила

1. Исходные PDF/XLSX/PPTX не редактируются как живой план.
2. Все принятые изменения переносятся в Markdown-документы репозитория.
3. Внешняя рекомендация не считается реализованной без commit/test/production evidence.
4. Product/UX baseline не считается current state, пока нет кода, API и тестов.
5. При расхождении старого источника и фактической реализации отклонение фиксируется в `DEVELOPMENT-HISTORY.md`, ADR или каноническом baseline.
6. Секреты, персональные медицинские данные и токены не сохраняются в этом реестре.
7. Исходные артефакты Fable должны храниться в GitHub reference archive; чат/проект не является единственным долговременным хранилищем.
