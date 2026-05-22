"""Coder tool 子循环单元测试"""

import pytest

from agent.coder_loop import run_coder_with_tools, run_coder_single_shot, coder_tools_enabled
from agent.models import CoderOutput
from tests.fixtures.fake_llm import StatefulFakeLLM
from tests.fixtures.workflow_fixtures import minimal_coder_output


@pytest.fixture
def workspace_state(tmp_path):
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    return {"workspace_root": str(tmp_path), "tokens_input": 0, "tokens_output": 0}


@pytest.mark.asyncio
async def test_run_coder_with_tools_executes_read_file(workspace_state, monkeypatch):
    class _EmptyIndex:
        def is_loaded(self):
            return False

    monkeypatch.setattr("agent.coder_loop.get_graph_index", lambda: _EmptyIndex())

    fake = StatefulFakeLLM(
        coder_out=minimal_coder_output(),
        tool_rounds=[[{"name": "read_file", "input": {"path": "main.py"}}]],
    )

    out = await run_coder_with_tools(
        llm=fake,
        user_prompt="implement",
        state=workspace_state,
        emit=None,
    )
    assert isinstance(out, CoderOutput)
    assert fake._tool_round_index == 1


@pytest.mark.asyncio
async def test_run_coder_single_shot():
    fake = StatefulFakeLLM(coder_out=minimal_coder_output())
    out = await run_coder_single_shot(
        llm=fake,
        user_prompt="go",
        system="sys",
    )
    assert out.diff


def test_coder_tools_enabled_flag(monkeypatch):
    from config.settings import get_settings, Settings

    monkeypatch.setenv("CODER_TOOLS_ENABLED", "false")
    import config.settings as mod
    mod._settings = None
    assert coder_tools_enabled() is False

    monkeypatch.setenv("CODER_TOOLS_ENABLED", "true")
    mod._settings = None
    assert coder_tools_enabled() is True
