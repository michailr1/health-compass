# HC-013 — Session Management Audit

Status: `IMPLEMENTED — CI IN PROGRESS`  
Base: `main` at `61f61a1051c397966b4dae508eb12b7a70e14078`  
Production: untouched

## Goal

Provide a security-account UI and API for:

- listing active sessions;
- identifying the current session;
- revoking another session;
- revoking the current session with cookie removal;
- rotating the current session token without changing the session identity.

## Existing foundation

`health_compass.auth_sessions` already stores:

- stable session UUID;
- user ID;
- hashed session token;
- IP address;
- user agent;
- creation and expiration timestamps;
- optional revocation timestamp.

No schema migration is required. Existing RLS policies already scope SELECT and UPDATE to `user_id = app_current_user_id()`, and FORCE RLS is preserved.

## Implemented security invariants

- raw session tokens are never returned by an API or stored in the database;
- list responses expose only the session UUID and presentation metadata;
- only the authenticated session owner can list or revoke sessions;
- revoked and expired sessions are excluded from the active list;
- rotation replaces only `session_token_hash` and keeps the same session UUID and expiry;
- the old cookie becomes invalid after transaction commit;
- revoking the current session sets `revoked_at` and removes the browser cookie;
- revocation uses UPDATE, not physical DELETE;
- browser-session endpoints reject development-header authentication without a cookie;
- production rollout is out of scope.

## Implemented API

```text
GET    /auth/sessions
DELETE /auth/sessions/{session_id}
POST   /auth/sessions/current/rotate
```

The list returns:

- session UUID;
- current-session flag;
- IP address;
- user agent;
- creation and expiration timestamps.

No token or token hash is serialized.

## Implemented frontend

The existing `/app/sign-in-methods` route now renders a composed account-security page:

- existing sign-in methods UI remains unchanged;
- `ActiveSessionsCard` is rendered below it;
- current session badge;
- mobile/desktop and browser summary;
- IP address when available;
- created and expiry timestamps;
- `Обновить текущий сеанс` action;
- `Завершить сеанс` for other sessions;
- `Выйти на этом устройстве` for the current session;
- explicit confirmation before revocation.

## Tests and CI

Added coverage for:

- browser-cookie requirement;
- no raw token exposure;
- response contract;
- browser/device presentation labels;
- FORCE RLS on `auth_sessions`;
- existing owner-only SELECT and UPDATE policies;
- app-role SELECT and UPDATE privileges;
- explicit lint coverage for all new frontend files.

## Out of scope

- geolocation by IP;
- device fingerprinting;
- push/email alerts for new sessions;
- changing the global session TTL;
- production rollout.
