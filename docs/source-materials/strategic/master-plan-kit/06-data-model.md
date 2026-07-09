# 06 — Модель данных Health Compass

Версия: 1.0 · Дата: 2026-07-08 · Диаграмма: `06-data-model-diagram.mmd` / `.pdf`
Обозначения: [есть] — реализовано в ветке; [MVP] — до/в составе MVP; [v2] — после MVP.

## 0. Принципы

1. Tenant boundary = `workspace_id`; profile boundary = `profile_id` (human) или `pet_id` (vet). Каждая пользовательская таблица несёт одну из этих границ и покрыта RLS (ENABLE+FORCE) в миграции создания.
2. Разделение слоёв: **факт** (исходный документ/сырое событие) → **извлечение** (structured, с confidence и версией модели) → **подтверждение человеком** → **интерпретация/рекомендация AI** (отдельные таблицы, всегда с provenance). Ни один слой не перезаписывает предыдущий.
3. История иммутабельна: исправления — новые версии (`document_extractions.version`, `extraction_corrections`), не UPDATE поверх.
4. Human и Pet: общая инфраструктура (files, timeline-механика, permissions, audit), но раздельные доменные таблицы и раздельные справочники норм (ADR-018). `profile_type` в одной таблице отвергнут: слишком легко перепутать нормы в JOIN и в AI-контексте.
5. Retention/soft delete: медицинские данные — soft delete + отложенный hard delete по `deletion_requests`; audit_log — append-only.

## 1. Identity и доступ [есть, доработка PHASE-01/10]

| Таблица | Ключевые поля | Границы/RLS | Примечания |
|---|---|---|---|
| users | id, email(non-unique), display_name, status | self (id = current_user) | email — контактный атрибут, не ключ идентичности |
| user_identities | user_id, provider, subject UNIQUE(provider,subject), issuer, claims JSONB, last_seen_at | self | lookup — только через definer-функцию |
| auth_sessions | user_id, session_token_hash UNIQUE, csrf_token_hash, ip, user_agent, expires_at, revoked_at | select/update по session_hash-контексту; insert self | добавить rotated_from_id [MVP] для ротации |
| email_login_tokens | email, token_hash UNIQUE, expires_at, used_at, requested_ip | доступ только через SECURITY DEFINER функции | app-роль без прямых прав — верно |
| workspaces | id, name, slug, created_by_user_id | select через членство; insert self-created | |
| workspace_members | workspace_id, user_id, role(owner/member) | self-select; insert bootstrap-owner; [MVP] insert по invitation | UNIQUE(workspace_id,user_id) |
| health_profiles | workspace_id, owner_user_id, display_name, birth_date [MVP], sex [MVP] | select can_view; insert owner+member | человеческий домен |
| profile_permissions | profile_id, user_id, permission(owner/edit/analyze/view) | self-select; owner-select [MVP]; insert bootstrap-owner + [MVP] grant by owner | UNIQUE(profile_id,user_id) |
| invitations | workspace_id/profile_id, email, token_hash, role, expires_at, accepted_by | issuer-select; consume через definer-функцию [MVP] | модель есть, поток не реализован |
| consents [MVP] | user_id, subject_type, subject_id, kind(ai_processing/external_llm/sharing/export), granted_at, revoked_at | self | обязательна до внешнего LLM |
| audit_log [MVP] | actor_user_id, workspace_id, profile_id/pet_id, action, entity, entity_id, meta JSONB, created_at | append-only; select owner | партиционировать по месяцу [v2] |

## 2. Документы и файлы [MVP: PHASE-04]

| Таблица | Ключевые поля | Примечания |
|---|---|---|
| medical_documents | profile_id, doc_type, title, document_date, facility_id, practitioner_id, status(uploaded/processing/needs_review/confirmed), created_by | «карточка» документа в timeline |
| document_files | document_id, storage_key, sha256, size, mime, av_status, original_filename | байты — в object storage, не в БД |
| document_extractions | document_id, version, engine(model+version), payload JSONB, confidence, status | иммутабельные версии |
| extraction_corrections | extraction_id, field_path, old_value, new_value, corrected_by, created_at | история правок человеком |
| provenance | entity_type, entity_id, source_kind(document/wearable/manual/ai), source_id, extracted_by, confirmed_by | сквозная ссылка «откуда взялось значение» |

## 3. Human Health — ядро [MVP: PHASE-05/06], расширения [v2]

Лаборатория: `lab_test_definitions` (справочник: код LOINC-подобный, название, единицы, конверсии; **human-only**), `lab_reference_ranges` (test_id, lab_id nullable, sex, age_min/max, low, high, units), `lab_reports` (profile_id, document_id, taken_at, lab_facility), `lab_result_items` (report_id, test_id, value_raw, value_si, units_raw, flag, confidence, confirmed_at).

Измерения: `measurement_types` (справочник, custom per workspace), `measurements` (profile_id, type_id, value, unit, measured_at, source=provenance). Временной ряд — обычная таблица + BRIN(measured_at).

События/timeline: `medical_events` (profile_id, event_type, occurred_at, title, document_id, payload JSONB, verified) — материализованная лента; всё остальное (визиты, операции, вакцинации `vaccinations`, диагнозы `conditions/diagnoses`, аллергии `allergies`, лекарства `medications`+`medication_schedules`+`medication_intakes`, симптомы `symptoms/symptom_entries`) публикует событие в timeline через outbox [v2 для полноты, MVP — документы+анализы+измерения].

Образ жизни [v2]: nutrition_logs/meals/foods/recipes/hydration; workouts/exercises/workout_sets; sleep_sessions; habits/habit_entries. Генетика [v2, отдельный этап]: genetic_files (шифрование at rest, отдельные права), genetic_variants, genetic_annotations (версия базы знаний), genetic_interpretations (evidence_level, revocable).

Носимые устройства [MVP: Oura, PHASE-07]: `wearable_connections` (profile_id, provider, oauth токены шифрованные, status), `wearable_sync_runs` (connection_id, cursor, started/finished, stats, error), `wearable_raw_events` (connection_id, provider_event_id UNIQUE per connection — идемпотентность, payload JSONB, received_at), `normalized_metrics` (profile_id, metric_key, value, start_at, end_at, tz, source_run_id, schema_version). Reconciliation: raw хранится всегда, normalized можно перестроить.

## 4. AI [PHASE-08]

ai_conversations (profile_id|pet_id, user_id), ai_messages (role, content, redactions), ai_runs (model, prompt_version, input_hash, cost, latency), ai_evidence (run_id → entity_type/entity_id/цитата — каждое утверждение ассистента ссылается на данные), ai_feedback, ai_safety_events (run_id, kind: red_flag/blocked_advice/injection_detected, payload). Embeddings: `document_chunks` (document_id, chunk, embedding vector, model_version) — удаляются каскадно с документом и по deletion_requests.

## 5. Pet Health [PHASE-11, архитектурно закладывается сейчас]

pets (workspace_id, species_id, breed_id, name, sex, birth_date/approx_age, neutered, microchip, lifestyle), pet_guardians (pet_id, user_id, role), pet_ownership_history; pet_species/pet_breeds (справочники); pet_vet_visits, pet_conditions, pet_diagnoses, pet_medications(+intakes; поле dose_per_kg), pet_vaccinations, pet_parasite_treatments, pet_lab_reports/pet_lab_results + **pet_lab_reference_ranges (по species/breed/age/sex — полностью отдельный справочник)**, pet_measurements (BCS/MCS и др.), pet_feeding_logs/pet_foods, pet_activity_logs, pet_behavior_logs, pet_litter_logs, pet_sleep_sessions, pet_devices/pet_device_metrics, pet_care_tasks. RLS: границы через pet_guardians (аналог profile_permissions), те же паттерны политик и definer-функций (`app_can_view_pet`).

## 6. Управление продуктом [PHASE-12]

plans, subscriptions, entitlements (plan_id → feature_key → limit), feature_flags, quotas/usage_counters (workspace_id, key, period, used), billing_events, exports (запрошенные архивы; статус, storage_key, expires_at), deletion_requests (subject, scope, requested_at, executed_at, report JSONB).

## 7. Индексация и целостность (общие правила)

* FK всегда с явным `ON DELETE` (CASCADE только внутри агрегата; между агрегатами — RESTRICT + deletion_requests).
* Уникальность: identity(provider,subject); wm(workspace,user); pp(profile,user); raw events (connection, provider_event_id).
* Индексы под RLS-предикаты: (user_id), (profile_id), (workspace_id) на каждой таблице границы.
* JSONB — только для payload переменной структуры (claims, extraction payload, raw events); типизированные значения — в колонках.
