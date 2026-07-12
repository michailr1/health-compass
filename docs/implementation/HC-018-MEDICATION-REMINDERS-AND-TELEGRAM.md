# HC-018 — Medication Reminders and Telegram Notifications

Status: `PLANNED / NOT IMPLEMENTED / NOT DEPLOYED`  
Planned placement: after HC-017 E3 security review; may be implemented before or in parallel with HC-017 F only after an explicit scheduling decision.  
Production impact of this document: none.

## 1. Product goal

Provide user-controlled medication reminders through Telegram without turning Telegram into a source of medical truth or a storage system for health records.

Health Compass remains the system of record for reminder plans, schedules, delivery attempts and user responses. Telegram is only an external delivery and interaction channel.

## 2. Initial user experience

A user can:

- connect a Telegram account through a verified, expiring, one-time linking flow;
- create a reminder for a user-confirmed medication or a manually entered reminder item;
- choose time, days, start date, optional end date and timezone behavior;
- pause, resume or stop a reminder;
- respond using `Принял`, `Отложить` or `Пропустить`;
- view the response history in Health Compass;
- choose how much information Telegram messages contain.

An absent Telegram response is recorded only as `no_response`. It is not automatically treated as a missed dose.

## 3. Notification privacy modes

### 3.1 Neutral mode

Neutral mode is the mandatory default.

Example:

```text
Пора выполнить запланированный приём.

[Принял] [Отложить] [Пропустить]
```

The message contains no medication name, dosage, diagnosis, indication or other health detail.

### 3.2 Detailed mode

Detailed mode is explicit opt-in.

Example:

```text
Пора принять препарат: Метформин
Дозировка: 500 мг
Приём: после еды

[Принял] [Отложить] [Пропустить]
```

Detailed messages may contain only fields explicitly confirmed by the user in the reminder plan:

- medication name;
- dosage text;
- quantity or form;
- route or timing instruction;
- user-authored note such as `после еды`.

Detailed messages must not include:

- diagnosis or reason for treatment;
- unrelated clinical history;
- AI-generated warnings or interpretations;
- inferred adherence conclusions;
- dose changes or medical recommendations.

### 3.3 Settings hierarchy

Health Compass must provide:

1. a profile-level default for all medication reminders;
2. an optional per-reminder override.

Canonical values:

```text
telegram_message_detail_level = neutral | detailed
```

Default value: `neutral`.

A per-reminder override may be `inherit`, `neutral` or `detailed`.

The effective setting is resolved when a delivery is created and stored with that delivery so later setting changes do not rewrite delivery history.

### 3.4 Detailed-mode warning and preview

Before enabling detailed mode, the user must acknowledge:

```text
Название препарата и детали приёма будут передаваться через Telegram
и могут отображаться в уведомлениях на заблокированном экране.
```

The settings screen must show a preview of the exact neutral and detailed message formats.

Switching from detailed back to neutral must take effect for all future unsent deliveries. Previously sent Telegram messages cannot be recalled reliably and must not be represented as deleted from Telegram.

## 4. System boundary

```text
Health Compass PostgreSQL
→ scheduler/outbox
→ Telegram Bot API
→ signed callback token
→ Health Compass API
→ PostgreSQL response record
```

Telegram must not be used as:

- the canonical reminder database;
- a medication catalogue;
- an authorization source for profile access;
- a source for changing confirmed medication data;
- a durable audit log.

## 5. Core entities

The detailed schema is deferred to implementation design, but the domain requires separate entities equivalent to:

```text
telegram_connections
medication_reminder_plans
medication_reminder_schedules
medication_reminder_deliveries
medication_intake_responses
```

Medication records and reminder plans are separate. Removing a reminder must not remove the medication from the health profile. Removing a medication must not silently rewrite historical reminder deliveries or responses.

## 6. Security and privacy invariants

- Telegram connection requires an authenticated Health Compass session.
- Linking uses a short-lived, single-use token and explicit confirmation in both channels where practical.
- Telegram chat identifiers are treated as personal data and protected by RLS.
- Callback payloads use opaque, signed, expiring identifiers and contain no medical text.
- A callback can affect only one expected delivery and is idempotent.
- Cross-profile and cross-workspace access is denied at the database boundary.
- A user can disconnect Telegram and revoke future deliveries without deleting medical records.
- Health-data consent and Telegram-notification consent are separate and independently revocable.
- Ordinary application logs and audit events contain no medication names, doses or message bodies.
- Delivery workers run with dedicated `NOBYPASSRLS` privileges and restricted database functions.
- Detailed mode never becomes enabled through migration, import, OCR or AI inference.
- No reminder is created automatically from OCR, documents, AI extraction or a medication list.
- No dose, schedule or instruction is changed automatically.

## 7. Scheduling semantics

Implementation must define and test:

- profile timezone and daylight-saving transitions;
- duplicate delivery prevention;
- restart-safe scheduling;
- transactional outbox behavior;
- retry limits and backoff;
- Telegram rate limiting and outage handling;
- pause/resume behavior;
- schedule edits without duplicate or lost deliveries;
- snooze idempotency;
- late responses;
- clock drift and worker concurrency.

A delivery record must distinguish at least:

```text
planned
queued
sent
failed
cancelled
responded
expired
```

Response values must distinguish at least:

```text
taken
snoozed
skipped
no_response
```

`no_response` is a system observation about interaction, not a clinical assertion that medication was missed.

## 8. Implementation slices

### R1 — Safe Telegram linking

- verified one-time linking;
- connection status and disconnect;
- separate notification consent;
- neutral test notification;
- RLS and negative cross-profile tests.

### R2 — Reminder plans and scheduler

- reminder plan and schedule model;
- timezone-safe scheduling;
- transactional outbox;
- dedicated worker role;
- duplicate prevention and restart recovery.

### R3 — Responses

- `Принял`, `Отложить`, `Пропустить`;
- signed callbacks;
- idempotent response handling;
- configurable snooze interval within bounded limits;
- history in Health Compass.

### R4 — Privacy modes and adherence view

- neutral/detailed profile default;
- per-reminder override;
- preview and explicit detailed-mode acknowledgement;
- reports based only on explicit responses;
- clear distinction between `skipped` and `no_response`.

### R5 — Optional extensions

- bounded repeat reminder after no response;
- course end handling;
- medication stock reminders;
- trusted-person notifications only with separate explicit consent and a new threat review.

## 9. Non-goals for the initial release

- prescribing medication;
- recommending or adjusting dosage;
- checking drug interactions;
- diagnosing non-adherence;
- automatically notifying doctors, relatives or caregivers;
- importing schedules from OCR without explicit review and creation;
- emergency alerts;
- replacing professional medical advice.

## 10. Merge and rollout gates

Before implementation can be merged:

- database contract and RLS negative tests exist;
- callback replay, expiry and cross-profile attacks are tested;
- scheduler concurrency and duplicate delivery behavior are tested;
- detailed-mode opt-in and neutral default are tested;
- logs are verified to contain no medical message content;
- exact-head CI passes;
- an independent security/privacy review finds no unresolved Critical or High issue.

Before production rollout:

- bot credentials and rotation procedure are provisioned;
- webhook or polling transport is hardened;
- Telegram outage and retry behavior are verified;
- privacy copy and consent withdrawal are manually accepted;
- a disposable-account end-to-end test passes;
- rollout is explicitly approved.

## 11. Stop conditions

Stop merge or rollout when:

- detailed mode is enabled by default;
- a detailed message can be sent without explicit acknowledgement;
- Telegram can modify medication or clinical records directly;
- an absent response is presented as a confirmed missed dose;
- callback tokens contain medication details;
- a callback can be replayed or used across profiles;
- workers have broad table mutation grants;
- medication names, doses or message bodies enter ordinary logs;
- schedule concurrency can create duplicate messages;
- disconnect or consent withdrawal does not stop future deliveries;
- production is changed without a controlled rollout decision.
