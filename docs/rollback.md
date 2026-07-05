# Rollback — Health Compass

## Быстрый rollback (symlink)

Если новая версия не работает:

```bash
ssh root@funti.cc

# Узнать предыдущий release
ls -lt /opt/health-compass/releases/

# Переключить symlink на предыдущий
ln -sfn /opt/health-compass/releases/v0.1.0-20260706_015839 /opt/health-compass/current

# Проверить и перезагрузить Apache
apache2ctl configtest && apache2ctl graceful

# Проверить
curl -sS -D- https://funti.cc/health/
```

## Полный rollback (из backup)

Если структура releases повреждена:

```bash
ssh root@funti.cc

# Восстановить файлы из backup
BACKUP_DIR="/opt/health-compass/backups/pre-git-20260706_015116"
cp -a $BACKUP_DIR/health-compass /var/www/health-compass

# Восстановить конфигурацию Apache
cp $BACKUP_DIR/health-compass.conf /etc/apache2/conf-enabled/health-compass.conf

# Проверить и перезагрузить
apache2ctl configtest && apache2ctl graceful

# Проверить
curl -sS -D- https://funti.cc/health/
```

## Проверка после rollback

```bash
# HTTP-статус
curl -sS -D- -o /dev/null https://funti.cc/health/

# Assets
curl -sS -o /dev/null -w '%{http_code}' https://funti.cc/health/assets/index-*.css
curl -sS -o /dev/null -w '%{http_code}' https://funti.cc/health/assets/index-*.js

# SPA-маршруты
curl -sS -o /dev/null -w '%{http_code}' https://funti.cc/health/login
curl -sS -o /dev/null -w '%{http_code}' https://funti.cc/health/dashboard

# Apache error log
tail -10 /var/log/apache2/error.log

# Marzban (не должен быть затронут)
curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/
docker ps --format '{{.Names}} {{.Status}}'
```

## Контрольные суммы оригинальных файлов (для верификации)

Хранятся в: `/opt/health-compass/backups/pre-git-20260706_015116/checksums.txt`
