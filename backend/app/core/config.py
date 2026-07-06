"""Health Compass API — Application configuration via Pydantic Settings."""

from __future__ import annotations

from pathlib import Path

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

    # Database — application connection
    database_url: str = (
        "postgresql+psycopg://health_compass_app:changeme@127.0.0.1:5433/health_compass"
    )

    # Database — migrator connection (Alembic, schema changes)
    database_migrator_url: str | None = None

    # Future OIDC (not yet active)
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_audience: str | None = None

    # CORS — only if needed
    cors_origins: list[str] = ["https://funti.cc"]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def migrator_url(self) -> str:
        return self.database_migrator_url or self.database_url


settings = Settings()
