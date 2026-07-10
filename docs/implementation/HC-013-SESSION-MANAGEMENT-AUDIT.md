# HC-013 — Session Management Audit

Status: `IN PROGRESS`  
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

No schema migration is required for the first implementation slice.

## Security invariants

- raw session tokens are never returned by an API or stored in the database;
- list responses expose only the session UUID and presentation metadata;
- only the authenticated session owner can list or revoke sessions;
- rotation changes the token hash atomically and invalidates the old cookie immediately;
- rotation keeps the same session UUID and expiration boundary;
- revoked and expired sessions are excluded from the active list;
- revoking the current session removes the browser cookie;
- outsider access returns 401/404 according to the existing auth boundary;
- production rollout is out of scope.

## Proposed API

```text
GET    /auth/sessions
DELETE /auth/sessions/{session_id}
POST   /auth/sessions/current/rotate
```

## Frontend

Extend `SignInMethodsPage` with an `ActiveSessionsCard`:

- current session badge;
- device/browser summary from user agent;
- IP address when available;
- created and expiry timestamps;
- `Обновить текущий сеанс` action;
- `Завершить сеанс` action for each session;
- clear warning when ending the current session logs the browser out.

## Tests

- current-session detection;
- active-only filtering;
- owner-only revocation;
- atomic token rotation;
- old token invalid after rotation;
- current-session revocation clears cookie;
- frontend presentation helpers and action states.
