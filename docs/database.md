# Database

## PostgreSQL 16

Health Compass uses PostgreSQL 16 running in a Docker container.

### Connection

- **Host:** 127.0.0.1:5433
- **Production database:** health_compass
- **Test database:** health_compass_test
- **Application schema:** health_compass

### Roles

| Role | Purpose | Privileges |
|------|---------|------------|
| `health_compass_migrator` | Alembic migrations | OWNER of schema and tables |
| `health_compass_app` | Application runtime | CONNECT, USAGE, SELECT/INSERT/UPDATE/DELETE on tables |
| `health_compass_test_migrator` | Test migrations | Same as migrator, for test DB only |
| `health_compass_test_app` | Test runtime | Same as app, for test DB only |

All application roles have: `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS`

### Schema

```
health_compass (schema)
├── service_metadata    — Key-value store for system configuration
├── audit_events        — Immutable audit log
└── processing_jobs     — Async job tracking
```

### Tables

#### service_metadata
| Column | Type | Description |
|--------|------|-------------|
| key | VARCHAR(255) PK | Configuration key |
| value | TEXT | Configuration value |
| updated_at | TIMESTAMPTZ | Last update timestamp |

#### audit_events
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Unique event identifier |
| event_type | VARCHAR(100) | Type of event |
| result | VARCHAR(20) | Success/failure/error |
| request_id | VARCHAR(36) | Correlating request ID |
| actor_user_id | VARCHAR(255) | User who performed action |
| profile_id | VARCHAR(255) | Related profile |
| entity_type | VARCHAR(100) | Type of affected entity |
| entity_id | VARCHAR(255) | ID of affected entity |
| ip_address | VARCHAR(45) | Client IP |
| user_agent | TEXT | Client user agent |
| metadata | JSONB | Additional event data |
| created_at | TIMESTAMPTZ | Event timestamp |

#### processing_jobs
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Job identifier |
| job_type | VARCHAR(100) | Type of job |
| status | VARCHAR(20) | queued/running/completed/failed/cancelled |
| progress | FLOAT | Progress percentage |
| result | JSONB | Job result data |
| error_code | VARCHAR(50) | Error code if failed |
| error_message | TEXT | Error details if failed |
| created_at | TIMESTAMPTZ | Creation timestamp |
| started_at | TIMESTAMPTZ | Processing start |
| completed_at | TIMESTAMPTZ | Processing end |

### Migrations

Managed by Alembic. Migration files in `backend/alembic/versions/`.

```bash
# Create new migration
cd /opt/health-compass/repo/backend
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one step
uv run alembic downgrade -1
```

### Backup

```bash
# Production database
docker exec health-compass-pg16 pg_dump -U health_compass_migrator \
  -d health_compass --format=custom \
  -f /tmp/health_compass_$(date +%Y%m%d_%H%M%S).dump
docker cp health-compass-pg16:/tmp/health_compass_*.dump \
  /opt/health-compass/backups/

# Global objects
docker exec health-compass-pg16 pg_dumpall --globals-only -U postgres > \
  /opt/health-compass/backups/pg16-globals-$(date +%Y%m%d_%H%M%S).sql
```

### Restore

```bash
# Restore global objects
docker exec -i health-compass-pg16 psql -U postgres < pg16-globals-*.sql

# Restore database
docker cp health_compass_*.dump health-compass-pg16:/tmp/
docker exec health-compass-pg16 pg_restore -U health_compass_migrator \
  -d health_compass --clean --if-exists /tmp/health_compass_*.dump
```
