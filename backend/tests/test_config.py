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
        "oidc_redirect_uri": "https://health.funti.cc/api/auth/callback",
        "frontend_url": "https://health.funti.cc/app",
        "email_auth_enabled": True,
        "magic_link_consume_url": "https://health.funti.cc/api/auth/email/consume",
        "smtp_host": "smtp-relay.example",
        "smtp_from_email": "health@example.com",
        "allow_dev_auth": False,
        "account_linking_enabled": True,
        "document_upload_enabled": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_configuration_is_valid_when_complete() -> None:
    production_settings().validate_production()


def test_subdomain_defaults_use_root_paths() -> None:
    settings = Settings(_env_file=None)
    assert settings.frontend_url == "https://health.funti.cc/app"
    assert settings.cors_origins == ["https://health.funti.cc"]


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
        ("magic_link_consume_url", "MAGIC_LINK_CONSUME_URL"),
        ("smtp_host", "SMTP_HOST"),
        ("smtp_from_email", "SMTP_HOST and SMTP_FROM_EMAIL"),
    ],
)
def test_production_rejects_missing_required_settings(field: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        production_settings(**{field: ""}).validate_production()


def test_production_rejects_disabled_account_linking() -> None:
    """CR-08: duplicate-account protection must be fail-safe in production."""
    with pytest.raises(ValueError, match="ACCOUNT_LINKING_ENABLED"):
        production_settings(account_linking_enabled=False).validate_production()


def test_production_rejects_default_account_linking_flag() -> None:
    """The absence of the environment variable must not disable protection."""
    values = production_settings().model_dump()
    values.pop("account_linking_enabled")
    with pytest.raises(ValueError, match="ACCOUNT_LINKING_ENABLED"):
        Settings(_env_file=None, **values).validate_production()


def test_development_allows_disabled_account_linking() -> None:
    """Disabling the protection stays an explicit development-only override."""
    Settings(
        _env_file=None, environment="development", account_linking_enabled=False
    ).validate_production()


def test_document_intake_defaults_to_disabled() -> None:
    settings = Settings(_env_file=None)
    assert settings.document_upload_enabled is False
    assert settings.document_storage_backend == "local"
    assert settings.document_max_bytes == 20 * 1024 * 1024
    assert settings.document_max_image_pixels == 25_000_000


def test_production_rejects_document_upload_enablement() -> None:
    with pytest.raises(ValueError, match="DOCUMENT_UPLOAD_ENABLED"):
        production_settings(document_upload_enabled=True).validate_production()


def test_development_allows_explicit_document_upload_enablement() -> None:
    Settings(
        _env_file=None,
        environment="development",
        document_upload_enabled=True,
    ).validate_production()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("document_storage_backend", "s3", "DOCUMENT_STORAGE_BACKEND"),
        ("document_storage_root", "", "DOCUMENT_STORAGE_ROOT"),
        ("document_max_bytes", 20 * 1024 * 1024 + 1, "DOCUMENT_MAX_BYTES"),
        ("document_max_image_pixels", 25_000_001, "DOCUMENT_MAX_IMAGE_PIXELS"),
    ],
)
def test_document_intake_rejects_unsupported_slice_b_configuration(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        Settings(_env_file=None, **{field: value}).validate_production()
