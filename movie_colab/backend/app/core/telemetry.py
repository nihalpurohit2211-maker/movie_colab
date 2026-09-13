"""
app/core/telemetry.py
In-memory asyncio.Queue registry that maps task_id -> SSE subscriber queues.

Lifecycle:
  create_task(task_id)   - Called when a transfer is accepted; registers cancel event.
  emit(task_id, event)   - Broadcasts a ProgressEvent to all active SSE subscribers.
  subscribe(task_id)     - Async generator yielding raw SSE frames ("data: ...\\n\\n").
  cancel_task(task_id)   - Sets the cancellation event for a running transfer.
  get_cancel_event(id)   - Returns the asyncio.Event used to signal cancellation.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from app.schemas.transfer import ProgressEvent, TransferStatus

logger = logging.getLogger(__name__)

# task_id -> list of subscriber queues
_registry: dict[str, list[asyncio.Queue[ProgressEvent | None]]] = {}

# task_id -> cancellation event
_cancel_flags: dict[str, asyncio.Event] = {}

# task_id -> latest ProgressEvent (cached for reconnecting mobile/desktop clients)
_latest_events: dict[str, ProgressEvent] = {}

_TERMINAL = {TransferStatus.completed, TransferStatus.failed}


def create_task(task_id: str) -> None:
    """Register a new task. Must be called before emit() or subscribe()."""
    _registry[task_id] = []
    _cancel_flags[task_id] = asyncio.Event()
    logger.debug("Task %s registered in telemetry", task_id)


def get_cancel_event(task_id: str) -> asyncio.Event | None:
    """Return the cancellation event for a task, or None if not found."""
    return _cancel_flags.get(task_id)


def get_task_status(task_id: str) -> ProgressEvent | None:
    """Return the latest cached status snapshot of task_id, or None if not found."""
    return _latest_events.get(task_id)


async def emit(task_id: str, event: ProgressEvent) -> None:
    """
    Broadcast *event* to all SSE subscribers of *task_id* and cache latest state.
    On terminal events (completed / failed) a None sentinel is appended to
    signal the end of the stream to every subscriber.
    """
    _latest_events[task_id] = event

    queues = _registry.get(task_id, [])
    for q in queues:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Task %s: subscriber queue full, dropping event", task_id)

    if event.status in _TERMINAL:
        for q in queues:
            try:
                q.put_nowait(None)  # sentinel - closes the generator
            except asyncio.QueueFull:
                pass
        _cancel_flags.pop(task_id, None)
        logger.debug("Task %s reached terminal state: %s", task_id, event.status)


async def subscribe(task_id: str) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted strings for *task_id*.
    Immediately yields the latest cached ProgressEvent on connect so
    reconnecting mobile/desktop clients never experience a blank progress state.
    """
    # 1. Yield latest cached state immediately if present
    cached = _latest_events.get(task_id)
    if cached is not None:
        yield f"data: {cached.model_dump_json()}\n\n"
        if cached.status in _TERMINAL:
            return  # Task already concluded

    # 2. Subscribe to subsequent real-time events
    q: asyncio.Queue[ProgressEvent | None] = asyncio.Queue(maxsize=256)
    bucket = _registry.setdefault(task_id, [])
    bucket.append(q)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=20.0)
            except asyncio.TimeoutError:
                # Send a heartbeat comment to keep the connection alive
                yield ": heartbeat\n\n"
                continue

            if event is None:
                break  # terminal sentinel received

            yield f"data: {event.model_dump_json()}\n\n"

    except asyncio.CancelledError:
        # Client disconnected; swallow and clean up
        pass
    finally:
        try:
            bucket.remove(q)
        except ValueError:
            pass
        if not bucket and task_id in _registry:
            del _registry[task_id]


def cancel_task(task_id: str) -> bool:
    """Signal cancellation for a running task.  Returns False if not found."""
    event = _cancel_flags.get(task_id)
    if event is None:
        return False
    event.set()
    logger.info("Cancellation signalled for task %s", task_id)
    return True
