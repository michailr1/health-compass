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

    # HC-017 stays disabled outside development until encrypted storage,
    # scanner, rendering and deployment controls are independently approved.
    document_upload_enabled: bool = False
    document_storage_backend: str = "local_encrypted"
    document_storage_root: str = "/tmp/health-compass-documents"
    document_max_bytes: int = 20 * 1024 * 1024
    document_max_image_pixels: int = 25_000_000
    document_min_free_bytes: int = 512 * 1024 * 1024
    document_encryption_active_key_id: str = "dev-document-key"
    document_credentials_directory: str = "/tmp/health-compass-document-credentials"

    # Development/test defaults only. Production values must be selected from
    # measured capacity during the controlled rollout and kept explicit.
    document_profile_max_bytes: int = 512 * 1024 * 1024
    document_global_max_bytes: int = 10 * 1024 * 1024 * 1024
    document_profile_max_documents: int = 100
    document_profile_max_queued_jobs: int = 20

    # Scanner worker.
    document_worker_database_url: str = ""
    document_scanner_socket: str = "/run/clamav/clamd.ctl"
    document_scanner_timeout_seconds: int = 60
    document_scanner_max_signature_age_hours: int = 48
    document_worker_lease_seconds: int = 300
    document_worker_max_attempts: int = 5

    # Safe renderer worker. Paths are fixed executable locations; no shell is
    # used and user-controlled values never become executable arguments.
    document_renderer_database_url: str = ""
    document_pdfinfo_path: str = "/usr/bin/pdfinfo"
    document_pdftocairo_path: str = "/usr/bin/pdftocairo"
    document_magick_path: str = "/usr/bin/magick"
    document_render_timeout_seconds: int = 30
    document_render_cpu_seconds: int = 20
    document_render_memory_bytes: int = 512 * 1024 * 1024
    document_render_max_output_bytes: int = 50 * 1024 * 1024
    document_render_max_pages: int = 50
    document_render_dpi: int = 150
    document_render_lease_seconds: int = 300
    document_render_max_attempts: int = 3

    # Storage reconciliation worker.
    document_reconciler_database_url: str = ""
    document_orphan_grace_seconds: int = 60 * 60
    document_orphan_delete_seconds: int = 7 * 24 * 60 * 60

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
        if self.document_storage_backend.strip().lower() != "local_encrypted":
            raise ValueError(
                "DOCUMENT_STORAGE_BACKEND must be 'local_encrypted' in HC-017 Slice C"
            )
        if not self.document_storage_root.strip():
            raise ValueError("DOCUMENT_STORAGE_ROOT must not be empty")
        if self.document_max_bytes < 1 or self.document_max_bytes > 20 * 1024 * 1024:
            raise ValueError("DOCUMENT_MAX_BYTES must be between 1 and 20971520")
        if (
            self.document_max_image_pixels < 1
            or self.document_max_image_pixels > 25_000_000
        ):
            raise ValueError(
                "DOCUMENT_MAX_IMAGE_PIXELS must be between 1 and 25000000"
            )
        if self.document_min_free_bytes < 0:
            raise ValueError("DOCUMENT_MIN_FREE_BYTES must not be negative")
        if not self.document_encryption_active_key_id.strip():
            raise ValueError("DOCUMENT_ENCRYPTION_ACTIVE_KEY_ID must not be empty")
        if not self.document_credentials_directory.strip():
            raise ValueError("DOCUMENT_CREDENTIALS_DIRECTORY must not be empty")
        if self.document_profile_max_bytes < self.document_max_bytes:
            raise ValueError("DOCUMENT_PROFILE_MAX_BYTES must cover one maximum document")
        if self.document_global_max_bytes < self.document_profile_max_bytes:
            raise ValueError("DOCUMENT_GLOBAL_MAX_BYTES must cover one profile quota")
        if not 1 <= self.document_profile_max_documents <= 10000:
            raise ValueError("DOCUMENT_PROFILE_MAX_DOCUMENTS must be between 1 and 10000")
        if not 1 <= self.document_profile_max_queued_jobs <= 1000:
            raise ValueError("DOCUMENT_PROFILE_MAX_QUEUED_JOBS must be between 1 and 1000")
        if not self.document_scanner_socket.strip().startswith("/"):
            raise ValueError("DOCUMENT_SCANNER_SOCKET must be an absolute Unix socket path")
        if not 1 <= self.document_scanner_timeout_seconds <= 300:
            raise ValueError("DOCUMENT_SCANNER_TIMEOUT_SECONDS must be between 1 and 300")
        if not 1 <= self.document_scanner_max_signature_age_hours <= 168:
            raise ValueError(
                "DOCUMENT_SCANNER_MAX_SIGNATURE_AGE_HOURS must be between 1 and 168"
            )
        if not 30 <= self.document_worker_lease_seconds <= 1800:
            raise ValueError("DOCUMENT_WORKER_LEASE_SECONDS must be between 30 and 1800")
        if not 1 <= self.document_worker_max_attempts <= 10:
            raise ValueError("DOCUMENT_WORKER_MAX_ATTEMPTS must be between 1 and 10")
        for field_name, value in (
            ("DOCUMENT_PDFINFO_PATH", self.document_pdfinfo_path),
            ("DOCUMENT_PDFTOCAIRO_PATH", self.document_pdftocairo_path),
            ("DOCUMENT_MAGICK_PATH", self.document_magick_path),
        ):
            if not value.strip().startswith("/"):
                raise ValueError(f"{field_name} must be an absolute executable path")
        if not 1 <= self.document_render_timeout_seconds <= 300:
            raise ValueError("DOCUMENT_RENDER_TIMEOUT_SECONDS must be between 1 and 300")
        if not 1 <= self.document_render_cpu_seconds <= 120:
            raise ValueError("DOCUMENT_RENDER_CPU_SECONDS must be between 1 and 120")
        if not 64 * 1024 * 1024 <= self.document_render_memory_bytes <= 2 * 1024 * 1024 * 1024:
            raise ValueError(
                "DOCUMENT_RENDER_MEMORY_BYTES must be between 67108864 and 2147483648"
            )
        if not 1024 <= self.document_render_max_output_bytes <= 100 * 1024 * 1024:
            raise ValueError(
                "DOCUMENT_RENDER_MAX_OUTPUT_BYTES must be between 1024 and 104857600"
            )
        if not 1 <= self.document_render_max_pages <= 50:
            raise ValueError("DOCUMENT_RENDER_MAX_PAGES must be between 1 and 50")
        if not 72 <= self.document_render_dpi <= 300:
            raise ValueError("DOCUMENT_RENDER_DPI must be between 72 and 300")
        if not 30 <= self.document_render_lease_seconds <= 1800:
            raise ValueError("DOCUMENT_RENDER_LEASE_SECONDS must be between 30 and 1800")
        if not 1 <= self.document_render_max_attempts <= 10:
            raise ValueError("DOCUMENT_RENDER_MAX_ATTEMPTS must be between 1 and 10")
        if not 60 <= self.document_orphan_grace_seconds <= 7 * 24 * 60 * 60:
            raise ValueError("DOCUMENT_ORPHAN_GRACE_SECONDS must be between 60 and 604800")
        if self.document_orphan_delete_seconds <= self.document_orphan_grace_seconds:
            raise ValueError(
                "DOCUMENT_ORPHAN_DELETE_SECONDS must exceed DOCUMENT_ORPHAN_GRACE_SECONDS"
            )
        if not self.is_production:
            return
        if self.document_upload_enabled:
            raise ValueError(
                "DOCUMENT_UPLOAD_ENABLED must remain false outside development "
                "until scanner, renderer, reconciliation and rollout are approved"
            )
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
