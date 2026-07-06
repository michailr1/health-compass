# Authentication Roadmap

## Current State (Stage 2A)

- No real authentication implemented
- All protected endpoints return 401 Unauthorized
- Auth-ready infrastructure in place:
  - `app/core/security.py` — dependency injection for future OIDC
  - `get_current_user()` — placeholder that always raises 401
  - `require_authentication()` — semantic alias for route dependencies
- Configuration parameters for future OIDC in `app/core/config.py`:
  - `oidc_issuer`
  - `oidc_client_id`
  - `oidc_audience`

## Planned: Authentik Integration

### Recommended Provider: Authentik

Authentik is an open-source identity provider that supports:
- OIDC and OAuth2
- LDAP
- MFA/TOTL/WebAuthn
- SCIM provisioning
- RBAC/ABAC

### Integration Steps (Future Stage)

1. Deploy Authentik (Docker Compose, separate from Health Compass)
2. Create OIDC application in Authentik
3. Configure backend:
   - Set `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_AUDIENCE`
   - Implement JWT validation in `security.py`
   - Replace `get_current_user()` with real token validation
4. Configure frontend:
   - Add OIDC client library (e.g., oidc-client-ts)
   - Implement login redirect to Authentik
   - Handle token refresh
5. Add Row-Level Security (RLS) for multi-user data isolation
6. Close public API documentation

### Security Constraints

- No real user data before authentication and RLS are in place
- No medical, genetic, or personal data before Stage 3+
- API documentation must be restricted before adding user-data endpoints
