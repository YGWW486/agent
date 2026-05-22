"""ToolRegistry 单元测试"""

import pytest
from pathlib import Path

from agent.tools.registry import ToolRegistry, READ_ONLY_TOOL_DEFINITIONS
from agent.tools.workspace import WorkspaceGuard


@pytest.fixture
def registry(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    (tmp_path / "readme.md").write_text("# Hello\n", encoding="utf-8")
    ws = WorkspaceGuard(tmp_path)
    return ToolRegistry(ws, index=None)


def test_tool_definitions_shape():
    assert len(READ_ONLY_TOOL_DEFINITIONS) == 3
    for t in READ_ONLY_TOOL_DEFINITIONS:
        assert "name" in t and "input_schema" in t


def test_read_file_success(registry):
    r = registry.execute("read_file", {"path": "src/app.py"})
    assert r["status"] == "success"
    assert "def hello" in r["data"]["content"]


def test_read_file_denied_env(registry, tmp_path):
    (tmp_path / ".env").write_text("X=1", encoding="utf-8")
    r = registry.execute("read_file", {"path": ".env"})
    assert r["status"] == "error"
    assert "敏感" in r["summary"]


def test_list_dir(registry):
    r = registry.execute("list_dir", {"path": "."})
    assert r["status"] == "success"
    names = {e["name"] for e in r["data"]["entries"]}
    assert "src" in names
    assert ".env" not in names


def test_unknown_tool(registry):
    r = registry.execute("write_file", {"path": "x"})
    assert r["status"] == "error"


def test_result_has_next_actions(registry):
    r = registry.execute("read_file", {"path": "readme.md"})
    assert "next_actions" in r
    assert isinstance(r["next_actions"], list)
