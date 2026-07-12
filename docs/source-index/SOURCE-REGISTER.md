# Health Compass — реестр источников

Этот файл связывает стратегические материалы, внешние reviews, implementation evidence и живую документацию репозитория.

## Стратегические материалы

| Источник | Назначение | Каноническое отражение |
|---|---|---|
| `01-health-compass-master-plan.pdf` | полный мастер-план продукта | `docs/PROJECT-PLAN.md` |
| `03-implementation-roadmap.xlsx` | этапы и зависимости | `docs/PROJECT-PLAN.md` |
| `04-health-compass-vision-and-roadmap.pptx` | продуктовая концепция | `docs/PROJECT-PLAN.md` |
| `14-unit-economics.xlsx` | экономика и монетизация | будущий economics plan |
| `START-HERE.md` | навигация по исходному комплекту | этот реестр и README |
| `health-compass-master-plan.zip` | reference archive | неизменяемый исходный архив |

## Product, UX and AI sources

| Источник | Назначение | Каноническое отражение |
|---|---|---|
| Fable Stage 2.5 intake materials | progressive health intake | `docs/PROGRESSIVE-HEALTH-INTAKE.md` |
| Fable Stage 3 product/UX/AI materials | Human/Pet model and AI safety | `docs/PRODUCT-UX-BASELINE.md`, `docs/AI-PRODUCT-SAFETY.md` |
| Fable Stage 3.5 UI blueprint | screens, navigation and actions | UX baseline and backlog |

## External reviews

| Source | Scope | Canonical result |
|---|---|---|
| `ревью Fable5.txt` | architecture, product, security, operations | plans, ADRs and runbooks |
| `2-Ревью-Fable5-Postgre-рекурсия.txt` | RLS recursion and escalation | migrations `0020–0021`, security invariants |
| Fable 5 review, 2026-07-11 | backend/frontend/auth/RLS/CI | `docs/reviews/FABLE-5-INDEPENDENT-CODE-REVIEW-2026-07-11.md` |
| ChatGPT review, 2026-07-11 | code, migrations and operations | `docs/reviews/CODE-REVIEW-CONSOLIDATED-2026-07-11.md` |

## HC-015 and HC-016 evidence

| Source | Purpose |
|---|---|
| PR `#39`, commit `c87723d7b4d0e4d2db9f1e0df4e936fbfd543346` | HC-015 remediation |
| migrations `0046–0048` | schema and privilege hardening |
| `docs/implementation/HC-015-PRODUCTION-EVIDENCE-2026-07-11.md` | controlled rollout evidence |
| PR `#44`, merge `69b56f12c25457321b49c7412479f5aa4f238b86` | clinical-record erasure |
| migration `0049` | restricted erasure and audit scrubbing |
| PR `#45`, merge `b8e868825f378195975e2729f3f36c21a1afa2d0` | approved warning-copy fix |

## HC-017 Slice A and B

| Source | Purpose |
|---|---|
| PR `#47`, merge `435c6ff7bd05468a8c4a3d48d165b712ab64cedd` | Documents/OCR/Labs architecture |
| `docs/implementation/HC-017-DOCUMENTS-OCR-LABS-FOUNDATION.md` | canonical foundation contract |
| PR `#48`, merge `ccabab77cf929456a74b69c3478c71f92f167f78` | secure document intake implementation |
| verified head `46c5ea89d35cc85be0af3b80a9c56f40d5705ac5` | exact reviewed Slice B code |
| migration `0050` | document tables, RLS and activity sync |
| CI `#402` | backend/frontend/migration/PostgreSQL verification |
| `docs/implementation/HC-017-SLICE-B-IMPLEMENTATION-2026-07-12.md` | canonical Slice B evidence |

## HC-017 Slice C1 evidence

| Source | Purpose |
|---|---|
| PR `#51`, merge `a0dd405ca3e789cb70e5c4ad94de9a272dff878f` | encrypted storage and scanner worker |
| verified head `c32e420b59d950aad48366c79010f5ac9fecb43b` | exact reviewed C1 code |
| migration `0051` | encryption/scanner metadata and worker functions |
| CI `#414` | backend/frontend/migration/worker verification |
| `docs/implementation/HC-017-SLICE-C1-IMPLEMENTATION-2026-07-12.md` | canonical C1 evidence |

Key C1 sources:

- `backend/app/storage/encrypted_objects.py`;
- `backend/app/storage/documents.py`;
- `backend/app/scanning/clamav.py`;
- `backend/app/workers/document_scanner.py`;
- `backend/alembic/versions/0051_add_encrypted_document_scanner_worker.py`.

## HC-017 Slice C2 evidence

| Source | Purpose |
|---|---|
| PR `#53`, merge `06e4f0a228b4867d9bf7983284bc04f3cb53cd05` | quota, reconciliation and safe rendering |
| verified head `568eca1ec1c91005b907cc79349036a71d7f6f83` | exact reviewed C2 code |
| migrations `0052–0053` | quota/render/reconciliation and idempotency hardening |
| CI `#433` | backend/frontend/full migration/renderer/reconciler verification |
| `docs/implementation/HC-017-SLICE-C2-SAFE-RENDERING-EVIDENCE-2026-07-12.md` | canonical C2 evidence |

Key C2 sources:

- `backend/alembic/versions/0052_add_document_quota_reconciliation_rendering.py`;
- `backend/alembic/versions/0053_make_document_missing_reconciliation_idempotent.py`;
- `backend/app/rendering/verified_memory.py`;
- `backend/app/rendering/safe_render.py`;
- `backend/app/workers/document_renderer.py`;
- `backend/app/workers/document_reconciler.py`.

## HC-017 combined C1+C2 security review

| Source | Purpose |
|---|---|
| `docs/reviews/HC-017-C1-C2-COMBINED-SECURITY-REVIEW-2026-07-12.md` | encryption/scanner/quota/render/reconciliation review |
| repository baseline `ac9e21f3315c4624a845e633c2a90881d348ca30` | reviewed baseline before D1 |
| CI `#414`, `#433`, `#435` | implementation and documentation verification |

```text
ACCEPT FOR REPOSITORY FOUNDATION
NO UNRESOLVED CRITICAL OR HIGH FINDING
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

## HC-017 Slice D architecture and implementation

| Source | Purpose |
|---|---|
| `docs/implementation/HC-017-SLICE-D-OCR-CANDIDATES-AND-HUMAN-REVIEW.md` | canonical D1/D2 contract |
| PR `#56`, merge `a33c3d515b885c6ea0e8f51291a1d25bed77cd7d` | D1 local OCR implementation |
| verified D1 head `dc28e9e220dd51264e6dab1244ce8d8696f501b2` | exact reviewed D1 code |
| migration `0054`, CI `#442` | D1 schema and verification |
| `docs/implementation/HC-017-SLICE-D1-OCR-CANDIDATES-EVIDENCE-2026-07-12.md` | canonical D1 evidence |
| PR `#58`, merge `f67a1128e29a1c62e8a3b27dd20c973df82947ad` | D2 human review implementation |
| verified D2 head `4ecae1fb0816803b2d858db1f5016bce589544d5` | exact reviewed D2 code |
| migration `0055`, CI `#454` | D2 schema and verification |
| `docs/implementation/HC-017-SLICE-D2-HUMAN-REVIEW-EVIDENCE-2026-07-12.md` | canonical D2 evidence |

Official Tesseract references:

- `https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html`;
- `https://tesseract-ocr.github.io/tessdoc/Data-Files.html`;
- `https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html`.

D1+D2 status:

```text
IMPLEMENTED
MERGED
CI VERIFIED
NOT DEPLOYED
NO AUTOMATIC CLINICAL OR LABS FACTS
```

## HC-017 Slice E architecture and E1 evidence

| Source | Purpose |
|---|---|
| PR `#60`, merge `e60c2f9f96dc5c1e377466614aa8ef12be6199d8` | confirmed Labs architecture and security contract |
| `docs/implementation/HC-017-SLICE-E-CONFIRMED-LABS-CORE.md` | canonical E1/E2/E3 contract |
| `docs/reviews/HC-017-SLICE-E-ARCHITECTURE-REVIEW-2026-07-12.md` | independent architecture review |
| PR `#61`, merge `2ad0ca47d994472201c218b3e6af37145cbacdec` | E1 source-preserving Lab drafts |
| verified head `419386e909207ab67921c008e210c059aba6658c` | exact reviewed E1 code |
| migrations `0056–0057` | Lab drafts, provenance and context-hardening functions |
| CI `#477` | backend/frontend/full migration/E1-RLS verification |
| `docs/implementation/HC-017-SLICE-E1-LAB-DRAFTS-EVIDENCE-2026-07-12.md` | canonical E1 implementation evidence |

Key E1 sources:

- `backend/alembic/versions/0056_add_source_preserving_lab_drafts.py`;
- `backend/alembic/versions/0057_harden_lab_draft_context_mutations.py`;
- `backend/app/models/lab_observation.py`;
- `backend/app/schemas/lab_observation.py`;
- `backend/app/services/lab_observation.py`;
- `backend/app/api/routes/lab_observation.py`;
- `backend/tests/test_lab_observation_drafts_rls.py`;
- `backend/tests/test_lab_observation_draft_context_hardening.py`;
- `src/lib/labDraftApi.ts`;
- `src/pages/LabDrafts.tsx`.

E1 status:

```text
IMPLEMENTED
MERGED
CI VERIFIED
NOT DEPLOYED
NO CONFIRMED OBSERVATIONS
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
3. External recommendations are not implemented without code/test evidence.
4. Architecture, implementation, merge, verification and deployment are separate states.
5. Production state overrides repository plans when describing user availability.
6. Secrets, credentials, encryption keys, object paths, OCR text and medical values are excluded.
7. Manual acceptance does not invent absent operational metrics.
8. Every rollout record names an exact SHA.
9. HC-017 is not production-ready before host provisioning, security review and controlled rollout gates pass.
10. OCR output and reviewed transcription are not clinical facts.
11. E1 Lab drafts are not confirmed observations and are invisible to `view`, `analyze`, analytics and AI interpretation.
