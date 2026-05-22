"""CODER_TOOLS_ENABLED 集成测试"""

import pytest

from tests.fixtures.fake_llm import StatefulFakeLLM
from tests.fixtures.workflow_fixtures import make_initial_state, minimal_coder_output


@pytest.mark.asyncio
async def test_workflow_with_tools_flag_off_unchanged(
    patched_workflow,
    workflow_config,
    initial_state,
):
    """CODER_TOOLS_ENABLED=false 时与现网 mock 路径一致"""
    wf = patched_workflow(StatefulFakeLLM())
    result = await wf.ainvoke(initial_state, workflow_config)
    assert result.get("status") in ("reviewing", "approved", "planning")


@pytest.mark.asyncio
async def test_workflow_with_tools_enabled(
    patched_workflow,
    workflow_config,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("CODER_TOOLS_ENABLED", "true")
    import config.settings as mod
    mod._settings = None

    (tmp_path / "app.py").write_text("v=1\n", encoding="utf-8")

    fake = StatefulFakeLLM(
        coder_out=minimal_coder_output(),
        tool_rounds=[[{"name": "read_file", "input": {"path": "app.py"}}]],
    )
    wf = patched_workflow(fake)
    state = make_initial_state(workspace_root=str(tmp_path))

    result = await wf.ainvoke(state, workflow_config)
    assert fake._tool_round_index >= 1
    assert result.get("code")
