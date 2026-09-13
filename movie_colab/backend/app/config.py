"""
app/config.py
Centralised application settings loaded from environment / .env file.
"""
from __future__ import annotations

import json
from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: str = "development"

    # Accepted CORS origins (supports list or comma-separated string from env vars).
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    # Drive v3 resumable upload requires all intermediate chunks to be an exact
    # multiple of 256 KiB (262,144 bytes).
    # Default is 64 MB (67,108,864 bytes = 256 * 256 KiB) for cloud transfers.
    CHUNK_SIZE_BYTES: int = 64 * 1024 * 1024

    MAX_CONCURRENT_TASKS: int = 10

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return ["*"]
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [part.strip() for part in stripped.split(",") if part.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return ["*"]

    @field_validator("CHUNK_SIZE_BYTES")
    @classmethod
    def validate_chunk_size(cls, v: int) -> int:
        drive_alignment = 256 * 1024  # 256 KiB
        if v < drive_alignment or v % drive_alignment != 0:
            raise ValueError(
                f"CHUNK_SIZE_BYTES must be a multiple of 256 KiB (262,144 bytes). Got {v}."
            )
        return v


# Module-level singleton imported across the application.
settings = Settings()
