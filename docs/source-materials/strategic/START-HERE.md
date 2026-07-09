# START HERE — Health Compass Master Plan

Версия комплекта: 1.0 · Дата: 2026-07-08
Основано на: архив ветки `feat/direct-google-and-email-auth` (Alembic head 0021; Git HEAD в архиве отсутствовал — зафиксировать в этом файле при следующем ревью: `expected HEAD: ______`).

## Основной документ

`01-health-compass-master-plan.md` (и его PDF-версия `01-health-compass-master-plan.pdf`).

## Текущие блокеры (PHASE-01, делать до любого нового функционала)

1. **RISK-006** — bootstrap записывает каждому реальному пользователю фейковый медицинский dashboard («предполагаемый Factor V Leiden»). Удалить (HC-005).
2. **RISK-001** — политика `users_oidc_insert WITH CHECK (true)`; **RISK-002** — право `view` может писать dashboard_snapshots; **RISK-003** — viewer видит все гранты профиля. Миграция 0022 (HC-003).
3. **RISK-012** — нет интеграционных тестов изоляции RLS (HC-002).
4. Документация противоречит коду (C-1…C-4): docs утверждают «backend отсутствует» и рекомендуют Authentik (HC-004).
5. Верификация production не проводилась в рамках этого ревью — первым действием запустить HC-001 (только чтение + smoke).

Инцидент `StatementTooComplex` (54001) в ветке уже исправлен миграциями 0020/0021; решение подтверждено как корректное (разбор: `02-technical-architecture.md` §2).

## Первые действия

1. Владелец: прочитать 01 (резюме) и раздел блокеров.
2. VPS-агент: выполнить HC-001 по промту из `09-agent-prompts/vps-agent-prompts.md` (§HC-001).
3. Coding agent: HC-002 → HC-003 → HC-005 по промтам из `09-agent-prompts/coding-agent-prompts.md`.
4. Архитектор: HC-004 (документация) по `09-agent-prompts/architect-prompts.md`.
5. После зелёного PHASE-01 — идти по `03-implementation-roadmap.xlsx` (лист Roadmap) и `10-machine-readable-roadmap.yaml`.

## Порядок чтения

| Роль | Порядок |
|---|---|
| Владелец | START-HERE → 01 (PDF) → 12 → 13/14 (XLSX) → 04 (презентация) |
| ИИ-архитектор | START-HERE → 02 → 06 → 07 → 11-adr/ → 03 (XLSX) → 10 (YAML) |
| Coding agent | 09-agent-prompts/coding-agent-prompts.md → задача из 10 (YAML) → 02 §3.2 (инварианты) |
| VPS-агент | ТОЛЬКО 09-agent-prompts/vps-agent-prompts.md (архитектурные документы ему не передаются) |
| Reviewer | 09-agent-prompts/review-prompts.md → 07 → 08 (XLSX) |

## Состав комплекта

```
START-HERE.md                              — этот файл
01-health-compass-master-plan.md/.pdf      — генеральный план
02-technical-architecture.md               — архитектура + разбор RLS-инцидента + RISK-регистр
03-implementation-roadmap.xlsx             — roadmap (9 листов, задачи HC-001…)
04-health-compass-vision-and-roadmap.pptx  — презентация
05-product-and-ux-specification.md         — продукт/UX
05-portal-wireframes.pdf                   — 8 wireframe-экранов
06-data-model.md / .mmd / .pdf             — модель данных + ER-диаграмма
07-security-and-threat-model.md            — security model
08-war-games.xlsx                          — военные игры (WG-001…)
09-agent-prompts/                          — промты: architect / coding / vps / review / incident / release
10-machine-readable-roadmap.yaml           — машиночитаемый план
11-adr/                                    — ADR-001…ADR-020
12-product-strategy-and-monetization.md    — стратегия и монетизация
13-pricing-and-entitlements.xlsx           — тарифы и entitlements
14-unit-economics.xlsx                     — unit-экономика (редактируемые допущения)
```

## Продолжение работы с более слабым ИИ

1. Дай агенту ТОЛЬКО его файл промтов из `09-agent-prompts/` и одну задачу HC-xxx из YAML (раздел tasks), включая stop conditions.
2. Требуй структурированный отчёт по шаблону из промта; сверяй commit SHA и alembic head с YAML-полями `expected_*` и обновляй их после приёмки.
3. Агент не имеет права принимать архитектурные решения: всё, что не описано в задаче, — стоп и вопрос архитектору.
4. Одна задача = один PR = один деплой; статусы задач ведутся в листе Roadmap (колонка status) и в YAML.
