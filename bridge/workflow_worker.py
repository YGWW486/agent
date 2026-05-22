"""RequestQueue 工作流消费者 — 从队列取出任务并运行 SSE 工作流"""

from __future__ import annotations

import asyncio
import logging

from bridge.request_queue import request_queue

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def workflow_queue_worker() -> None:
    """持续消费 request_queue 中的 workflow 任务"""
    from api.routes import _run_workflow_with_events

    logger.info("[WorkflowWorker] started")
    while True:
        job = await request_queue.get()
        thread_id = job.get("thread_id", "?")
        try:
            await _run_workflow_with_events(
                thread_id,
                job["initial_state"],
                job["event_queue"],
            )
        except Exception as e:
            logger.error(f"[WorkflowWorker] job {thread_id} failed: {e}")
        finally:
            request_queue.task_done()


def start_workflow_worker() -> asyncio.Task:
    """在 FastAPI lifespan 中启动后台 worker"""
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        return _worker_task
    _worker_task = asyncio.create_task(workflow_queue_worker())
    return _worker_task


async def stop_workflow_worker() -> None:
    """关闭 worker 并清空待处理队列"""
    global _worker_task
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
    request_queue.clear()
    logger.info("[WorkflowWorker] stopped")
