# 07 — Security & Threat Model Health Compass

Версия: 1.0 · Дата: 2026-07-08 · Связано: `02-technical-architecture.md` (§2 — разбор RLS-инцидента и RISK-001…012), `08-war-games.xlsx`, `11-adr/ADR-007`, `ADR-020`.

## 1. Актуальная поверхность (по коду)

Реализовано и оценено как корректное: PKCE+state+nonce в Google OIDC; `email_verified` обязателен; identity=(provider,subject); magic-link токены хэшируются, одноразовы, rate-limit 5/15мин на email и 20/15мин на IP внутри SECURITY DEFINER функции; app-роль не имеет прямых прав на `email_login_tokens`; серверные сессии с хэшем, HttpOnly/Secure/SameSite=Lax; одна транзакция на запрос; тесты отказываются работать с БД без суффикса `_test`; конфиг запрещает dev-auth и плейсхолдеры вне development.

Открытые дефекты: RISK-001…RISK-012 (полные описания в 02-technical-architecture §2.3) — устраняются в PHASE-01 (HC-002/003/005/006).

## 2. Модель угроз (актив → угроза → контроль → статус)

### 2.1 Аутентификация и сессии
| Угроза | Контроль | Статус |
|---|---|---|
| Кража session cookie (XSS) | HttpOnly + строгий CSP (добавить) + отсутствие inline-скриптов | CSP — HC-007 |
| CSRF на state-changing API | SameSite=Lax сейчас; при расширении API — double-submit CSRF с `csrf_token_hash` (колонка уже есть) | HC-007 |
| Session fixation / отсутствие ротации | Ротация токена при повышении привилегий и раз в N часов; `rotated_from_id` | HC-006 |
| Перебор magic-link | 256-бит токен + TTL 15 мин + одноразовость + rate limit | есть |
| Дожигание magic-link сканером почты | Интерстициал: GET показывает кнопку, POST потребляет | HC-006 (RISK-009) |
| Автослияние аккаунтов по email | Запрещено архитектурно (0018); явный поток linking с подтверждением обоих факторов | ADR-003, PHASE-10 |
| Dev-auth в production | validate_production() + запрет в env + smoke-тест prod «dev header → 401» | тест добавить, HC-001 |

### 2.2 Изоляция данных (главный актив)
| Угроза | Контроль | Статус |
|---|---|---|
| Cross-user/cross-profile утечка через пропущенный RLS-предикат | Инвариант «таблица создаётся вместе с политиками», CI-проверка: запрос в pg_catalog на таблицы без FORCE RLS | HC-002/CI |
| Рекурсия политик (повторение инцидента 54001) | Definer-роль BYPASSRLS (внедрено 0020/0021) + регрессионный тест INSERT под FORCE RLS | HC-002 |
| Self-grant / self-add | Закрыто политиками pp_owner_bootstrap_insert / wm_creator_bootstrap_insert | есть, тест HC-002 |
| Эскалация viewer→writer (dashboard_snapshots) | RISK-002: политика требует edit/owner | HC-003 |
| Утечка списка грантов профиля | RISK-003: сузить select | HC-003 |
| Забытый RLS-контекст в пуле | Транзакционный set_config(true) + одна транзакция на запрос; тест «без контекста SELECT пуст» | есть; тест HC-002 |
| Бывший владелец питомца сохраняет доступ | pet_ownership_history + отзыв pet_guardians при передаче | PHASE-11 |

### 2.3 Файлы и обработка документов (PHASE-04+)
Upload: whitelist mime+magic bytes, лимиты размера, ClamAV, защита от archive bomb (глубина/размер распаковки), хранение вне web-root с непредсказуемыми ключами, выдача через авторизованный endpoint (не статикой), sha256-дедупликация в пределах профиля. OCR — в отдельном процессе-воркере без сетевого доступа наружу (кроме явного Vision-флага), с таймаутами и ресурсными лимитами systemd.

### 2.4 AI-поверхность (PHASE-08)
Prompt injection: содержимое документов и raw wearable payload — всегда недоверенный ввод; в промт попадает как data-блок с явной пометкой, инструкции из него игнорируются; выход валидируется (нет ссылок на чужие profile_id — сравнение с контекстом запроса). Cross-profile: retrieval строго фильтруется profile_id ДО векторного поиска (metadata-фильтр, не post-filter). Human/pet confusion: раздельные промт-шаблоны и раздельные retrieval-индексы; в системном промте — вид/порода/возраст/вес; тест «человеческая норма не цитируется в pet-ответе». Внешний LLM: только по consent (kind=external_llm), с минимизацией (псевдонимизация ФИО), журналирование в ai_runs; embeddings удаляются при удалении документа и по deletion_requests. Опасные советы: правило-фильтр (дозировки, отмена лекарств, диагнозы) → блок + ai_safety_events + показ red-flag дисклеймера; emergency-эскалация по списку красных флагов.

### 2.5 Инфраструктура и агенты
| Угроза | Контроль |
|---|---|
| Действия на неправильном сервере (de.funti.cc) | Обязательный преамбул VPS-промта: hostname+IP+каталог+service; stop при несовпадении |
| Разрушительная миграция | Backup перед каждым `alembic upgrade`, запрет DROP без ADR, downgrade обязателен и протестирован в CI |
| Test/prod DB confusion | Суффикс `_test` (есть в conftest); в prod env — маркер ENVIRONMENT=production; VPS-агент сверяет имя БД из env с runbook |
| Секрет в shell history/логах | Агентам запрещено echo секретов; log sanitization: фильтр Authorization/cookie/token в логгере (HC-007) |
| Compromised coding agent | Агент не имеет prod-доступа by design; PR-review обязателен; CI без prod-секретов |
| Supply chain | dependency scanning (pip-audit, npm audit) в CI; lock-файлы уже есть |
| VPS hardening | ufw (только 80/443/SSH), fail2ban, автообновления безопасности, отдельный unix-пользователь сервиса, backend только на 127.0.0.1 (уже так) |

### 2.6 Данные: экспорт, удаление, восстановление
Export: асинхронный, ZIP с манифестом, ссылка с TTL, журнал в audit_log; запрет блокировать экспорт при downgrade (см. 12-product-strategy §5). Deletion: заявка → grace period → каскадный отчёт (таблица/число строк/embeddings/файлы/бэкапы-ротация) → фиксация в deletion_requests. Backup: ежедневный pg_dump + файловое хранилище, шифрование, ХРАНЕНИЕ ВНЕ VPS, ежемесячная проверка restore на staging (runbook). Account recovery: наличие двух identity (Google+email) — основной механизм; журнал recovery-действий; наследование доступа (легаси-контакт) — v2, ADR-задел.

## 3. Матрица разрешений (целевая, PHASE-10)
| Действие | owner | edit | analyze | view |
|---|---|---|---|---|
| Читать данные профиля | ✓ | ✓ | ✓ | ✓ |
| Писать измерения/документы | ✓ | ✓ | — | — |
| Подтверждать извлечения | ✓ | ✓ | — | — |
| AI-анализ, отчёты | ✓ | ✓ | ✓ | — |
| Управлять доступами | ✓ | — | — | — |
| Экспорт/удаление | ✓ | — | — | — |

## 4. Порядок работ по безопасности
PHASE-01: RISK-001/002/003/006 + RLS-тесты + docs. PHASE-02: CI-скан политик, Sentry со scrubbing, backup+restore runbook, CSP/CSRF/лог-санитайзинг (HC-007). PHASE-04: файловый контур. PHASE-07: шифрование wearable-токенов (libsodium sealed box, ключ в env), мониторинг sync. PHASE-08: AI-safety контур целиком до любого реального LLM-ответа пользователю.
