"""工作流运行时 SSE 事件 — ContextVar 注入 event queue"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

_event_queue_var: ContextVar[asyncio.Queue | None] = ContextVar("workflow_event_queue", default=None)


def set_event_queue(queue: asyncio.Queue | None):
    return _event_queue_var.set(queue)


def reset_event_queue(token) -> None:
    _event_queue_var.reset(token)


async def emit_sse(payload: dict[str, Any]) -> None:
    """向当前 workflow 的 SSE 队列推送事件（无队列时静默跳过）"""
    queue = _event_queue_var.get()
    if queue is None:
        return
    if "timestamp" not in payload:
        payload = {
            **payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    await queue.put(payload)
