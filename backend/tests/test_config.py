from __future__ import annotations

import pytest

from app.core.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+asyncpg://app:secret@db/app",
        "database_migrator_url": "postgresql+psycopg://migrator:secret@db/app",
        "oidc_issuer": "https://accounts.google.com",
        "oidc_client_id": "client-id",
        "oidc_client_secret": "client-secret",
        "oidc_redirect_uri": "https://app.example/health/api/auth/callback",
        "allow_dev_auth": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_configuration_is_valid_when_complete() -> None:
    production_settings().validate_production()


def test_production_rejects_dev_auth() -> None:
    with pytest.raises(ValueError, match="ALLOW_DEV_AUTH"):
        production_settings(allow_dev_auth=True).validate_production()


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("database_url", "DATABASE_URL"),
        ("database_migrator_url", "DATABASE_MIGRATOR_URL"),
        ("oidc_client_id", "Google OIDC settings"),
        ("oidc_client_secret", "Google OIDC settings"),
        ("oidc_redirect_uri", "OIDC_REDIRECT_URI"),
    ],
)
def test_production_rejects_missing_required_settings(field: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        production_settings(**{field: ""}).validate_production()
