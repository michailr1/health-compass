# HC-015 — Safari Magic Link Origin Regression

Status: `CONFIRMED / HOTFIX REQUIRED / PRODUCTION NOT CHANGED`

Date: 2026-07-11

## Production symptom

A real Email Magic Link opened successfully on iPhone Safari and displayed the scanner-safe confirmation page. Submitting the confirmation form returned:

```json
{"detail":"Invalid request origin"}
```

The rejection occurs before form parsing and before `app_consume_email_login_token`, so the token is not consumed by this failed attempt.

## Diagnostic evidence

Production configuration normalizes to:

```text
https://health.funti.cc
```

Synthetic POST checks against `/api/auth/email/consume`:

| Origin | Result |
|---|---:|
| absent | 303 |
| `https://health.funti.cc` | 303 |
| `https://health.funti.cc/` | 303 |
| `https://health.funti.cc:443` | 403 |
| `null` | 403 |
| `https://evil.example` | 403 |

The diagnostic proves that the current comparison rejects two browser-compatible representations: an explicit default HTTPS port and the opaque origin value `null`. It does not prove which one Safari sent in the real request because the effective request Origin was not captured.

## Root cause

`_origin_is_allowed()` performs string equality against the origin derived from `FRONTEND_URL`:

```python
origin.rstrip("/") == "https://health.funti.cc"
```

This does not normalize default ports and treats literal `null` as an ordinary hostile origin.

This is a code defect, not a configuration-only defect.

## Required safe hotfix

1. Normalize scheme, hostname and effective port before origin comparison, so `https://health.funti.cc` and `https://health.funti.cc:443` are equivalent.
2. Do not blindly accept `Origin: null`.
3. Bind the interstitial GET to the subsequent POST with a short-lived random browser-confirmation value:
   - set a Secure, HttpOnly, SameSite cookie on GET;
   - render the same random value in a hidden form field;
   - on POST, require constant-time equality for `Origin: null`;
   - reject missing or mismatched confirmation for `Origin: null` before token consumption.
4. Preserve rejection of hostile origins such as `https://evil.example`.
5. Preserve scanner safety: GET must never consume the token.
6. Preserve one-time token replay rejection and query/token log redaction.

## Acceptance tests

- GET shows the interstitial, sets the short-lived confirmation cookie and does not consume the token.
- same-origin POST succeeds;
- explicit `:443` origin succeeds;
- `Origin: null` succeeds only with a matching confirmation cookie + hidden field;
- `Origin: null` without the binding returns 403 and leaves the token unused;
- cross-origin POST returns 403 even with a valid token;
- replay is rejected;
- raw token and confirmation values do not appear in application, Uvicorn or proxy logs.

## Current project status

```text
HC-015: DEPLOYED / AUTOMATED VERIFIED / MANUAL MAGIC-LINK SMOKE FAILED
```

Google login remains manually verified. Full HC-015 closure is blocked until this hotfix is merged, deployed and the real Magic Link GET → POST → replay flow passes on iPhone Safari.
