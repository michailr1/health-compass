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

    # Service metadata
    service_name: str = "health-compass-api"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Server
    host: str = "127.0.0.1"
    port: int = 8100

    # Database — application connection (REQUIRED outside development)
    database_url: str = ""

    # Database — migrator connection (REQUIRED for Alembic outside development)
    database_migrator_url: str = ""

    # Build commit — injected at deploy time, avoids subprocess per request
    build_commit: str = ""

    # Direct Google OIDC
    oidc_issuer: str | None = "https://accounts.google.com"
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_audience: str | None = None
    oidc_redirect_uri: str | None = None

    # Server-side session cookie
    session_cookie_name: str = "hc_session"
    session_ttl_seconds: int = 60 * 60 * 12
    frontend_url: str = "https://funti.cc/health/"

    # Temporary integration-test auth. Must stay disabled outside local development.
    allow_dev_auth: bool = False

    # CORS — only if needed
    cors_origins: list[str] = ["https://funti.cc"]

    @property
    def is_production(self) -> bool:
        """Treat every non-development environment as production-like."""
        return self.environment.strip().lower() != "development"

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() == "development"

    @property
    def migrator_url(self) -> str:
        """Return the migrator database URL.

        Must be explicitly set via DATABASE_MIGRATOR_URL.
        Never falls back to database_url to prevent accidental DDL on app schema.
        """
        return self.database_migrator_url

    def validate_production(self) -> None:
        """Raise on dangerous non-development misconfiguration."""
        if self.allow_dev_auth and not self.is_development:
            raise ValueError("ALLOW_DEV_AUTH must be false outside development")
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


settings = Settings()
