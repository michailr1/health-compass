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
| PR `#48` | secure document intake implementation |
| verified head `46c5ea89d35cc85be0af3b80a9c56f40d5705ac5` | exact reviewed Slice B code |
| merge `ccabab77cf929456a74b69c3478c71f92f167f78` | Slice B merged into `main` |
| migration `0050` | document tables, RLS and activity sync |
| CI `#402` | backend/frontend/migration/PostgreSQL verification |
| `docs/implementation/HC-017-SLICE-B-IMPLEMENTATION-2026-07-12.md` | canonical Slice B evidence |

## HC-017 Slice C1 evidence

| Source | Purpose |
|---|---|
| PR `#51` | encrypted storage and scanner-worker implementation |
| verified head `c32e420b59d950aad48366c79010f5ac9fecb43b` | exact reviewed C1 code |
| merge `a0dd405ca3e789cb70e5c4ad94de9a272dff878f` | C1 merged into `main` |
| migration `0051` | encryption/scanner metadata and worker functions |
| CI `#414` | backend/frontend/migration/worker verification |
| `docs/implementation/HC-017-SLICE-C1-IMPLEMENTATION-2026-07-12.md` | canonical C1 evidence |

Key C1 sources:

- `backend/app/storage/encrypted_objects.py`;
- `backend/app/storage/documents.py`;
- `backend/app/scanning/clamav.py`;
- `backend/app/workers/document_scanner.py`;
- `backend/alembic/versions/0051_add_encrypted_document_scanner_worker.py`;
- `backend/tests/test_encrypted_objects.py`;
- `backend/tests/test_clamav_client.py`;
- `backend/tests/test_document_worker_rls.py`.

## HC-017 Slice C2 evidence

| Source | Purpose |
|---|---|
| PR `#53` | quota, reconciliation and safe-rendering implementation |
| verified head `568eca1ec1c91005b907cc79349036a71d7f6f83` | exact reviewed C2 code |
| merge `06e4f0a228b4867d9bf7983284bc04f3cb53cd05` | C2 merged into `main` |
| migrations `0052–0053` | quota/render/reconciliation and idempotency hardening |
| CI `#433` | backend/frontend/full migration/renderer/reconciler verification |
| `docs/implementation/HC-017-SLICE-C2-SAFE-RENDERING-EVIDENCE-2026-07-12.md` | canonical C2 evidence |

Key C2 sources:

- `backend/alembic/versions/0052_add_document_quota_reconciliation_rendering.py`;
- `backend/alembic/versions/0053_make_document_missing_reconciliation_idempotent.py`;
- `backend/app/rendering/verified_memory.py`;
- `backend/app/rendering/safe_render.py`;
- `backend/app/storage/rendered_documents.py`;
- `backend/app/workers/document_renderer.py`;
- `backend/app/workers/document_reconciler.py`;
- `backend/tests/test_safe_render.py`;
- `backend/tests/test_document_rendering_rls.py`;
- `backend/tests/test_document_reconciliation_rls.py`.

## HC-017 combined C1+C2 security review

| Source | Purpose |
|---|---|
| `docs/reviews/HC-017-C1-C2-COMBINED-SECURITY-REVIEW-2026-07-12.md` | combined encryption/scanner/quota/render/reconciliation review |
| repository baseline `ac9e21f3315c4624a845e633c2a90881d348ca30` | reviewed baseline before D1 |
| CI `#414`, `#433`, `#435` | exact implementation and documentation verification |

```text
ACCEPT FOR REPOSITORY FOUNDATION
NO UNRESOLVED CRITICAL OR HIGH FINDING
NOT APPROVED FOR PRODUCTION DEPLOYMENT
```

## HC-017 Slice D architecture

| Source | Purpose |
|---|---|
| `docs/implementation/HC-017-SLICE-D-OCR-CANDIDATES-AND-HUMAN-REVIEW.md` | canonical D1/D2 OCR and review contract |
| Tesseract command-line documentation | fixed local OCR command and TSV output contract |
| Tesseract data-file documentation | language/traineddata provisioning contract |
| Tesseract quality documentation | page segmentation and quality constraints |

Selected architecture:

```text
C2 encrypted safe_page
→ full GCM verification
→ sealed memory input
→ bounded local Tesseract TSV
→ encrypted TSV provenance
→ strict parser
→ owner/edit-only needs_review candidates
→ explicit patient matching
→ no automatic clinical or Labs fact
```

Official technical references:

- `https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html`;
- `https://tesseract-ocr.github.io/tessdoc/Data-Files.html`;
- `https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html`;
- `https://tesseract-ocr.github.io/tessdoc/Home.html`.

## HC-017 Slice D1 implementation evidence

| Source | Purpose |
|---|---|
| PR `#56` | local OCR candidate extraction implementation |
| verified head `dc28e9e220dd51264e6dab1244ce8d8696f501b2` | exact reviewed D1 code |
| merge `a33c3d515b885c6ea0e8f51291a1d25bed77cd7d` | D1 merged into `main` |
| migration `0054` | OCR tables, FORCE RLS, queue/worker/reconciliation functions |
| CI `#442` | backend/frontend/full migration/OCR-RLS verification |
| `docs/implementation/HC-017-SLICE-D1-OCR-CANDIDATES-EVIDENCE-2026-07-12.md` | canonical D1 evidence |

Key D1 sources:

- `backend/alembic/versions/0054_add_document_ocr_candidates.py`;
- `backend/app/ocr/tesseract.py`;
- `backend/app/storage/ocr_documents.py`;
- `backend/app/workers/document_ocr.py`;
- `backend/app/api/routes/document_ocr.py`;
- `backend/app/services/document_ocr.py`;
- `backend/tests/test_document_ocr_rls.py`;
- `backend/tests/test_tesseract_ocr.py`;
- `backend/tests/test_ocr_storage.py`.

D1 status:

```text
IMPLEMENTED
MERGED
CI VERIFIED
NOT DEPLOYED
NO AUTOMATIC CLINICAL OR LABS FACTS
```

## HC-017 Slice D2 implementation evidence

| Source | Purpose |
|---|---|
| PR `#58` | human OCR review and patient matching implementation |
| verified head `4ecae1fb0816803b2d858db1f5016bce589544d5` | exact reviewed D2 code |
| merge `f67a1128e29a1c62e8a3b27dd20c973df82947ad` | D2 merged into `main` |
| migration `0055` | patient decisions, review provenance and restricted review functions |
| CI `#454` | backend/frontend/full migration/D2-RLS verification |
| `docs/implementation/HC-017-SLICE-D2-HUMAN-REVIEW-EVIDENCE-2026-07-12.md` | canonical D2 evidence |

Key D2 sources:

- `backend/alembic/versions/0055_add_document_ocr_human_review.py`;
- `backend/app/models/document_ocr.py`;
- `backend/app/schemas/document_ocr.py`;
- `backend/app/services/document_ocr.py`;
- `backend/app/api/routes/document_ocr.py`;
- `backend/tests/test_document_ocr_review_rls.py`;
- `backend/tests/test_document_ocr_review_schemas.py`;
- `src/lib/documentOcrReviewApi.ts`;
- `src/pages/DocumentOCRReview.tsx`;
- `src/pages/Documents.tsx`.

D2 status:

```text
IMPLEMENTED
MERGED
CI VERIFIED
NOT DEPLOYED
NO AUTOMATIC CLINICAL OR LABS FACTS
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
10. OCR output and reviewed transcription are not clinical facts without a separate explicit confirmation transaction.
