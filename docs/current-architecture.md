# Current Architecture — Health Compass

## Статус: Этап 1 — Git-based deployment

### Компоненты

| Компонент | Статус | Детали |
|---|---|---|
| Frontend | ✅ Работает | React SPA (Vite + shadcn/ui), сборка из GitHub |
| Backend | ❌ Отсутствует | Планируется |
| База данных | ❌ Отсутствует | PostgreSQL доступен на VPS, но не используется |
| Авторизация | ❌ Отсутствует | Встроенный mock-логин в SPA |
| Reverse proxy | ✅ Apache 2.4 | HTTP→HTTPS redirect, Alias /health |
| HTTPS | ✅ Let's Encrypt | Сертификат для funti.cc |
| CI/CD | ❌ Отсутствует | Ручной деплой через rsync |

### Схема deployment

```
GitHub (michailr1/health-compass)
  ↓ gh repo clone
Локальная сборка (npm install → npm run build)
  ↓ rsync
VPS: /opt/health-compass/
  ├── repo/          ← Git-репозиторий
  ├── releases/      ← Собранные версии
  └── current → releases/v0.1.0-*/   ← Symlink
       ↓ Apache Alias
https://funti.cc/health/
```

### HTTP-цепочка

```
Пользователь → https://funti.cc/health/
  → Apache *:443 (SSL)
  → Alias /health → /opt/health-compass/current
  → FallbackResource /health/index.html (SPA)
  → Статические файлы из releases/
```

### Связанные сервисы (не Health Compass)

| Сервис | Порт | Назначение |
|---|---|---|
| Marzban | 8000 (localhost) | VPN-панель, Docker |
| PostgreSQL | 5432 (localhost) | СУБД, не используется Health Compass |
| Roundcube | — | Email-клиент (неактивен) |

### Ограничения текущей архитектуры

1. Нет backend — все данные статические/заглушки
2. Нет авторизации — mock-логин в SPA
3. Нет БД — PostgreSQL не подключён
4. Нет CI/CD — ручной деплой
5. Нет изоляции — Apache + Marzban + PostgreSQL на одном VPS
6. Node.js 14 на VPS — устарел, сборка ведётся локально

### План следующих этапов

1. ✅ Git-based deployment (текущий этап)
2. Backend API (FastAPI/Node)
3. PostgreSQL + миграции
4. Авторизация (JWT / Authentik)
5. Docker Compose для всей системы
6. CI/CD (GitHub Actions)
7. Отдельный поддомен / выделенный reverse proxy
