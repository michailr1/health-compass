# 2026-07-13 — HC-018 Medication Reminders planned

Status: `DOCUMENTED / PLANNED / NOT IMPLEMENTED / NOT DEPLOYED`.

## Decision

Medication reminders through Telegram are accepted as a separate future Health Compass stage:

```text
HC-018 — Medication Reminders and Telegram Notifications
```

The stage is planned after HC-017 E3 security review and must not be mixed into the E3 correction/void/erasure database contract.

## Accepted product requirements

- Telegram is only a delivery and interaction channel.
- Health Compass remains the system of record.
- The user controls reminder creation, schedule and notification content.
- Telegram responses include `Принял`, `Отложить` and `Пропустить`.
- Lack of response is stored as `no_response`, not as a confirmed missed dose.
- OCR, AI, imports and medication lists cannot create reminders automatically.
- Health Compass does not prescribe or change medication dosage.

## Accepted privacy modes

```text
telegram_message_detail_level = neutral | detailed
default = neutral
```

The user can configure:

1. a profile-level default;
2. a per-reminder override: `inherit | neutral | detailed`.

Neutral notification example:

```text
Пора выполнить запланированный приём.
```

Detailed notification may show only fields explicitly confirmed by the user, such as medication name, dosage text and a user-authored instruction.

Detailed mode requires:

- explicit opt-in;
- a warning that details are transmitted through Telegram and may appear on a locked screen;
- a preview of the exact message format.

Diagnosis, unrelated medical history, AI interpretation and inferred adherence conclusions are excluded from Telegram messages.

## Canonical documents

- `docs/PROJECT-PLAN.md`, version 2.7;
- `docs/implementation/HC-018-MEDICATION-REMINDERS-AND-TELEGRAM.md`.

## Repository and production impact

This decision changes documentation only.

```text
CODE UNCHANGED
DATABASE UNCHANGED
PRODUCTION UNCHANGED
HC-017 E3 REMAINS THE NEXT IMPLEMENTATION STAGE
```
