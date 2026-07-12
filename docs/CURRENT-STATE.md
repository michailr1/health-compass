# Health Compass — текущее состояние

Дата: 2026-07-12  
Основная ветка: `main`  
Main HEAD: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production URL: `https://health.funti.cc`  
Последний approved rollout target: `b8e868825f378195975e2729f3f36c21a1afa2d0`  
Production Alembic target: `0049`  
Текущий engineering verdict: `READY FOR NEXT PRODUCT PHASE / FOLLOW-UPS REMAIN`

## Evidence boundary

Владелец подтвердил 2026-07-12, что production-интерфейс и HC-016 работают.

В текущем репозитории есть полный automated rollout evidence для HC-015 и Git/CI evidence для HC-016. Детальный финальный VPS-отчёт HC-016 с backup path, release symlink, service output и disposable PostgreSQL checks в каноническую документацию не скопирован. Поэтому эти конкретные operational values здесь не выдумываются.

## Что работает в production

- FastAPI backend и React/Vite frontend;
- PostgreSQL + Alembic;
- direct Google OAuth 2.0 / OIDC;
- Email Magic Links через Brevo;
- локальные PostgreSQL sessions;
- users, identities, workspaces, profiles и permissions;
- FORCE ROW LEVEL SECURITY и tenant isolation;
- безопасный account linking и controlled duplicate resolution foundation;
- Basic Health Profile;
- история веса, provenance, consent и append-only audit;
- Clinical Context для состояний, аллергий, лекарств и добавок;
- review states `unknown`, `deferred`, `confirmed_none`, `has_entries`;
- contextual intake decisions;
- mobile-oriented questionnaire flow;
- Clinical Dictionaries v2 с Russian-first search и free-text fallback;
- dashboard context coverage и переходы к заполнению профиля;
- отдельные действия **Убрать из профиля** и **Удалить навсегда** для клинических записей.

## HC-014 — Clinical Dictionaries v2

Reviewed seed set развёрнут и подтверждён:

- 69 concepts total;
- 107 aliases;
- 0 duplicate concept business keys;
- 0 duplicate aliases;
- 0 orphan aliases;
- все 66 reviewed business keys представлены;
- повторный apply идемпотентен;
- существовавшие UUID сохранены.

Известные content gaps первого seed set:

- `мигрень` / `migraine`;
- `hypertension`;
- singular English `penicillin`;
- English phrase `vitamin d`.

Free-text entry остаётся доступным; gaps не являются importer defect.

## HC-015 — Code Review Remediation

Статус: `DEPLOYED / AUTOMATED VERIFIED / OWNER SMOKE CONFIRMED`.

Production rollout evidence зафиксирован в:

```text
docs/implementation/HC-015-PRODUCTION-EVIDENCE-2026-07-11.md
```

HC-015 закрыл блокирующие findings независимых review:

- duplicate Clinical Context routes;
- duplicate-resolution schema drift;
- scanner-unsafe Magic Link GET consume;
- wrong-domain и stale clinical dictionary mappings;
- неполный frontend lint/typecheck gate;
- void/review concurrency defects;
- unsafe logging и query-token exposure для новых логов;
- слишком широкие privileges на `users`;
- неполный migration-cycle gate.

HC-015 application commit: `c87723d7b4d0e4d2db9f1e0df4e936fbfd543346`.  
Alembic после HC-015: `0048`.

## Safari Magic Link regression

После HC-015 scanner-safe interstitial был выявлен Safari-specific origin regression. Он исправлен отдельным hotfix.

Hotfix commit:

```text
8c09c02fa007cd5e5945c5a93b4913ce63868e68
```

Владелец подтвердил работу Email Magic Link на iPhone Safari.

## HC-016 — Owner-controlled Clinical Record Erasure

Статус: `MERGED / PRODUCTION MANUALLY ACCEPTED`.

Source PRs:

- PR `#44` — owner-controlled permanent clinical record erasure;
- PR `#45` — удаление лишней фразы о backup retention из пользовательского предупреждения.

Merged target:

```text
b8e868825f378195975e2729f3f36c21a1afa2d0
```

Alembic head:

```text
0049
```

Продукт различает:

1. **Убрать из профиля** — void/soft removal с сохранением защищённой истории.
2. **Удалить навсегда** — owner-only erasure записи и value-bearing audit events.

Security contract:

- у `health_compass_app` нет прямого DELETE на clinical tables;
- runtime erasure выполняется только через `health_compass.app_erase_clinical_record(...)`;
- функция принадлежит `health_compass_rls_definer`;
- PUBLIC EXECUTE отозван;
- editor/viewer/outsider не могут выполнить permanent erasure;
- stale `expected_updated_at` не удаляет данные;
- удаление доступно после отзыва medical consent;
- сохраняется только content-free tombstone `clinical_record.erased`.

Текущий UI-текст:

```text
Запись и содержащие её медицинские значения в журнале изменений будут удалены. Отменить это действие нельзя.
```

Канонические документы:

```text
docs/implementation/HC-016-CLINICAL-RECORD-ERASURE.md
docs/implementation/HC-016-PRODUCTION-ACCEPTANCE-2026-07-12.md
```

## Подтверждённые security properties

- runtime role `NOBYPASSRLS`;
- отдельный `health_compass_rls_definer NOLOGIN BYPASSRLS`;
- ограниченные `SECURITY DEFINER` functions;
- фиксированные `search_path` и `row_security` settings;
- PUBLIC EXECUTE отозван у чувствительных definer functions;
- PKCE, state, nonce, issuer/audience/azp и verified-email checks;
- consent, provenance, void и audit для clinical data;
- одна DB transaction на request для transaction-local RLS context;
- прямой runtime DELETE клинических записей запрещён;
- optimistic concurrency применяется к destructive clinical actions.

## Известные ограничения продукта

- OCR/import документов не реализован;
- реальные загрузки лабораторных документов не реализованы;
- Labs core и динамика лабораторных показателей не реализованы;
- Oura и другие wearable integrations не реализованы;
- invitations и совместный доступ не завершены как user flow;
- AI explanation, evidence retrieval и doctor report не реализованы;
- clinical safety flags не выводятся автоматически из свободного текста;
- система не диагностирует заболевания и не рассчитывает дозы;
- словарь остаётся assistive и не заменяет free text.

## Технические follow-ups

Не блокируют переход к следующему product phase:

- revoke unnecessary PUBLIC EXECUTE у двух обычных trigger functions отдельной forward migration;
- переход с deprecated `authlib.jose` на `joserfc`;
- dictionary search indexes/trigram optimisation;
- cleanup неиспользуемой CORS configuration;
- OIDC discovery/JWKS caching;
- ограниченное хранение и штатная ротация исторических Apache logs, созданных до query-safe logging fix;
- добавить в репозиторий детальный HC-016 VPS rollout report, если исходный отчёт будет доступен.

## Следующий product этап

Текущий блокирующий remediation gate снят.

Следующий основной этап:

```text
PHASE-03 — Human Documents, OCR Review and Labs foundation
```

Рекомендуемый первый vertical slice:

```text
Upload
→ Processing
→ OCR Review
→ User Confirmation
→ Lab Results
→ Metric Dynamics
→ Contextual Intake
```

До импорта реальных медицинских данных необходимо сначала зафиксировать upload/storage threat model, provenance contract, document access matrix и deletion lifecycle.

## Роли

### ChatGPT / coding role

- архитектура и data contracts;
- product code;
- migrations, RLS и tests;
- frontend;
- документация;
- точные задачи VPS-agent.

### VPS-agent

- работает только с production host;
- фиксирует HEAD/Alembic before;
- создаёт backup;
- получает конкретный approved commit;
- выполняет build, migrations, systemd/release switch;
- запускает smoke tests;
- не принимает архитектурных решений;
- не использует production DB для destructive automated tests;
- не выводит secrets.

## Stop conditions

Остановить merge или rollout при:

- несовпадении expected HEAD;
- dirty production worktree;
- неуспешном backup;
- нескольких Alembic heads;
- неуспешной migration;
- признаках cross-user leak;
- `5xx`, `54001`, `42501`, `permission denied` или Traceback;
- CI, запущенном не на exact deployed SHA;
- появлении tokens, secrets или medical values в logs.
