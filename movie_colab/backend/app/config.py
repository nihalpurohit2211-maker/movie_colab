"""
app/config.py
Centralised application settings loaded from environment / .env file.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: str = "development"

    # Accepted CORS origins.
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    # Drive v3 resumable upload requires all intermediate chunks to be an exact
    # multiple of 256 KiB.  16 MB = 64 x 256 KiB.
    CHUNK_SIZE_BYTES: int = 16 * 1024 * 1024  # 16,777,216 bytes

    MAX_CONCURRENT_TASKS: int = 10


# Module-level singleton imported across the application.
settings = Settings()
