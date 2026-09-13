"""
app/api/v1/endpoints.py
Transfer pipeline API routes.

POST /transfer/start              - Validate request, spawn background task, return task_id.
GET  /transfer/{task_id}/progress - SSE stream of ProgressEvent objects.
POST /transfer/{task_id}/cancel   - Signal cancellation for a running task.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Optional
from urllib.parse import unquote, urlparse

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core import downloader, drive_uploader, telemetry
from app.schemas.transfer import (
    ProgressEvent,
    TransferRequest,
    TransferStartResponse,
    TransferStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _filename_from_url(url: str) -> str:
    """Best-effort filename extraction from the URL path component."""
    try:
        path = urlparse(url).path
        segments = [s for s in path.split("/") if s]
        if segments:
            name = unquote(segments[-1])
            if name:
                return name
    except Exception:
        pass
    return "download"


# ---------------------------------------------------------------------------
# Background transfer coroutine
# ---------------------------------------------------------------------------

async def _run_transfer(
    task_id: str,
    url: str,
    access_token: str,
    folder_name: str,
    filename_override: Optional[str],
) -> None:
    """
    Full transfer pipeline:
      queued -> downloading -> uploading_to_drive -> syncing -> completed
                                                              \\-> failed
    os.sync() is executed inside drive_uploader.stream_to_drive() upon
    receiving the terminal 200/201 from Drive, guaranteeing the flush
    happens before the completed event is emitted here.
    """
    cancel_event = telemetry.get_cancel_event(task_id) or asyncio.Event()

    try:
        # ---- 1. Queued -------------------------------------------------------
        await telemetry.emit(task_id, ProgressEvent(
            task_id=task_id,
            status=TransferStatus.queued,
            message="Transfer queued, opening source stream…",
        ))

        # ---- 2. Open stream (headers + async generator) ----------------------
        meta, chunks = await downloader.open_stream(url, cancel_event)

        filename = filename_override or meta.filename or _filename_from_url(url)
        mime_type = meta.content_type
        total_size = meta.total_size

        await telemetry.emit(task_id, ProgressEvent(
            task_id=task_id,
            status=TransferStatus.downloading,
            message=f"Source open — {filename} ({mime_type})",
            total_bytes=total_size or 0,
        ))

        # ---- 3. Drive: folder resolution + resumable session -----------------
        drive_timeout = httpx.Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0)
        async with httpx.AsyncClient(timeout=drive_timeout) as drive_client:

            folder_id = await drive_uploader.resolve_or_create_folder(
                access_token, folder_name, drive_client
            )

            upload_uri = await drive_uploader.initiate_resumable_session(
                access_token, folder_id, filename, mime_type, total_size, drive_client
            )

            await telemetry.emit(task_id, ProgressEvent(
                task_id=task_id,
                status=TransferStatus.uploading_to_drive,
                message=f"Uploading '{filename}' -> Drive:/{folder_name}",
                total_bytes=total_size or 0,
            ))

            # ---- 4. Stream chunks (os.sync called inside on 200/201) ---------
            drive_file_id = await drive_uploader.stream_to_drive(
                upload_uri=upload_uri,
                source_gen=chunks,
                total_size=total_size,
                task_id=task_id,
                cancel_event=cancel_event,
                client=drive_client,
            )

        # ---- 5. Syncing banner (os.sync already executed above) --------------
        await telemetry.emit(task_id, ProgressEvent(
            task_id=task_id,
            status=TransferStatus.syncing,
            message="os.sync() complete — Drive confirmed write",
            percent=99.9,
        ))

        drive_link: Optional[str] = (
            f"https://drive.google.com/file/d/{drive_file_id}/view"
            if drive_file_id
            else None
        )

        # ---- 6. Completed ----------------------------------------------------
        await telemetry.emit(task_id, ProgressEvent(
            task_id=task_id,
            status=TransferStatus.completed,
            message="Transfer complete",
            percent=100.0,
            drive_file_id=drive_file_id or "",
            drive_file_link=drive_link,
        ))

    except asyncio.CancelledError:
        logger.info("Task %s was cancelled", task_id)
        await telemetry.emit(task_id, ProgressEvent(
            task_id=task_id,
            status=TransferStatus.failed,
            message="Transfer cancelled by user",
            error="Cancelled",
        ))

    except Exception as exc:
        logger.exception("Task %s failed: %s", task_id, exc)
        await telemetry.emit(task_id, ProgressEvent(
            task_id=task_id,
            status=TransferStatus.failed,
            message="Transfer failed",
            error=str(exc)[:500],
        ))


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@router.post("/transfer/start", response_model=TransferStartResponse, status_code=202)
async def start_transfer(request: TransferRequest) -> TransferStartResponse:
    """
    Accept a transfer request, register it in telemetry, and launch the
    background pipeline coroutine.  Returns the task_id immediately.
    """
    task_id = str(uuid.uuid4())
    telemetry.create_task(task_id)

    asyncio.create_task(
        _run_transfer(
            task_id=task_id,
            url=str(request.url),
            access_token=request.access_token,
            folder_name=request.folder_name,
            filename_override=request.filename,
        ),
        name=f"transfer-{task_id}",
    )

    logger.info("Accepted transfer task %s for URL %s", task_id, request.url)
    return TransferStartResponse(task_id=task_id)


@router.get("/transfer/{task_id}/progress")
async def get_progress(task_id: str) -> StreamingResponse:
    """
    SSE stream of ProgressEvent objects for the given task.
    Keeps the connection alive with periodic heartbeat comments.
    """
    async def _event_stream():
        async for frame in telemetry.subscribe(task_id):
            yield frame

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


@router.post("/transfer/{task_id}/cancel", status_code=200)
async def cancel_transfer(task_id: str) -> dict:
    """Signal cancellation for a running transfer task."""
    cancelled = telemetry.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id!r} not found or already completed",
        )
    return {"task_id": task_id, "cancelled": True}
