"""search_repo 混合搜索测试"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent.context import GraphIndex
from agent.tools.registry import ToolRegistry
from agent.tools.workspace import WorkspaceGuard


@pytest.fixture
def graph_index(tmp_path):
    graph = {
        "nodes": [
            {"id": "n1", "source_file": "src/auth.py", "label": "Auth", "summary": "auth module"},
        ],
        "links": [],
    }
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    idx = GraphIndex()
    idx.load(path)
    return idx


@pytest.fixture
def registry_with_index(tmp_path, graph_index):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text("def login(): pass\n", encoding="utf-8")
    ws = WorkspaceGuard(tmp_path)
    return ToolRegistry(ws, index=graph_index)


def test_search_graph_mode(registry_with_index):
    r = registry_with_index.execute("search_repo", {"query": "auth", "mode": "graph"})
    assert r["status"] == "success"
    assert r["data"]["mode"] == "graph"
    assert "auth" in str(r["data"].get("files", [])).lower()


def test_search_text_mode_mock_rg(registry_with_index):
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "src/auth.py:1:def login(): pass\n"

    with patch("agent.tools.registry.subprocess.run", return_value=mock_proc):
        r = registry_with_index.execute("search_repo", {"query": "login", "mode": "text"})

    assert r["status"] == "success"
    assert r["data"]["mode"] == "text"
    assert len(r["data"]["matches"]) >= 1


def test_search_no_rg_fallback_warning(tmp_path):
    (tmp_path / "foo.txt").write_text("hello", encoding="utf-8")
    ws = WorkspaceGuard(tmp_path)
    reg = ToolRegistry(ws, index=None)

    with patch("agent.tools.registry.subprocess.run", side_effect=FileNotFoundError):
        r = reg.execute("search_repo", {"query": "hello", "mode": "text"})

    assert r["status"] == "error"
    assert "rg" in r["summary"].lower() or "ripgrep" in r["summary"].lower()
