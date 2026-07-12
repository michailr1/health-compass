# Health Compass — security invariants

Эти правила обязательны для всех изменений. Их нельзя ослаблять без отдельного ADR, threat review и негативных тестов.

## Identity и sessions

- Для MVP используются только direct Google OIDC и Email Magic Links.
- Authentik, Keycloak и внешний IAM не возвращаются без нового ADR.
- Google identity определяется парой `provider + subject`, а не email.
- Email Magic Link одноразовый, ограничен по времени и хранится только в виде hash.
- GET Magic Link не имеет права поглощать token или создавать session; meaningful consume выполняется только после явного user action через POST.
- Tokens, cookies, authorization headers и raw auth query strings не попадают в logs, analytics и error pages.
- Серверная сессия хранится в PostgreSQL; browser получает HttpOnly Secure cookie.
- Logout изменяет state только через POST и отзывает локальную session.
- User/session RLS context устанавливается внутри транзакции запроса.
- Verified email само по себе не объединяет аккаунты.
- Production account-linking protection является fail-safe invariant, а не необязательным feature toggle.
- Последнюю identity пользователя удалить нельзя.

## PostgreSQL и RLS

- Все таблицы с пользовательскими и медицинскими данными: `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`.
- Runtime role: `health_compass_app` с `NOBYPASSRLS`.
- Migrator role не используется приложением.
- Helper-функции, которым необходим обход RLS, принадлежат только `health_compass_rls_definer NOLOGIN BYPASSRLS`.
- Такие функции возвращают только ограниченные scalar/record contracts, используют статический SQL, `search_path=''` и `row_security=off`.
- `PUBLIC EXECUTE` на security-definer функции запрещён.
- Новая таблица не принимается без RLS policies и двухпользовательских негативных тестов.
- Запрещены политики, позволяющие пользователю самостоятельно выдать себе доступ к чужому profile/workspace.
- Bootstrap owner выполняется отдельными statements/flush; профиль и permission нельзя объединять в один statement без повторного анализа snapshot semantics.
- Column-level grants используются для identity-critical и system-managed полей; runtime role не получает широкий UPDATE без необходимости.
- Duplicate assessment обязан учитывать все profile-owned таблицы текущей схемы до destructive absorption.

## Tenant isolation tests

Минимальный обязательный набор:

- A видит свои workspace/profile/dashboard;
- A не видит данные B;
- A не может выдать себе owner на profile B;
- A не может добавить себя в workspace B;
- без user context SELECT возвращает 0 строк;
- повторный вход не создаёт дубликат user;
- INSERT с RETURNING проходит для profile, permission, snapshot и auth session;
- проверка проводится на «тёплых» данных, а не только при первом bootstrap;
- duplicate resolution с любыми meaningful profile rows не удаляет данные и не возвращает необработанный 500.

## Clinical data integrity

- `canonical_concept_id` соответствует domain конкретной clinical section.
- Изменение или очистка source `code`/`code_system` атомарно обновляет либо очищает canonical mapping.
- Derived canonical columns не должны напрямую изменяться клиентом без явного server contract.
- Review state `confirmed_none` нельзя сохранить, если в той же атомарной проверке существуют несовместимые записи.
- Void/update используют optimistic concurrency и возвращают controlled conflict для stale write.
- User-entered free text не переписывается молча каноническим понятием.
- Free-text fallback остаётся доступным при отсутствии dictionary match.

## Documents, OCR and Labs

- Загруженный документ считается недоверенным вводом до завершения structural validation и malware scan.
- Upload всегда проходит через quarantine; scanner failure действует fail closed.
- Ограничения размера, количества страниц, формата и ресурсов применяются на backend/worker, а не только во frontend.
- Filename, declared MIME и extension не считаются доказательством типа; проверяются magic bytes и структура.
- Raw document не хранится в PostgreSQL и не размещается в public web root.
- Storage key создаётся сервером и не содержит filename, email, profile name или medical values.
- Любой download/preview сначала проходит database authorization по `profile_id`.
- Роль `analyze` не получает raw document и OCR drafts; ей доступны только confirmed structured observations.
- Background worker использует отдельные credentials и не работает как migrator или `health_compass_app`.
- Worker не имеет права подтверждать clinical facts и не получает широкий доступ к profile tables.
- OCR output всегда имеет статус `needs_review` до explicit user confirmation.
- Low-confidence fields нельзя подтверждать автоматически или скрытым bulk action.
- Candidate edit/confirmation используют optimistic concurrency; stale confirmation не создаёт частичных facts.
- Reprocessing идемпотентен и не перезаписывает подтверждённые observations.
- Source text, units and reference ranges сохраняются; normalization не переписывает их молча.
- Несовместимые units не объединяются в один metric series без отдельного validated conversion contract.
- Patient mismatch не исправляется автоматическим поиском или silent profile reassignment.
- Document permanent erasure доступен только owner и охватывает raw, derived, OCR candidates и sole-provenance confirmed observations.
- После перехода в `deletion_pending` пользовательский доступ прекращается немедленно, а storage cleanup повторяется идемпотентно.
- Original filename, OCR text, patient identifiers, analytes, values, units, ranges и signed URLs запрещены в ordinary logs и metrics labels.
- External OCR/LLM получает документы только после отдельного provider review и explicit revocable consent.

## Confirmed Labs invariants

- Finalized OCR transcription остаётся источником, а не confirmed Lab observation.
- Lab observation создаётся только отдельной явной owner/editor confirmation transaction.
- Background worker, OCR parser, dictionary и AI не имеют права создавать confirmed observation.
- Draft Lab rows доступны только owner/edit; view/analyze не получают drafts и OCR source text.
- Analyze получает только active confirmed structured observations.
- `source_analyte_text`, `source_value_text`, `source_unit_text`, `source_reference_range_text` и source date/specimen text сохраняются отдельно от parsed/canonical fields.
- Parsed decimal/date/range и canonical concept не перезаписывают source wording.
- Silent unit conversion, silent canonical mapping и automatic reference-range interpretation запрещены.
- Unknown/mismatch patient decision блокирует confirmation; `not_present` требует отдельного explicit assignment acknowledgement.
- Confirmation валидирует current finalized OCR run, document version, patient-decision version, draft version и exact OCR-candidate manifest в одной транзакции.
- Identical confirmation retry идемпотентен; conflicting retry не создаёт частичных rows.
- Confirmed source/value fields не изменяются in place; correction создаёт replacement observation и supersession chain.
- Duplicate-looking observations не объединяются молча и не теряют document provenance.
- Confirmed observation без valid source-document/OCR/candidate provenance запрещён.
- Document deletion немедленно скрывает связанные drafts/observations и удаляет sole-provenance observations идемпотентно.
- Void/correction используют optimistic concurrency; permanent erasure owner-only и доступен после consent withdrawal.
- Ordinary audit/logs не содержат analyte, value, unit, range, patient identity или source text.
- Confirmed Labs core не создаёт diagnosis, recommendation, treatment instruction или dose calculation.

Канонические contracts:

- `docs/implementation/HC-017-DOCUMENTS-OCR-LABS-FOUNDATION.md`;
- `docs/implementation/HC-017-SLICE-D-OCR-CANDIDATES-AND-HUMAN-REVIEW.md`;
- `docs/implementation/HC-017-SLICE-E-CONFIRMED-LABS-CORE.md`.

## Privacy и medical safety

- Демонстрационные данные должны быть явно помечены и не выдаваться за реальные данные пользователя.
- Никаких автоматических диагнозов, назначений или отмены лечения.
- Любая медицинская интерпретация имеет provenance и источник.
- AI-ответ без evidence запрещён после включения AI-контура.
- Retrieval фильтруется по `profile_id` до поиска.
- Аналитика и логи не содержат медицинских значений, токенов и секретов.
- Экспорт и удаление пользователя должны охватывать raw, normalized, derived data и embeddings.

## API и routing

- Один method/path pair имеет одного канонического владельца route.
- Нельзя полагаться на порядок `include_router` для выбора корректного API contract.
- Backend errors используют документированный ограниченный набор envelopes; stack traces и SQL details не раскрываются.
- `request_id` возвращается в body или `X-Request-ID` и сохраняется frontend.
- State-changing GET routes запрещены, если нет отдельного ADR и компенсирующей защиты.

## CI и migrations

- Frontend CI выполняет full-source lint, TypeScript typecheck, tests и build.
- PostgreSQL CI проверяет migrations, RLS и privilege invariants.
- Для release-bound migration выполняется полный cycle `head → base → head` на отдельной test DB либо документируется безопасное исключение.
- `downgrade(): pass` запрещён, если после downgrade database state не соответствует объявленной revision.
- CI должен быть зелёным на exact commit SHA, который предлагается к deployment.

## Deployment

- Production deploy выполняется только из конкретного проверенного commit SHA.
- Перед миграцией — backup и проверка restore listing.
- Порядок: migration → backend → frontend → smoke.
- Автоматический downgrade запрещён после частично применённой или нетранзакционной миграции.
- Cross-user leak важнее доступности: при подтверждении сервис переводится в maintenance до исправления.
- Scanner GET, wrong-domain canonical mapping, duplicate-resolution 500 или token leakage являются stop conditions.
- Для document/Labs pipeline stop conditions включают scanner bypass, public raw-object access, cross-profile access, unconfirmed OCR facts, silent normalization, unsupported observations и medical data in logs.
