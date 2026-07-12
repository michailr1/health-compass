# Health Compass — реестр источников

Этот файл связывает стратегические материалы, внешние reviews, implementation evidence и живую документацию репозитория.

## Стратегические материалы

| Источник | Назначение | Каноническое отражение |
|---|---|---|
| `01-health-compass-master-plan.pdf` | полный мастер-план продукта | `docs/PROJECT-PLAN.md` |
| `03-implementation-roadmap.xlsx` | этапы, зависимости и сроки | `docs/PROJECT-PLAN.md` |
| `04-health-compass-vision-and-roadmap.pptx` | продуктовая концепция и roadmap | `docs/PROJECT-PLAN.md` |
| `14-unit-economics.xlsx` | экономика и монетизация | будущий economics plan |
| `START-HERE.md` | навигация по исходному комплекту | этот реестр и README |
| `health-compass-master-plan.zip` | reference archive | неизменяемый исходный архив |

## Product, UX and AI sources

| Источник | Назначение | Каноническое отражение |
|---|---|---|
| Fable Stage 2.5 intake materials | progressive health intake | `docs/PROGRESSIVE-HEALTH-INTAKE.md` |
| Fable Stage 3 product/UX/AI materials | Human/Pet product model, AI safety | `docs/PRODUCT-UX-BASELINE.md`, `docs/AI-PRODUCT-SAFETY.md` |
| Fable Stage 3.5 UI blueprint | screens, navigation, actions, components | `docs/PRODUCT-UX-BASELINE.md`, project backlog |

Accepted deviations are recorded in canonical Markdown, not by editing the source PDF/XLSX/PPTX artifacts.

## External reviews

| Source | Scope | Canonical result |
|---|---|---|
| `ревью Fable5.txt` | architecture, product, security, operations | plans, ADRs, runbooks, recommendation register |
| `2-Ревью-Fable5-Postgre-рекурсия.txt` | RLS recursion and escalation paths | migrations `0020–0021`, security invariants |
| Fable 5 independent review, 2026-07-11 | backend/frontend/auth/RLS/Clinical Context/CI | `docs/reviews/FABLE-5-INDEPENDENT-CODE-REVIEW-2026-07-11.md` |
| ChatGPT independent review, 2026-07-11 | code, migrations, contracts, operations | `docs/reviews/CODE-REVIEW-CONSOLIDATED-2026-07-11.md` |

## HC-015 evidence

| Source | Purpose |
|---|---|
| PR `#39`, application commit `c87723d7b4d0e4d2db9f1e0df4e936fbfd543346` | remediation implementation |
| migrations `0046–0048` | duplicate activity, dictionary integrity, users grants |
| `docs/implementation/HC-015-PRODUCTION-EVIDENCE-2026-07-11.md` | backup, migration, health, logging and automated rollout evidence |
| backend/frontend/PostgreSQL tests | exact contract and regression evidence |

## Safari Magic Link hotfix evidence

| Source | Purpose |
|---|---|
| commit `8c09c02fa007cd5e5945c5a93b4913ce63868e68` | Safari-safe origin handling |
| owner manual confirmation | iPhone Safari Magic Link works after hotfix |

## HC-016 evidence

| Source | Purpose |
|---|---|
| PR `#44`, merge `69b56f12c25457321b49c7412479f5aa4f238b86` | owner-controlled clinical erasure |
| migration `0049` | restricted erasure, audit scrubbing and tombstone contract |
| PR `#45`, merge `b8e868825f378195975e2729f3f36c21a1afa2d0` | approved UI copy correction |
| `docs/implementation/HC-016-CLINICAL-RECORD-ERASURE.md` | product/API/database contract |
| `docs/implementation/HC-016-PRODUCTION-ACCEPTANCE-2026-07-12.md` | manual acceptance and evidence boundary |

## HC-017 Slice A architecture evidence

| Source | Purpose |
|---|---|
| PR `#47`, merge `435c6ff7bd05468a8c4a3d48d165b712ab64cedd` | Documents/OCR/Labs architecture |
| `docs/implementation/HC-017-DOCUMENTS-OCR-LABS-FOUNDATION.md` | canonical architecture and delivery contract |
| `docs/SECURITY-INVARIANTS.md` | upload, storage, worker, OCR, logging and deletion invariants |
| `docs/PRODUCT-UX-BASELINE.md` | upload/review/result user-flow baseline |
| `docs/AI-PRODUCT-SAFETY.md` | untrusted-document and human-confirmation rules |

Slice A status:

```text
ARCHITECTURE MERGED
NO PRODUCT CODE
NO PRODUCTION CHANGE
```

## HC-017 Slice B implementation evidence

| Source | Purpose |
|---|---|
| PR `#48` | Secure Document Intake Foundation implementation |
| verified head `46c5ea89d35cc85be0af3b80a9c56f40d5705ac5` | exact reviewed and tested implementation |
| merge `ccabab77cf929456a74b69c3478c71f92f167f78` | Slice B merged into `main` |
| migration `0050` | document metadata, durable jobs, RLS, privileges and duplicate-activity sync |
| CI run `#402` | backend, frontend, migration-cycle and PostgreSQL verification |
| `docs/implementation/HC-017-SLICE-B-IMPLEMENTATION-2026-07-12.md` | canonical implementation evidence and production boundary |

### Slice B database and security sources

| Source | Evidence |
|---|---|
| `backend/alembic/versions/0050_add_secure_document_intake_foundation.py` | tables, RLS, grants, helper ownership, audit action and activity wrapper |
| `backend/tests/test_document_intake_rls.py` | owner/edit/view/analyze/outsider matrix, no direct UPDATE/DELETE |
| `backend/tests/test_migration_cycle.py` | `head → base → head`, owners, grants, FORCE RLS |
| `backend/tests/test_document_intake_http.py` | profile-aware capabilities, upload and access contracts |

### Slice B upload and artifact sources

| Source | Evidence |
|---|---|
| `backend/app/storage/documents.py` | private local quarantine adapter, magic-byte and dimension checks |
| `backend/app/core/document_upload_limit.py` | pre-parser Content-Length and chunked-body boundary |
| `backend/app/db/session.py` | rollback cleanup hooks for external artifacts |
| `backend/tests/test_document_storage.py` | opaque keys, permissions, formats and size checks |
| `backend/tests/test_document_upload_limit.py` | body limit before multipart parsing |
| `backend/tests/test_session_rollback_cleanup.py` | failure/cancellation cleanup behavior |

### Slice B frontend sources

| Source | Evidence |
|---|---|
| `src/pages/Documents.tsx` | metadata/status page and disabled incomplete features |
| `src/lib/documentApi.ts` | capabilities, upload and list contracts |
| `src/lib/documentApi.test.ts` | format/status/size helper coverage |

Slice B status:

```text
IMPLEMENTED
MERGED
CI VERIFIED
NOT DEPLOYED
PRODUCTION UPLOAD DISABLED
```

## Current factual sources

- Git commits and pull requests;
- Alembic migrations;
- automated tests and CI runs;
- production SQL and rollout reports;
- Apache/systemd/Certbot state;
- explicit owner manual acceptance;
- approved architecture and security contracts.

## Rules

1. Source PDF/XLSX/PPTX artifacts remain immutable references.
2. Accepted decisions are copied into canonical Markdown.
3. External recommendations are not “implemented” without code/test evidence.
4. Architecture status does not mean implementation or deployment.
5. `IMPLEMENTED`, `MERGED`, `VERIFIED` and `DEPLOYED` are separate states.
6. Production state has priority over repository plans when describing what users can access.
7. Secrets, auth tokens, private storage keys and medical values are not stored in this register.
8. Manual acceptance confirms user-visible behavior but does not invent absent operational metrics.
9. Every rollout evidence record names an exact commit SHA.
10. HC-017 Slice B must not be described as production-ready before scanner, private storage and worker reviews are complete.
