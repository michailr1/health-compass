# Health Compass — consolidated code review

Дата: 2026-07-11  
Проверенный repository HEAD: `1a61f0307130e19fedeabd95218293d9a5075fe1`  
Production code at review time: `f3d7e8fedcdad5448abce5c74c1bdb698e5e82e6`  
Production Alembic: `0045 (head)`  
Статус: `ACCEPTED REVIEW / REMEDIATION REQUIRED`  
Итоговый verdict: `FIX BEFORE ROLLOUT`

## 1. Источники

Этот документ объединяет два независимых статических code review:

1. внутреннее архитектурно-техническое ревью ChatGPT по фактическому GitHub-коду;
2. независимое ревью Fable 5, сохранённое в `docs/reviews/FABLE-5-INDEPENDENT-CODE-REVIEW-2026-07-11.md`.

Совпавшие выводы считаются высокоуверенными. Уникальные findings сохраняются, если они подтверждены кодом или требуют отдельного runtime regression test.

## 2. Executive summary

Подтверждённых Critical findings, cross-user data leak, RLS bypass или self-escalation не обнаружено.

Сильные стороны текущей архитектуры:

- PostgreSQL RLS используется как реальная tenant boundary;
- tenant tables используют `ENABLE/FORCE ROW LEVEL SECURITY`;
- runtime role — `NOBYPASSRLS`;
- ограниченные helper functions принадлежат отдельной `NOLOGIN BYPASSRLS` роли;
- Google OIDC использует PKCE, state, nonce и строгую token verification;
- Clinical Context использует consent, provenance, audit, void и immutable history;
- seed import словаря versioned, reviewable и идемпотентен по concept business key.

Однако следующий rollout и добавление нового функционала должны быть остановлены до исправления блокирующих дефектов:

1. latent route collision и несовместимый response contract Clinical Context;
2. duplicate absorption, не синхронизированный с таблицами `0039/0045`;
3. неполная целостность `canonical_concept_id`;
4. Magic Link consume через state-changing GET;
5. неполный frontend quality gate.

## 3. Сводка findings

| ID | Severity | Статус | Краткое описание | Решение |
|---|---|---|---|---|
| CR-01 | High | подтверждено кодом | Duplicate Clinical Context summary/review routes с несовместимыми contracts | HC-015 Slice A |
| CR-02 | High | подтверждено кодом; HTTP regression required | Duplicate absorption не учитывает review/intake tables | HC-015 Slice B |
| CR-03 | High | подтверждено кодом | Magic Link token поглощается через GET | HC-015 Slice C |
| CR-04 | Medium | подтверждено обоими ревью | `canonical_concept_id` может ссылаться на concept чужого domain | HC-015 Slice D |
| CR-05 | Medium | подтверждено кодом | Старый `canonical_concept_id` может сохраниться после очистки/смены code | HC-015 Slice D |
| CR-06 | Medium | подтверждено обоими ревью | CI не запускает полный frontend lint и `tsc --noEmit` | HC-015 Slice E |
| CR-07 | Medium | подтверждено кодом | Alias seed upsert конфликтует не по полному business key | HC-015 Slice D |
| CR-08 | Medium | архитектурный/config risk | Безопасный account linking зависит от feature flag и production invariant не зафиксирован кодом | HC-015 Slice C |
| CR-09 | Medium | подтверждено кодом | Void operations не имеют optimistic concurrency token | HC-015 Slice F |
| CR-10 | Medium | подтверждено кодом | Race между confirmed-empty review и конкурентным добавлением записи | HC-015 Slice F |
| CR-11 | Medium | подтверждено кодом | Structured error с `request_id` теряется frontend API client | HC-015 Slice F |
| CR-12 | Medium | подтверждено кодом | Логи не являются безопасным structured JSON; query string требует redaction | HC-015 Slice C |
| CR-13 | Medium | подтверждено кодом | Migration downgrade boundary `0041` и полный cycle недостаточно проверены | HC-015 Slice E |
| CR-14 | Low | подтверждено обоими ревью | Dictionary search не использует `normalized_text` indexes эффективно | follow-up after rollout gate |
| CR-15 | Low | подтверждено кодом | Typeahead без debounce/AbortSignal создаёт лишние и stale requests | follow-up UI hardening |
| CR-16 | Low | подтверждено кодом | Dose нельзя надёжно очистить в edit flow | follow-up UI correctness |
| CR-17 | Low | подтверждено кодом | UTC date conversion может сдвинуть календарную дату | follow-up UI correctness |
| CR-18 | Low | подтверждено Fable | Logout выполняется через GET | HC-015 Slice C |
| CR-19 | Low | defense in depth | `users` имеет слишком широкий UPDATE grant | HC-015 Slice B/C security hardening |
| CR-20 | Low | техдолг | `cors_origins` объявлен, но middleware не подключён | clarify or remove config |
| CR-21 | Low | performance/architecture | OIDC discovery/JWKS могут загружаться на каждый callback | follow-up cache hardening |
| CR-22 | Low | документация | `CURRENT-STATE.md` и ближайший plan отстали от production | исправляется этим docs update |

## 4. Findings, блокирующие rollout

### CR-01 — Clinical Context route collision

Существуют legacy и current реализации одних и тех же summary/review routes. Их response shapes несовместимы, а корректность зависит от порядка `include_router`.

Acceptance:

- один канонический route owner;
- legacy route удалён или не регистрируется;
- HTTP test подтверждает `200` и валидный `ClinicalContextSummary`;
- router order больше не влияет на результат.

### CR-02 — duplicate absorption schema drift

Functions duplicate assessment/absorption не учитывают `profile_clinical_reviews` и `profile_intake_decisions`. Аккаунт с такими данными может ошибочно считаться пустым, после чего FK заблокирует удаление profile.

Acceptance:

- обе таблицы считаются meaningful activity;
- автоматическое absorption для такого аккаунта не запускается;
- API возвращает controlled conflict, не 500;
- PostgreSQL regression test покрывает оба типа строк.

### CR-03 — scanner-unsafe Magic Link consume

Обычная Email Magic Link выполняет meaningful state change по GET с token в URL. Mail scanner, preview service или security gateway может открыть ссылку раньше пользователя и поглотить одноразовый token.

Acceptance:

- GET только показывает interstitial/confirmation state;
- token consumption и session creation выполняются POST;
- token не попадает в application logs;
- replay, expiry и browser flow покрыты tests;
- существующие user-enumeration и rate-limit свойства сохраняются.

### CR-04/CR-05 — canonical concept integrity

Database проверяет существование concept, но не всегда его domain и не гарантирует очистку stale mapping при изменении source code fields.

Acceptance:

- condition/allergy/medication/supplement принимают только concept своего domain;
- очистка или смена `code`/`code_system` детерминированно обновляет либо очищает `canonical_concept_id`;
- invalid combinations отклоняются на DB boundary;
- migration имеет upgrade/downgrade и negative tests.

### CR-06 — неполный frontend quality gate

Vite/SWC build не заменяет TypeScript compiler check. CI lint ограничен ручным списком файлов.

Acceptance:

- full-source ESLint;
- `tsc -p tsconfig.app.json --noEmit`;
- build и frontend tests остаются обязательными;
- новый deliberately invalid test fixture или documented verification подтверждает, что gate ловит ошибки вне старого списка.

## 5. Обязательные follow-up findings в том же remediation cycle

### Auth и logging

- logout переводится на POST;
- production account-linking invariant становится fail-safe и проверяемым на startup/deploy;
- query strings, tokens и medical values не попадают в logs;
- logging output становится корректным structured JSON либо безопасным plain format с request ID.

### Clinical concurrency

- void получает `expected_updated_at` или эквивалентную conditional update семантику;
- confirmed-empty transition атомарно проверяет отсутствие entries;
- conflicts возвращают стабильный 409 contract.

### API/frontend contract

Frontend должен понимать оба разрешённых error envelope либо backend должен иметь единый canonical envelope. `request_id` должен отображаться пользователю в support-friendly error state без раскрытия внутренних деталей.

### Migration safety

- добавить full `upgrade head → downgrade base → upgrade head` в отдельном PostgreSQL CI job;
- отдельно проверить границу миграции с non-reversible privilege changes;
- запрещено оставлять `downgrade(): pass`, если revision marker становится ложным отражением DB state.

## 6. Не подтверждённые уязвимости

Следующие проблемы не были обнаружены:

- cross-user чтение/изменение medical data;
- bypass `FORCE RLS` runtime role;
- PUBLIC execution sensitive definer functions;
- self-grant owner чужого profile;
- self-add в чужой workspace;
- удаление последней identity;
- автоматическое превращение free text в confirmed canonical fact через штатный UI.

Это не отменяет обязательных regression tests после каждого schema/auth change.

## 7. Решение по rollout

До завершения HC-015:

- не добавлять новые product features;
- не повышать Alembic head новыми параллельными feature migrations;
- не выполнять production rollout code changes;
- разрешены документация, локальные tests и отдельная remediation branch.

После завершения HC-015 необходимы:

1. green backend/frontend/PostgreSQL CI;
2. independent diff review;
3. controlled backup-first rollout;
4. auth, duplicate-resolution и Clinical Context smoke tests;
5. фиксация production HEAD/Alembic и обновление history/current state.

## 8. Связанные документы

- `docs/reviews/FABLE-5-INDEPENDENT-CODE-REVIEW-2026-07-11.md`;
- `docs/reviews/FABLE-RECOMMENDATIONS.md`;
- `docs/implementation/HC-015-CODE-REVIEW-REMEDIATION.md`;
- `docs/SECURITY-INVARIANTS.md`;
- `docs/CURRENT-STATE.md`;
- `docs/DEVELOPMENT-HISTORY.md`.
