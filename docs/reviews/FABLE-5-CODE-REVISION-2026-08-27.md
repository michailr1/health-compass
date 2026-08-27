# Fable 5 — ревизия кода Health Compass после паузы

Дата: 2026-08-27  
Проверенный repository HEAD: `a9634a2` (main; application baseline `c7dcae4da3860f6f73224f639be78424c6f3fa63`)  
Repository Alembic head: `0062` (один head, линейный)  
Production (по каноническим docs): `fb1e7a2f70c4b24edbdff6dfd2889c34a63e2c75`, Alembic `0058`, upload выключен, workers не запущены  
Вердикт: **`HEALTHY / CONTINUE PLAN`** — блокирующих findings нет

## 1. Область проверки

Полная ревизия после ~5 недель паузы: HC-016 (permanent erasure), весь контур
HC-017 (Slices B–E3: encrypted intake, scanner, quotas/reconciliation,
safe rendering, OCR candidates, human review, Lab drafts, confirmed
observations, lifecycle), миграции `0049–0062`, worker-процессы, storage и
crypto-слой, frontend, CI, открытые PR и согласованность документации.

Методика: чтение ключевых модулей + автоматический аудит инвариантов по
живой БД, мигрированной до `0062`, + полный локальный прогон всех
CI-эквивалентных наборов.

## 2. Результаты тестов (локально, CI-эквивалентное окружение)

- backend unit (`-m "not integration"`, без DB env): **203 passed, 14 skipped**;
- PostgreSQL integration/RLS: **121 passed**;
- migration boundary: **passed**; полный цикл `head → base → head` в
  изолированной БД: **passed**;
- Ruff и compileall: чисто;
- frontend: lint **0 errors**, typecheck **чисто**, **59 tests passed**, build успешен.

## 3. Подтверждённый SQL-аудит инвариантов (head 0062)

- **Все ~75 `SECURITY DEFINER` функций** принадлежат
  `health_compass_rls_definer`, имеют `search_path=''`, `row_security=off`
  и не имеют `PUBLIC EXECUTE` — кроме двух legacy-исключений (REV-02 ниже).
- **Worker-роли (`worker`, `renderer`, `reconciler`, `ocr_worker`) имеют
  ноль прямых табличных grants** — только EXECUTE на строго свои
  claim/heartbeat/complete/fail функции. Матрица разделения ролей чистая.
- Все пользовательские/медицинские таблицы: `ENABLE + FORCE RLS`.
  Без RLS остаются только `alembic_version`, глобальные read-only словари и
  три legacy-таблицы `0001` (REV-01).
- Column-grant на `users` (только `display_name`, `updated_at`) сохранён.

## 4. Подтверждённые сильные стороны нового кода

- **Crypto-слой** (`app/storage/encrypted_objects.py`): AES-256-GCM с AAD,
  привязанным к `document_id` + роли артефакта; атомарная эксклюзивная
  публикация через `link()`; `O_NOFOLLOW`, single-link проверки; проверка
  прав key-файла; поток plaintext до аутентификации разрешён только
  malware-сканеру и явно задокументирован.
- **Renderer/OCR sandbox** (`app/rendering/safe_render.py`): memfd с
  sealing, `RLIMIT_CPU/AS/FSIZE/NOFILE/NPROC`, фиксированный `env`,
  `start_new_session` + kill process group, без shell; пользовательские
  значения не становятся аргументами исполняемых файлов.
- **Workers** работают только через definer-функции с lease/heartbeat и
  идемпотентными ключами; fail-политика fail-closed.
- **Upload** возможен только при `DOCUMENT_UPLOAD_ENABLED` **и**
  `is_development` — включить загрузку в production одним env-флагом
  структурно невозможно; квоты резервируются в транзакции; rollback-cleanup
  зашифрованного объекта при откате.
- **E2/E3**: подтверждение и lifecycle только через definer-функции с
  `expected_lifecycle_version`, идемпотентностью, явными acknowledgements и
  контролируемыми SQLSTATE (`HC404/409/422/428`); immutable snapshots;
  erasure owner-only.
- Route-table uniqueness, migration-cycle тест, full-source frontend gates —
  всё из HC-015 живо и расширено на новые таблицы.

## 5. Findings

Блокирующих нет. Все — Low/процессные.

| ID | Severity | Описание | Рекомендация |
|---|---|---|---|
| REV-01 | Low | Legacy-таблицы `0001` `audit_events`, `processing_jobs`, `service_metadata`: без RLS, с полным CRUD grant для app-роли, **нигде не используются кодом** (модели мертвы) | Отдельная cleanup-миграция: удалить таблицы и модели либо отозвать grants; негативный тест |
| REV-02 | Low | `app_issue_email_login_token` и `app_consume_email_login_token` (из `0019`) сохраняют `search_path=health_compass, pg_temp` вместо инвариантного `search_path=''` | Выровнять в следующей hardening-миграции; практической эксплуатации нет (фиксированная схема, `pg_temp` последним) |
| REV-03 | Info | Trigger-функции `sync_clinical_dictionary_concept`, `sync_clinical_review_legacy_flag` формально имеют `PUBLIC EXECUTE` | Безвредно (trigger-функции невызываемы напрямую); можно отозвать для единообразия |
| REV-04 | Process | Draft PR `#71` (HC-019): на финальном head `e7aaedf` **нет ни одного CI check** | Перед review/merge прогнать CI на exact head — это же требование стоит в самом плане |
| REV-05 | Process | Открытые устаревшие PR `#25` (HC-013, база до HC-015 — код невозможно мержить, в плане уже помечен как «reimplement from main») и `#17` (docs) | Закрыть оба с комментарием; HC-013 реализовывать заново с актуального main, когда дойдёт очередь |
| REV-06 | Info | На главной `Dashboard` при пустом профиле CTA «Подключить источник» ведёт в тупик (интеграций нет) | Уже закрывается HC-019 (PR #71) по принятым решениям от 2026-07-13 |

## 6. Состояние продукта и «где мы остановились»

Развёрнуто и принято в production (`fb1e7a2`, Alembic `0058`):
auth-контур, профили/RLS, Clinical Context + словари, erasure (HC-016),
задеплоенный, но **выключенный** фундамент документов B–E2.

В репозитории сверх production: HC-017 E3 (correction/void/erasure
lifecycle, `0059–0062`) — merged, CI verified, **NOT DEPLOYED**.

Не существует ещё нигде: работающий production-конвейер документов
(workers не запущены, upload выключен), metric dynamics (Slice F),
HC-018 reminders, HC-019 UI (draft).

## 7. Рекомендуемый порядок дальнейших шагов

1. **HC-019** (навигация ≤5 пунктов, «Анализы», «Сон», empty states) —
   draft PR `#71` уже реализует принятые решения: прогнать CI на exact head,
   review, merge. Малый риск, видимая ценность.
2. **Решение о rollout E3** (`0059–0062`) — отдельное backup-first
   развёртывание, чтобы репозиторий и production снова совпали.
3. **Операционный запуск конвейера документов** — самый крупный кусок
   PHASE-03: поднять scanner/renderer/reconciler/OCR сервисы в production,
   операционная приёмка, затем включение upload (потребует изменения кода —
   сейчас upload намеренно заперт на development).
4. **Slice F Metric Dynamics** — после приёмки E3.
5. Мелкие REV-01/REV-02 — одной hardening-миграцией при следующем
   backend-изменении.
6. Затем по плану: HC-018 reminders, HC-013 sessions UI (заново), Оура/сон.

## 8. Ограничения ревизии

Не проверялись runtime-проверкой: фактическое production-состояние
(SHA/Alembic взяты из канонических docs), реальные SMTP/OIDC, systemd/Apache
конфигурация VPS, поведение ClamAV/poppler/tesseract на реальных файлах.
