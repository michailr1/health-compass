# HC-019 — Navigation and Empty-State UX Revision

Status: `DEFINED / NOT IMPLEMENTED / NOT DEPLOYED`  
Decision date: `2026-07-13`  
Scheduling: after HC-017 E3; do not mix with the E3 database/security contract.

## 1. Goal

Replace implementation-shaped navigation and developer-facing document copy with a user-task-oriented structure that explains what the product can actually do now.

HC-019 is a frontend/product-language slice. It must not weaken HC-017 security controls or imply that the disabled document-processing pipeline is operational.

## 2. Mobile navigation

The bottom navigation must contain no more than five primary items:

```text
Главная
История
Добавить
Ассистент
Ещё
```

Current top-level implementation/demo entries must not remain as separate bottom tabs:

```text
Документы
Oura
Генетика
План
Источники
```

Placement rules:

- health-data domains appear in task/domain terms, not vendor names;
- integrations and device management live under `Ещё` → `Источники`/integration settings;
- demo or unavailable areas do not occupy primary navigation;
- desktop navigation follows the same information architecture even when rendered differently.

## 3. Documents becomes Analyses

The user-facing section label is:

```text
Анализы
```

Do not use `Документы` as the primary navigation label for the Lab-results workflow.

Exact empty-state explanation:

> Загрузите PDF или фото результатов анализов. Мы распознаем значения — вы проверите и подтвердите их, после этого они появятся в показателях, динамике и отчётах. Ничего не станет медицинским фактом без вашего подтверждения.

When upload is disabled, the same screen must clearly state that loading is temporarily unavailable. It must not show an enabled-looking upload CTA that cannot complete.

## 4. Upload copy

User-facing secure-storage explanation:

> Файл хранится в зашифрованном виде и виден только вам. После проверки файла мы распознаем текст — вы сможете просмотреть и подтвердить результат.

Required button label when upload is enabled:

```text
Загрузить
```

Forbidden user-facing wording:

- `Загрузить в карантин`;
- explanations that the original file name is not used as a storage path;
- path traversal, opaque object keys or internal storage identifiers;
- `карантин` as a product status label.

Allowed status wording:

```text
Идёт проверка файла
```

Technical terms and guarantees remain in security and implementation documentation.

## 5. Sleep domain and integrations

The top-level data domain is:

```text
Сон
```

`Oura` must not be a top-level navigation domain. It is one possible source inside integration settings.

Future sources, including Apple Health and Health Connect subject to their own ADR and implementation, must plug into the same source-management area rather than create vendor-specific top-level tabs.

## 6. Empty dashboard CTA

Hide `Подключить источник` until at least one real, usable integration exists in the deployed product.

Primary empty-dashboard CTA must always be executable in the current environment:

1. `Заполнить профиль здоровья`; or
2. `Загрузить анализы` only when upload is actually enabled.

Do not advertise unavailable integrations or disabled workflows as primary actions.

## 7. States and routes

HC-019 may preserve existing internal route compatibility, but user-visible labels and navigation must follow this specification.

Required states:

- no health data and upload disabled;
- no health data and upload enabled;
- analyses exist;
- no integrations available;
- one or more integrations available;
- mobile bottom navigation;
- desktop navigation;
- direct refresh of existing application routes.

## 8. Accessibility and responsive requirements

- active navigation item is visually and programmatically identifiable;
- touch targets remain usable on mobile;
- labels are not icon-only without accessible names;
- primary CTA is visible without horizontal scrolling;
- empty-state copy remains readable at narrow widths;
- no layout shift or hidden route access caused by reducing bottom tabs.

## 9. Acceptance criteria

- mobile bottom navigation has at most five items and matches the accepted baseline;
- `Документы` is replaced by `Анализы` in the user-facing workflow;
- exact analysis empty-state copy is present;
- exact secure-storage copy is present where relevant;
- `карантин` and storage-path explanations are absent from UI;
- `Oura` is not a top-level tab;
- `Сон` represents the data domain;
- `Подключить источник` is hidden when no real integration exists;
- primary empty-state CTA is executable;
- existing routes remain refresh-safe;
- frontend lint, typecheck, tests and build pass;
- manual mobile and desktop smoke pass.

## 10. Non-goals

HC-019 does not:

- enable document upload;
- provision scanner/OCR workers;
- implement Oura, Apple Health or Health Connect ingestion;
- implement metric dynamics;
- change PostgreSQL or RLS;
- change HC-017 E3 correction/void/erasure semantics.
