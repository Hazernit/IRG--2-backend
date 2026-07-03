import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.events.broker import event_broker


router = APIRouter(tags=["events"])


@router.get("/events", response_class=StreamingResponse)
async def stream_events(request: Request) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        async with event_broker.subscribe() as queue:
            yield ": connected\n\n"
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                event_name = event.get("type", "message")
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"event: {event_name}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

