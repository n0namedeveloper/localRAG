"""Logs API: SSE stream of recent pipeline logs."""
import asyncio
import logging
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/logs", tags=["logs"])

log_broker: asyncio.Queue[dict] = asyncio.Queue(maxsize=200)
logger = logging.getLogger(__name__)


async def put_log(entry: dict):
    if log_broker.full():
        try:
            log_broker.get_nowait()
        except asyncio.QueueEmpty:
            pass
    await log_broker.put(entry)


@router.get("/stream")
def stream_logs():
    """Server-Sent Events (SSE) stream of pipeline logs."""

    async def event_source():
        while True:
            try:
                entry = await asyncio.wait_for(log_broker.get(), timeout=5)
                data = json.dumps(entry)
                yield f"data: {data}\\n\\n"
            except asyncio.TimeoutError:
                yield f"data: {{\"type\":\"ping\",\"time\":{time.time()}}}\\n\\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")