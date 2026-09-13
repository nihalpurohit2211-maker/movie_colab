"""
app/core/downloader.py
Zero-copy streaming downloader.

Primary path  : httpx.AsyncClient streaming (follows redirects, reads headers).
Fallback path : yt-dlp subprocess piping to stdout (media platforms / httpx failures).

open_stream() returns (StreamMeta, AsyncGenerator[bytes, None]).
The generator yields raw byte chunks.  The drive_uploader's ChunkAccumulator
re-buffers them into exact 16 MB Drive-aligned blocks.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import AsyncGenerator, Optional
from urllib.parse import urlparse, unquote

import httpx

logger = logging.getLogger(__name__)

# Read size per aiter_bytes / process.stdout.read call.
_READ_CHUNK = 2 * 1024 * 1024  # 2 MB

MEDIA_PLATFORMS: frozenset[str] = frozenset({
    "youtube.com", "www.youtube.com", "youtu.be",
    "vimeo.com", "www.vimeo.com",
    "dailymotion.com", "www.dailymotion.com",
    "twitch.tv", "www.twitch.tv",
    "instagram.com", "www.instagram.com",
    "twitter.com", "www.twitter.com", "x.com",
    "tiktok.com", "www.tiktok.com",
    "facebook.com", "www.facebook.com",
    "bilibili.com", "www.bilibili.com",
})


@dataclass
class StreamMeta:
    total_size: Optional[int] = None
    filename: Optional[str] = None
    content_type: str = "application/octet-stream"


# ---------------------------------------------------------------------------
# Helper: populate StreamMeta from HTTP response headers
# ---------------------------------------------------------------------------

def _extract_meta(meta: StreamMeta, headers: httpx.Headers) -> None:
    """Fill *meta* in-place from response headers."""
    if "content-length" in headers:
        try:
            meta.total_size = int(headers["content-length"])
        except ValueError:
            pass

    meta.content_type = (
        headers.get("content-type", "application/octet-stream").split(";")[0].strip()
    )

    cd = headers.get("content-disposition", "")
    if "filename" in cd.lower():
        for part in cd.split(";"):
            part = part.strip()
            if part.lower().startswith("filename*="):
                # RFC 5987: filename*=UTF-8''encoded-name
                try:
                    _, encoded = part.split("''", 1)
                    meta.filename = unquote(encoded.strip())
                except ValueError:
                    pass
                break
            elif part.lower().startswith("filename="):
                meta.filename = part[9:].strip('"').strip("'").strip()
                break


def _is_media_platform(url: str) -> bool:
    try:
        return (urlparse(url).hostname or "").lower() in MEDIA_PLATFORMS
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Primary downloader: httpx async streaming
# ---------------------------------------------------------------------------

async def _open_httpx_stream(
    url: str,
    cancel_event: asyncio.Event,
) -> tuple[StreamMeta, AsyncGenerator[bytes, None]]:
    """
    Open an httpx streaming GET and return as soon as response headers arrive.
    Data continues to flow through the returned async generator.
    """
    meta = StreamMeta()
    ready: asyncio.Event = asyncio.Event()
    error: list[BaseException] = []
    q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=1)

    async def _produce() -> None:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0),
                follow_redirects=True,
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            ) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    _extract_meta(meta, resp.headers)
                    ready.set()
                    async for chunk in resp.aiter_bytes(chunk_size=_READ_CHUNK):
                        if cancel_event.is_set():
                            return
                        await q.put(chunk)
        except Exception as exc:
            error.append(exc)
        finally:
            ready.set()   # unblock caller even on error
            await q.put(None)  # sentinel - always signal end

    produce_task = asyncio.create_task(_produce())

    try:
        await asyncio.wait_for(ready.wait(), timeout=60.0)
    except asyncio.TimeoutError:
        produce_task.cancel()
        raise ConnectionError(f"Connection to {url!r} timed out after 60 s")

    if error:
        produce_task.cancel()
        raise error[0]

    async def _consume() -> AsyncGenerator[bytes, None]:
        try:
            while True:
                item = await q.get()
                if item is None:
                    if error:
                        raise error[0]
                    return
                yield item
        except GeneratorExit:
            produce_task.cancel()

    return meta, _consume()


# ---------------------------------------------------------------------------
# Fallback downloader: yt-dlp subprocess
# ---------------------------------------------------------------------------

async def _open_ytdlp_stream(
    url: str,
    cancel_event: asyncio.Event,
) -> tuple[StreamMeta, AsyncGenerator[bytes, None]]:
    """
    Launch yt-dlp with `-o -` to pipe encoded video bytes to stdout.
    Suitable for YouTube, Vimeo, and other media platforms.
    """
    meta = StreamMeta(content_type="video/mp4")
    error: list[BaseException] = []
    q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=1)

    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--quiet",
        "--no-warnings",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", "-",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def _produce() -> None:
        try:
            assert process.stdout is not None
            while True:
                if cancel_event.is_set():
                    process.kill()
                    break
                chunk = await process.stdout.read(_READ_CHUNK)
                if not chunk:
                    break
                await q.put(chunk)
            await process.wait()
            if process.returncode not in (0, None) and not cancel_event.is_set():
                stderr_bytes = b""
                if process.stderr:
                    stderr_bytes = await process.stderr.read(4096)
                error.append(
                    RuntimeError(
                        f"yt-dlp exited with code {process.returncode}: "
                        f"{stderr_bytes.decode(errors='replace')[:300]}"
                    )
                )
        except Exception as exc:
            error.append(exc)
        finally:
            await q.put(None)

    asyncio.create_task(_produce())

    async def _consume() -> AsyncGenerator[bytes, None]:
        while True:
            item = await q.get()
            if item is None:
                if error:
                    raise error[0]
                return
            yield item

    return meta, _consume()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def open_stream(
    url: str,
    cancel_event: asyncio.Event,
) -> tuple[StreamMeta, AsyncGenerator[bytes, None]]:
    """
    Open a zero-copy streaming download from *url*.

    Returns (StreamMeta, async_chunk_generator).
    Routing:
      - Media platform URL  -> yt-dlp directly.
      - Other URL           -> httpx primary; yt-dlp fallback on HTTP/connection error.

    The chunk generator yields raw bytes in up to 8 MB segments.
    drive_uploader.stream_to_drive() re-accumulates them into 16 MB Drive chunks.
    """
    if _is_media_platform(url):
        logger.info("Media platform detected — routing via yt-dlp: %s", url)
        return await _open_ytdlp_stream(url, cancel_event)

    try:
        return await _open_httpx_stream(url, cancel_event)
    except (httpx.HTTPStatusError, httpx.RequestError, OSError, ConnectionError) as exc:
        logger.warning("httpx streaming failed (%s) — falling back to yt-dlp", exc)
        return await _open_ytdlp_stream(url, cancel_event)
