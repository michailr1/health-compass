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
4. При расхождении старого источника и фактической реализации отклонение фиксируется в `DEVELOPMENT-HISTORY.md` или ADR.
5. Секреты, персональные медицинские данные и токены не сохраняются в этом реестре.
