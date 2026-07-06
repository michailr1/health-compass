# Backend Architecture

## Overview

Health Compass Backend is a FastAPI application serving as the API layer for the Health Compass personal health portal.

## Technology Stack

- **Runtime:** Python 3.12 (managed via uv)
- **Framework:** FastAPI 0.115+
- **ASGI Server:** Uvicorn
- **ORM:** SQLAlchemy 2.x (async)
- **Database Driver:** psycopg 3 (async)
- **Migrations:** Alembic
- **Validation:** Pydantic 2
- **Database:** PostgreSQL 16 (Docker container)

## Directory Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── api/
│   │   ├── router.py        # Main API router
│   │   └── routes/
│   │       ├── health.py    # GET /health/api/health
│   │       ├── version.py   # GET /health/api/version
│   │       └── private.py   # GET /health/api/private/ping (401)
│   ├── core/
│   │   ├── config.py        # Pydantic Settings
│   │   ├── logging.py       # Structured JSON logging
│   │   ├── request_id.py    # Request ID middleware
│   │   └── security.py      # Auth-ready dependency (always 401)
│   ├── db/
│   │   ├── base.py          # SQLAlchemy DeclarativeBase
│   │   └── session.py       # Async session factory
│   ├── models/
│   │   ├── service_metadata.py
│   │   ├── audit_event.py
│   │   └── processing_job.py
│   └── schemas/
│       ├── health.py
│       ├── version.py
│       └── errors.py
├── alembic/                 # Database migrations
├── tests/                   # pytest test suite
├── pyproject.toml
├── uv.lock
└── .env.example
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health/api/health | No | Service health + database check |
| GET | /health/api/version | No | Service version and build info |
| GET | /health/api/private/ping | Yes (401) | Protected endpoint placeholder |
| GET | /health/api/docs | No* | Swagger UI (temporary) |
| GET | /health/api/redoc | No* | ReDoc (temporary) |
| GET | /health/api/openapi.json | No* | OpenAPI schema (temporary) |

*Documentation is temporarily public. Must be restricted before adding user-data endpoints.

## Port

- **Internal:** 127.0.0.1:8100
- **External:** https://funti.cc/health/api/ (via Apache ProxyPass)

## Database

- **Host:** 127.0.0.1:5433 (Docker PostgreSQL 16)
- **Database:** health_compass (production), health_compass_test (test)
- **Schema:** health_compass (application schema, not public)
- **Migrations:** Alembic, run by health_compass_migrator role

## Security Model

- **No real authentication yet** — all protected endpoints return 401
- Auth-ready: security module with dependency injection for future OIDC
- Database roles strictly separated: migrator (DDL) vs app (DML)
- No SUPERUSER, CREATEDB, CREATEROLE for application roles
- Secrets stored in /etc/health-compass/ (root-only, 0600)
