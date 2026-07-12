# HC-017 Slice B — Secure Document Intake Implementation Evidence

Status: `MERGED / VERIFIED IN CI / NOT DEPLOYED`  
Date: 2026-07-12  
Source PR: `#48`  
Verified head: `46c5ea89d35cc85be0af3b80a9c56f40d5705ac5`  
Merge commit: `ccabab77cf929456a74b69c3478c71f92f167f78`  
CI run: `#402`  
Repository Alembic head: `0050`  
Production Alembic: `0049`

## Verdict

Slice B establishes a secure development/test document-intake foundation and is merged into `main`.

It is not approved for production deployment. Production upload remains disabled and startup validation rejects attempts to enable it outside development.

```text
MERGEABLE_AND_MERGED
NOT_DEPLOYABLE
```

## Implemented boundary

### Database

- migration `0050` follows `0049` with a single Alembic head;
- `profile_documents` stores source-document metadata only;
- `document_processing_jobs` stores durable intake-job metadata;
- both tables use RLS and FORCE RLS;
- owner/edit may insert;
- owner/edit/view may read metadata;
- analyze and outsider cannot read document metadata;
- runtime application role has no direct UPDATE or DELETE;
- processing jobs are bound to the same profile as their parent document by composite FK;
- `document.uploaded` audit contains no filename or medical values;
- documents participate in duplicate-account meaningful-activity assessment.

### Upload and quarantine

- accepted formats: PDF, JPEG and PNG;
- extension, declared MIME and magic bytes must agree;
- maximum source file size: 20 MiB;
- maximum image size: 25 megapixels;
- complete multipart request is bounded before parsing;
- chunked request bodies are counted;
- storage key uses only a server-generated UUID;
- local development/test storage uses private file permissions;
- PDF is not parsed by the web process;
- quarantined originals cannot be previewed or downloaded.

### Transaction consistency

External quarantine artifacts register transaction-bound rollback cleanup.

Cleanup runs when:

- route validation or database work fails;
- final database commit fails;
- request task is cancelled.

Cleanup errors do not disclose paths or filenames.

### API and UI

Implemented routes:

```text
GET  /profiles/{profile_id}/document-intake/capabilities
POST /profiles/{profile_id}/documents
GET  /profiles/{profile_id}/documents
GET  /profiles/{profile_id}/documents/{document_id}
```

Implemented UI:

```text
/app/documents
```

The page exposes only metadata and quarantine status. It explicitly states that preview and OCR are unavailable.

## Security findings resolved before merge

The implementation review found and fixed:

1. **FORCE RLS function-creation ordering** — document visibility helper now defers body compilation until ownership is transferred to the dedicated definer role.
2. **Job/profile integrity** — composite FK prevents a processing job from referencing a document owned by another profile.
3. **ORM flush ordering** — parent document is flushed before the dependent job inside the same transaction.
4. **Analyze-role overreach** — a document-specific PostgreSQL helper excludes analyze from raw-document metadata.
5. **Misleading frontend capability** — capability is calculated against the current profile and permission, not only a global feature flag.
6. **External-object orphan risk** — rollback cleanup covers route error, commit error and request cancellation.
7. **Pre-parser body exhaustion** — ASGI middleware bounds both Content-Length and chunked document uploads before multipart parsing.
8. **Failure diagnostics** — backend lint failures produce short-lived non-sensitive artifacts for exact diagnosis.

## CI evidence

CI run `#402` passed on exact head `46c5ea89...`.

Successful jobs:

- backend compile;
- Ruff;
- backend unit tests;
- frontend lint;
- frontend typecheck;
- frontend tests;
- frontend production build;
- migration boundary tests;
- isolated `head → base → head` migration cycle;
- all PostgreSQL integration and RLS tests.

## Production boundary

Production remains unchanged:

```text
application: b8e868825f378195975e2729f3f36c21a1afa2d0
Alembic: 0049
DOCUMENT_UPLOAD_ENABLED=false
```

Not available in production:

- document upload;
- quarantine storage;
- scanner;
- preview/download;
- worker;
- OCR;
- extraction review;
- confirmed Labs data.

No rollout task should be issued for PR `#48`.

## Next approved activity

Before Slice C implementation:

- independent security review of Slice B;
- production private-storage decision;
- malware-scanner decision;
- worker-role and credential design;
- safe PDF inspection and rasterization threat model.

Slice C remains a separate branch and PR.
