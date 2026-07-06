# Backend Rollback

## Standard Rollback (no data loss)

```bash
# 1. Stop backend
systemctl stop health-compass-api
systemctl disable health-compass-api

# 2. Restore Apache configuration
cp /opt/health-compass/backups/health-compass.conf.bak \
  /etc/apache2/conf-enabled/health-compass.conf
apache2ctl configtest && systemctl reload apache2

# 3. Stop PostgreSQL 16 container (volume preserved)
cd /opt/health-compass/runtime/postgres
docker compose -f compose.yml down

# 4. Verify frontend
curl -s -o /dev/null -w '%{http_code}' http://localhost/health/

# 5. Verify Marzban
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/
```

## Database Rollback

The database volume is **never automatically deleted** during rollback.

To remove the database (only after explicit confirmation):

```bash
# Drop database and roles
docker exec -i health-compass-pg16 psql -U postgres << 'EOSQL'
DROP DATABASE IF EXISTS health_compass;
DROP DATABASE IF EXISTS health_compass_test;
DROP ROLE IF EXISTS health_compass_app;
DROP ROLE IF EXISTS health_compass_migrator;
DROP ROLE IF EXISTS health_compass_test_app;
DROP ROLE IF EXISTS health_compass_test_migrator;
EOSQL

# Remove volume (ONLY after confirmation)
docker volume rm health-compass-pg16
```

## Full Rollback (remove everything)

```bash
# 1. Stop backend
systemctl stop health-compass-api
systemctl disable health-compass-api
rm /etc/systemd/system/health-compass-api.service
systemctl daemon-reload

# 2. Restore Apache
cp /opt/health-compass/backups/health-compass.conf.bak \
  /etc/apache2/conf-enabled/health-compass.conf
a2dismod proxy proxy_http headers
apache2ctl configtest && systemctl reload apache2

# 3. Stop and remove PG16
cd /opt/health-compass/runtime/postgres
docker compose -f compose.yml down

# 4. Verify
curl -s -o /dev/null -w '%{http_code}' http://localhost/health/
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/
```
