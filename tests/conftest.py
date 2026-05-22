"""Shared pytest fixtures for agent workflow tests"""
from __future__ import annotations

import uuid

import pytest

import agent.orchestrator as orchestrator
from agent.orchestrator import build_workflow
from tests.fixtures.fake_llm import StatefulFakeLLM
from tests.fixtures.workflow_fixtures import make_initial_state


@pytest.fixture(autouse=True)
def disable_coder_tools_by_default(monkeypatch):
    """测试默认关闭 CODER_TOOLS，避免受本地 .env 影响"""
    monkeypatch.setenv("CODER_TOOLS_ENABLED", "false")
    import config.settings as mod
    mod._settings = None
    yield
    mod._settings = None


@pytest.fixture(autouse=True)
def reset_orchestrator_singletons():
    """Isolate global workflow and circuit breaker between tests."""
    orchestrator._workflow = None
    orchestrator._llm_circuit.failure_count = 0
    orchestrator._llm_circuit.last_failure_time = None
    orchestrator._llm_circuit.state = "closed"
    yield
    orchestrator._workflow = None


@pytest.fixture(autouse=True)
def mock_context(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "build_planner_context",
        lambda state: state.get("context", "ctx"),
    )
    monkeypatch.setattr(
        orchestrator,
        "build_coder_context",
        lambda state, task: state.get("context", "ctx"),
    )


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch):
    async def _retry_async(func, config=None, *args, **kwargs):
        return await func(*args, **kwargs)

    async def _circuit_call(self, func, *args, **kwargs):
        return await func(*args, **kwargs)

    monkeypatch.setattr(orchestrator, "retry_async", _retry_async)
    monkeypatch.setattr(
        orchestrator.CircuitBreaker,
        "call",
        _circuit_call,
    )


@pytest.fixture
def fake_merge(monkeypatch):
    async def _merge(state):
        return {
            "status": "approved",
            "suspended": False,
            "written_files": [{"path": "mock.py", "size": 1}],
        }

    monkeypatch.setattr(orchestrator, "merge_node", _merge)
    orchestrator._workflow = None


@pytest.fixture
def workflow_config():
    return {"configurable": {"thread_id": f"test-{uuid.uuid4().hex[:8]}"}}


@pytest.fixture
def initial_state():
    return make_initial_state()


@pytest.fixture
def patched_workflow(monkeypatch, fake_merge):
    """Return a factory: patched_workflow(fake_llm) -> compiled graph with mock LLM."""

    holder: dict = {}

    def _get_llm(model=None):
        return holder["llm"]

    monkeypatch.setattr(orchestrator, "get_llm", _get_llm)

    def _build(fake: StatefulFakeLLM):
        holder["llm"] = fake
        orchestrator._workflow = None
        return build_workflow()

    return _build
