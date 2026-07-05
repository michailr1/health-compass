# Deployment — Health Compass

## Структура проекта

```
/opt/health-compass/
├── repo/              # Git-репозиторий (клон GitHub)
├── releases/          # Собранные production-версии
│   └── v0.1.0-YYYYMMDD_HHMMSS/
├── shared/            # Будущие общие конфиги
├── backups/           # Резервные копии
└── current -> releases/v0.1.0-YYYYMMDD_HHMMSS/  # Активный release (symlink)
```

## Развёртывание новой версии

### 1. Получить исходный код

```bash
# На локальной машине с gh auth
HOME=/root gh repo clone michailr1/health-compass /tmp/health-compass-repo
```

### 2. Внести изменения (при необходимости)

- `vite.config.ts` — `base: "/health/"` обязателен для работы под Apache Alias
- `index.html` — пути к assets должны начинаться с `/health/`

### 3. Собрать production build

```bash
cd /tmp/health-compass-repo
npm ci
npm run build
```

> **Важно:** Для production-сборки используется `npm ci`, а не `npm install`.
> `npm ci` гарантирует точное воспроизведение зависимостей из `package-lock.json`.

### 4. Скопировать на VPS

```bash
RELEASE_ID="v0.1.0-$(date +%Y%m%d_%H%M%S)"

# Репозиторий
rsync -a --delete /tmp/health-compass-repo/ root@funti.cc:/opt/health-compass/repo/

# Сборка
rsync -a /tmp/health-compass-repo/dist/ root@funti.cc:/opt/health-compass/releases/$RELEASE_ID/
```

### 5. Переключить symlink и перезагрузить Apache

```bash
ssh root@funti.cc
ln -sfn /opt/health-compass/releases/$RELEASE_ID /opt/health-compass/current
apache2ctl configtest && apache2ctl graceful
```

### 6. Проверить

```bash
curl -sS -D- https://funti.cc/health/
curl -sS -o /dev/null -w '%{http_code}' https://funti.cc/health/assets/index-*.css
curl -sS -o /dev/null -w '%{http_code}' https://funti.cc/health/assets/index-*.js
curl -sS -o /dev/null -w '%{http_code}' https://funti.cc/health/login
curl -sS -o /dev/null -w '%{http_code}' https://funti.cc/health/dashboard
```

## Конфигурация Apache

Файл: `/etc/apache2/conf-enabled/health-compass.conf`

```apache
Alias /health /opt/health-compass/current
<Directory /opt/health-compass/current>
    Options -Indexes +FollowSymLinks
    AllowOverride None
    Require all granted
    DirectoryIndex index.html
    FallbackResource /health/index.html
</Directory>
```

- `-Indexes` — отключает листинг директории
- `+FollowSymLinks` — разрешает следовать symlink `current`
- `FallbackResource /health/index.html` — SPA-маршрутизация

## Требования к окружению

- Node.js ≥ 20 (на машине сборки)
- npm ≥ 10
- Apache 2.4 (на VPS)
- Ubuntu 20.04 (focal)

## Политика управления зависимостями

- **npm** является основным package manager для production deployment.
- **`package-lock.json`** является authoritative lockfile для сборки.
- **`bun.lock`** пока сохранён для совместимости с Lovable (генератор исходного кода).
- Не следует обновлять оба lockfile независимо — это приведёт к расхождению зависимостей.
- При изменении зависимостей `package-lock.json` должен обновляться через `npm install <package>`.
- Для воспроизводимой сборки всегда используйте `npm ci` (не `npm install`).
