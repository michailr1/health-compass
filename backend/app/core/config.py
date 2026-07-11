"""Health Compass API — Application configuration via Pydantic Settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "health-compass-api"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    host: str = "127.0.0.1"
    port: int = 8100

    database_url: str = ""
    database_migrator_url: str = ""
    build_commit: str = ""

    oidc_issuer: str | None = "https://accounts.google.com"
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_audience: str | None = None
    oidc_redirect_uri: str | None = None

    session_cookie_name: str = "hc_session"
    session_ttl_seconds: int = 60 * 60 * 12
    frontend_url: str = "https://health.funti.cc/app"

    email_auth_enabled: bool = True
    magic_link_ttl_seconds: int = 15 * 60
    magic_link_consume_url: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_starttls: bool = True
    smtp_use_ssl: bool = False

    account_linking_enabled: bool = False
    account_link_intent_ttl_seconds: int = 10 * 60
    account_link_cookie_name: str = "hc_account_link"

    allow_dev_auth: bool = False
    cors_origins: list[str] = ["https://health.funti.cc"]

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() != "development"

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() == "development"

    @property
    def migrator_url(self) -> str:
        return self.database_migrator_url

    def validate_production(self) -> None:
        if self.allow_dev_auth and not self.is_development:
            raise ValueError("ALLOW_DEV_AUTH must be false outside development")
        if self.account_link_intent_ttl_seconds < 60 or self.account_link_intent_ttl_seconds > 1800:
            raise ValueError("ACCOUNT_LINK_INTENT_TTL_SECONDS must be between 60 and 1800")
        if not self.is_production:
            return
        if not self.database_url:
            raise ValueError("DATABASE_URL is required outside development")
        if "changeme" in self.database_url.lower():
            raise ValueError("DATABASE_URL contains placeholder 'changeme'")
        if not self.database_migrator_url:
            raise ValueError("DATABASE_MIGRATOR_URL is required outside development")
        if "changeme" in self.database_migrator_url.lower():
            raise ValueError("DATABASE_MIGRATOR_URL contains placeholder 'changeme'")
        if not self.oidc_issuer or not self.oidc_client_id or not self.oidc_client_secret:
            raise ValueError("Google OIDC settings are required outside development")
        if not self.oidc_redirect_uri:
            raise ValueError("OIDC_REDIRECT_URI is required outside development")
        if not self.account_linking_enabled:
            # Fail safe: without the linking flow a second sign-in method
            # silently creates a duplicate account (CR-08). Disabling the
            # protection is a development-only override.
            raise ValueError(
                "ACCOUNT_LINKING_ENABLED must be true outside development; "
                "disabling duplicate-account protection is a development-only override"
            )
        if self.email_auth_enabled:
            if not self.magic_link_consume_url:
                raise ValueError("MAGIC_LINK_CONSUME_URL is required when email auth is enabled")
            if not self.smtp_host or not self.smtp_from_email:
                raise ValueError("SMTP_HOST and SMTP_FROM_EMAIL are required when email auth is enabled")
            if self.smtp_use_ssl and self.smtp_starttls:
                raise ValueError("SMTP_USE_SSL and SMTP_STARTTLS cannot both be true")


settings = Settings()
