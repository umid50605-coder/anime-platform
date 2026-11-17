"""
Application configuration.

All configuration is read from environment variables (optionally via a .env
file for local development). Nothing here is hardcoded secrets - see
.env.example at the repository root for the full list of variables.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- General ---
    app_name: str = "Anime Platform API"
    environment: str = "development"  # development | production | test
    # SAFE-BY-DEFAULT: when True, Starlette's ServerErrorMiddleware returns a
    # raw HTML traceback (source lines, file paths, locals) to the CLIENT for
    # any unhandled exception, and skips our own exception handler entirely
    # (see app/main.py's unhandled_exception_handler and
    # docs/decisions/0003-request-correlation-logging.md). Opt into this
    # explicitly per-environment (DEBUG=true) - never default it on.
    debug: bool = False

    # --- Database ---
    # MySQL is the primary database. SQLite remains available when explicitly
    # selected, and test fixtures use isolated in-memory SQLite databases.
    database_url: str = "mysql+pymysql://anime_app:CHANGE_ME@localhost:3306/anime_metadata"
    
    # --- Security / Auth ---
    jwt_secret_key: str = "CHANGE_ME_IN_ENV"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 30
    # Email verification (Task 11). The link is `<frontend_base_url>/verify-email#token=...`
    # (URL fragment, same reasoning as password reset). Resend is limited per
    # ACCOUNT in the database (cooldown + hourly cap), on top of the per-IP limit.
    email_verification_token_expire_minutes: int = 24 * 60
    email_verification_resend_cooldown_seconds: int = 60
    email_verification_max_sends_per_hour: int = 5
    # Base URL the password-reset link in the email points at (the SPA).
    # The link is `<base>/reset-password#token=...`: the token is in the URL
    # FRAGMENT, which browsers never send to any server, so it can't end up in
    # access logs or Referer headers. See docs/decisions/0005-password-reset.md.
    frontend_base_url: str = "http://localhost:5173"

    # --- CORS ---
    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://10.121.58.173:5173",
    ]

    # --- Logging ---
    log_level: str = "INFO"

    # --- Integrations (provider selection) ---
    # Supported implementations: "mock" and "jikan" (see app/integrations).
    anime_provider: str = "mock"
    anime_provider_base_url: str = "https://api.jikan.moe/v4"
    anime_provider_timeout_seconds: float = 10.0
    video_provider: str = "mock"
    video_storage_path: Path = Path.home() / "Videos" / "anime"
    email_provider: str = "memory"  # memory | smtp
    # SMTP (only read when email_provider="smtp"). Supply via environment only.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True  # STARTTLS on smtp_port; ignored when smtp_use_ssl
    smtp_use_ssl: bool = False  # implicit TLS (typically port 465)
    smtp_timeout_seconds: float = 10.0
    email_from_address: str = ""
    email_from_name: str = "Anime Platform"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor - import this, not Settings() directly."""
    return Settings()
