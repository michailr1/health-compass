# Backend Deployment

## Prerequisites

- Ubuntu 20.04+ VPS
- Docker and Docker Compose
- uv (installed)
- Apache with proxy modules

## Components

1. **PostgreSQL 16** — Docker container (health-compass-pg16)
2. **Backend API** — systemd service (health-compass-api)
3. **Apache** — reverse proxy for /health/api/

## PostgreSQL 16 Deployment

```bash
# Start PostgreSQL 16 container
cd /opt/health-compass/runtime/postgres
docker compose -f compose.yml up -d

# Verify
docker ps --filter name=health-compass-pg16
docker exec health-compass-pg16 pg_isready -U postgres
```

## Backend Deployment

```bash
# As root
cd /opt/health-compass/repo/backend

# Install dependencies
export PATH=$HOME/.local/bin:$PATH
uv sync

# Create systemd service
cp docs/examples/health-compass-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable health-compass-api
systemctl start health-compass-api

# Verify
systemctl status health-compass-api
curl -s http://127.0.0.1:8100/health/api/health
```

## Apache Configuration

```apache
# /etc/apache2/conf-enabled/health-compass.conf
Alias /health /opt/health-compass/current
<Directory /opt/health-compass/current>
    Options -Indexes +FollowSymLinks
    AllowOverride None
    Require all granted
    DirectoryIndex index.html
    FallbackResource /health/index.html
</Directory>

ProxyPass /health/api/ http://127.0.0.1:8100/health/api/
ProxyPassReverse /health/api/ http://127.0.0.1:8100/health/api/
```

## Environment Configuration

Production secrets are stored in:

```
/etc/health-compass/backend.env  (root:root, 0600)
/etc/health-compass/secrets/     (root:root, 0600)
```

## Verification

```bash
# Backend directly
curl -s http://127.0.0.1:8100/health/api/health
curl -s http://127.0.0.1:8100/health/api/version
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8100/health/api/private/ping

# Through Apache
curl -s https://funti.cc/health/api/health
curl -s https://funti.cc/health/api/version

# Frontend still works
curl -s -o /dev/null -w '%{http_code}' https://funti.cc/health/
```
