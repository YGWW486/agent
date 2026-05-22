"""RequestQueue 入队与 worker 消费测试"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from bridge.request_queue import request_queue
from bridge.server import app


@pytest.mark.asyncio
async def test_start_workflow_enqueues_job(monkeypatch):
    ran: list[str] = []

    async def fake_run(thread_id, initial_state, event_queue):
        ran.append(thread_id)
        await event_queue.put({"event": "stream_end"})

    monkeypatch.setattr("api.routes._run_workflow_with_events", fake_run)

    from bridge.workflow_worker import workflow_queue_worker

    worker = asyncio.create_task(workflow_queue_worker())
    await asyncio.sleep(0.05)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/workflow",
            json={"spec": "queue test", "context": "ctx"},
        )
    assert resp.status_code == 200
    thread_id = resp.json()["thread_id"]

    for _ in range(50):
        if thread_id in ran:
            break
        await asyncio.sleep(0.05)
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass

    assert thread_id in ran


@pytest.mark.asyncio
async def test_queue_full_returns_503(monkeypatch):
    async def reject_put(item, timeout=None, priority=0):
        return False

    monkeypatch.setattr(request_queue, "put", reject_put)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/workflow", json={"spec": "b", "context": ""})
    assert resp.status_code == 503
