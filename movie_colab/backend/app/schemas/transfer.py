"""
app/schemas/transfer.py
Pydantic v2 models for request validation and SSE event payloads.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator


class TransferStatus(str, Enum):
    """Ordered pipeline state machine stages."""
    queued = "queued"
    downloading = "downloading"
    uploading_to_drive = "uploading_to_drive"
    syncing = "syncing"
    completed = "completed"
    failed = "failed"


class TransferRequest(BaseModel):
    """Payload for POST /api/v1/transfer/start."""
    url: HttpUrl
    access_token: str
    folder_name: str = "Downloads/movie colab"
    filename: Optional[str] = None

    @field_validator("access_token")
    @classmethod
    def token_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("access_token must not be empty")
        return stripped

    @field_validator("folder_name")
    @classmethod
    def folder_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        return stripped if stripped else "Downloads/movie colab"


class ProgressEvent(BaseModel):
    """SSE payload emitted at each pipeline stage transition."""
    task_id: str
    status: TransferStatus
    bytes_downloaded: int = 0
    bytes_uploaded: int = 0
    total_bytes: int = 0
    percent: float = 0.0
    message: str = ""
    drive_file_id: Optional[str] = None
    drive_file_link: Optional[str] = None
    error: Optional[str] = None


class TransferStartResponse(BaseModel):
    """Response from POST /api/v1/transfer/start."""
    task_id: str
    status: TransferStatus = TransferStatus.queued
