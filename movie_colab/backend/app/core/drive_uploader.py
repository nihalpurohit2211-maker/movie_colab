"""
app/core/drive_uploader.py
Google Drive v3 Resumable Upload engine.

Key guarantees:
  - Every intermediate PUT chunk is exactly CHUNK_SIZE (16 MB = 64 x 256 KiB),
    satisfying the Drive API 256 KiB alignment requirement.
  - The final terminating PUT may carry an arbitrary remainder.
  - os.sync() is called immediately upon receiving the 200/201 terminal
    response, before control returns to the caller.
"""
from __future__ import annotations

import asyncio
import gc
import logging
import os
import time
from typing import AsyncGenerator, Optional

import httpx

from app.config import settings
from app.core import telemetry
from app.schemas.transfer import ProgressEvent, TransferStatus

logger = logging.getLogger(__name__)

_DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
_DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"


# ---------------------------------------------------------------------------
# Folder resolution
# ---------------------------------------------------------------------------

async def resolve_or_create_folder(
    token: str,
    path: str,
    client: httpx.AsyncClient,
) -> str:
    """
    Walk (and create if missing) a nested folder hierarchy in user Drive.
    Returns the Drive folder ID of the deepest path component.

    Example: "Downloads/movie colab"
      -> find/create "Downloads" under root
      -> find/create "movie colab" under "Downloads"
      -> return "movie colab" folder ID
    """
    parts = [p.strip() for p in path.split("/") if p.strip()]
    if not parts:
        return "root"

    parent_id = "root"
    auth = {"Authorization": f"Bearer {token}"}

    for part in parts:
        # Escape single quotes in the GQL filter
        escaped = part.replace("\\", "\\\\").replace("'", "\\'")
        q = (
            f"name='{escaped}' "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and '{parent_id}' in parents "
            f"and trashed=false"
        )
        resp = await client.get(
            _DRIVE_FILES_URL,
            params={"q": q, "fields": "files(id)", "spaces": "drive"},
            headers=auth,
        )
        resp.raise_for_status()
        files = resp.json().get("files", [])

        if files:
            parent_id = files[0]["id"]
            logger.debug("Resolved existing folder '%s' -> %s", part, parent_id)
        else:
            create_resp = await client.post(
                _DRIVE_FILES_URL,
                json={
                    "name": part,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                },
                headers={**auth, "Content-Type": "application/json"},
            )
            create_resp.raise_for_status()
            parent_id = create_resp.json()["id"]
            logger.info("Created Drive folder '%s' -> %s", part, parent_id)

    return parent_id


# ---------------------------------------------------------------------------
# Resumable session initiation
# ---------------------------------------------------------------------------

async def initiate_resumable_session(
    token: str,
    folder_id: str,
    filename: str,
    mime_type: str,
    total_size: Optional[int],
    client: httpx.AsyncClient,
) -> str:
    """
    Initiate a Drive v3 resumable upload session.
    Returns the upload URI from the Location response header.
    """
    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Upload-Content-Type": mime_type,
    }
    if total_size is not None:
        headers["X-Upload-Content-Length"] = str(total_size)

    resp = await client.post(
        _DRIVE_UPLOAD_URL,
        params={"uploadType": "resumable", "fields": "id,webViewLink,name"},
        json={"name": filename, "parents": [folder_id]},
        headers=headers,
    )
    resp.raise_for_status()

    upload_uri = resp.headers.get("location")
    if not upload_uri:
        raise RuntimeError(
            "Drive API did not return a Location header for the resumable session. "
            f"Status: {resp.status_code}  Body: {resp.text[:200]}"
        )

    logger.info("Resumable session started: %s...", upload_uri[:80])
    return upload_uri


# ---------------------------------------------------------------------------
# Chunked streaming to Drive
# ---------------------------------------------------------------------------

async def stream_to_drive(
    upload_uri: str,
    source_gen: AsyncGenerator[bytes, None],
    total_size: Optional[int],
    task_id: str,
    cancel_event: asyncio.Event,
    client: httpx.AsyncClient,
) -> Optional[str]:
    """
    Stream *source_gen* into the Drive resumable upload URI using a
    ChunkAccumulator that enforces the 16 MB alignment constraint.

    Returns the Drive file ID on success.
    Calls os.sync() immediately upon receiving the 200/201 terminal response.
    """
    buffer = bytearray()
    offset = 0        # bytes acknowledged by Drive so far
    bytes_dl = 0      # bytes received from source
    drive_file_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Inner helper: PUT one chunk and update offset
    # ------------------------------------------------------------------
    async def _put_chunk(data: bytes, *, is_final: bool) -> Optional[str]:
        nonlocal offset

        chunk_len = len(data)
        end_byte = offset + chunk_len - 1

        if total_size is not None:
            total_str = str(total_size)
        else:
            total_str = str(offset + chunk_len) if is_final else "*"

        content_range = f"bytes {offset}-{end_byte}/{total_str}"

        logger.debug(
            "PUT chunk task=%s  range=%s  size=%d B  final=%s",
            task_id, content_range, chunk_len, is_final,
        )

        resp = await client.put(
            upload_uri,
            content=data,
            headers={
                "Content-Length": str(chunk_len),
                "Content-Range": content_range,
            },
        )

        if resp.status_code == 308:
            # Chunk accepted; more data expected
            offset += chunk_len
            return None
        elif resp.status_code in (200, 201):
            # Upload complete — Drive returns the file metadata
            offset += chunk_len
            # Non-negotiable: flush OS page cache before signalling completion
            os.sync()
            logger.info("os.sync() executed for task %s", task_id)
            file_info = resp.json()
            return file_info.get("id")
        else:
            resp.raise_for_status()
            return None  # unreachable

    start_time = time.monotonic()

    # Stream chunks through the ChunkAccumulator
    async for raw_chunk in source_gen:
        if cancel_event.is_set():
            raise asyncio.CancelledError("Transfer cancelled by user")

        bytes_dl += len(raw_chunk)
        buffer.extend(raw_chunk)

        # Flush every full block immediately
        chunk_size = settings.CHUNK_SIZE_BYTES
        while len(buffer) >= chunk_size:
            chunk_data = bytes(buffer[:chunk_size])
            del buffer[:chunk_size]

            fid = await _put_chunk(chunk_data, is_final=False)
            if fid:
                drive_file_id = fid

            del chunk_data
            gc.collect()

            pct = round(offset / total_size * 100, 1) if total_size else 0.0
            elapsed = time.monotonic() - start_time
            speed = (offset / elapsed) if elapsed > 0.5 else None
            eta = (
                int((total_size - offset) / speed)
                if (total_size and speed and speed > 1024)
                else None
            )

            await telemetry.emit(task_id, ProgressEvent(
                task_id=task_id,
                status=TransferStatus.uploading_to_drive,
                bytes_downloaded=bytes_dl,
                bytes_uploaded=offset,
                total_bytes=total_size or 0,
                percent=pct,
                speed_bytes_per_sec=speed,
                eta_seconds=eta,
                message=f"Uploaded {offset / (1024 * 1024):.1f} MB",
            ))

    # Flush the final remainder (may be any size, including 0 if total was
    # an exact multiple of chunk_size and Drive already returned 200/201)
    if buffer and drive_file_id is None:
        final_data = bytes(buffer)
        buffer.clear()
        fid = await _put_chunk(final_data, is_final=True)
        if fid:
            drive_file_id = fid
        del final_data
        gc.collect()
    elif buffer:
        buffer.clear()
        gc.collect()

    return drive_file_id
