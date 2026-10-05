"""
Application configuration.

All configuration is read from environment variables (optionally via a .env
file for local development). Nothing here is hardcoded secrets - see
.env.example at the repository root for the full list of variables.
"""

from functools import lru_cache

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
    # Default is a local SQLite file so the foundation runs with zero external
    # infrastructure. Swap to a PostgreSQL URL in production - SQLAlchemy
    # abstracts the engine, so no application code needs to change.
    database_url: str = "sqlite:///./anime_platform.db"

    # --- Security / Auth ---
    jwt_secret_key: str = "CHANGE_ME_IN_ENV"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24h, fine for MVP

    # --- CORS ---
    cors_allow_origins: list[str] = ["http://localhost:5173"]

    # --- Logging ---
    log_level: str = "INFO"

    # --- Integrations (provider selection) ---
    # "mock" is the only implementation for now (see app/integrations).
    # Real vendors are intentionally NOT implemented yet.
    anime_provider: str = "mock"
    video_provider: str = "mock"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor - import this, not Settings() directly."""
    return Settings()
