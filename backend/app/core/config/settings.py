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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor - import this, not Settings() directly."""
    return Settings()
