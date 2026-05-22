"""runtime_events SSE 发射测试"""

import asyncio
import pytest

from agent.runtime_events import emit_sse, reset_event_queue, set_event_queue


@pytest.mark.asyncio
async def test_emit_sse_puts_on_queue():
    q: asyncio.Queue = asyncio.Queue()
    token = set_event_queue(q)
    try:
        await emit_sse({"event": "tool_call", "tool": "read_file"})
        item = await asyncio.wait_for(q.get(), timeout=1.0)
        assert item["event"] == "tool_call"
        assert "timestamp" in item
    finally:
        reset_event_queue(token)


@pytest.mark.asyncio
async def test_emit_sse_noop_without_queue():
    await emit_sse({"event": "tool_call"})
