"""Logs API: SSE stream of recent pipeline logs."""
import asyncio
import json
import logging
import time
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/logs", tags=["logs"])

log_broker: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)
logger = logging.getLogger(__name__)


async def put_log(entry: dict):
    if log_broker.full():
        try:
            log_broker.get_nowait()
        except asyncio.QueueEmpty:
            pass
    await log_broker.put(entry)


def put_log_sync(entry: dict):
    """Synchronous version for threads."""
    if log_broker.full():
        try:
            log_broker.get_nowait()
        except asyncio.QueueEmpty:
            pass
    log_broker.put_nowait(entry)


class SSELoggingHandler(logging.Handler):
    """Captures Python logging and pushes it to the SSE log_broker."""
    def emit(self, record):
        try:
            msg = self.format(record)
            entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "message": msg,
                "logger": record.name,
                "stage": "processing",
            }
            put_log_sync(entry)
        except Exception:
            self.handleError(record)


@router.get("/stream")
def stream_logs():
    """Server-Sent Events (SSE) stream of pipeline logs."""

    async def event_source():
        while True:
            try:
                entry = await asyncio.wait_for(log_broker.get(), timeout=5)
                data = json.dumps(entry)
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {{\"type\":\"ping\",\"time\":{time.time()}}}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")