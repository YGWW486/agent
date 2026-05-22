"""P2 — Planner/Coder 按需上下文测试"""
import json

import pytest

from agent.context import GraphIndex, get_graph_index, reset_graph_index
from agent.context_builder import (
    build_planner_context,
    build_coder_context,
    format_subgraph,
)
from agent.models import Task, AcceptanceCondition
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _isolate_graph_index():
    reset_graph_index()
    yield
    reset_graph_index()


def _make_multi_file_graph(file_count: int) -> dict:
    nodes = []
    links = []
    for i in range(file_count):
        path = f"src/module_{i:02d}.py"
        nid = f"node_{i}"
        nodes.append({
            "id": nid,
            "label": f"Symbol{i}",
            "file_type": "code",
            "source_file": path,
            "source_location": f"L{i}-L{i + 10}",
        })
        if i > 0:
            links.append({
                "source": f"node_{i - 1}",
                "target": nid,
                "relation": "imports",
                "confidence": "EXTRACTED",
                "confidence_score": 1.0,
                "source_file": path,
            })
    return {"nodes": nodes, "links": links, "hyperedges": []}


def _load_graph(tmp_path, file_count: int) -> GraphIndex:
    data = _make_multi_file_graph(file_count)
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    index = get_graph_index()
    index.load(path)
    return index


def _settings_patch(monkeypatch, **overrides):
    base = get_settings()

    class _S:
        PLANNER_CONTEXT_MAX_FILES = overrides.get(
            "PLANNER_CONTEXT_MAX_FILES", base.PLANNER_CONTEXT_MAX_FILES
        )
        CODER_CONTEXT_DEPTH = overrides.get("CODER_CONTEXT_DEPTH", base.CODER_CONTEXT_DEPTH)
        CODER_CONTEXT_MAX_FILES = overrides.get(
            "CODER_CONTEXT_MAX_FILES", base.CODER_CONTEXT_MAX_FILES
        )
        CONTEXT_MAX_CHARS = overrides.get("CONTEXT_MAX_CHARS", base.CONTEXT_MAX_CHARS)

    monkeypatch.setattr("agent.context_builder.get_settings", lambda: _S())
    return _S


def test_planner_context_caps_file_count(tmp_path, monkeypatch):
    _load_graph(tmp_path, 50)
    _settings_patch(monkeypatch, PLANNER_CONTEXT_MAX_FILES=30, CONTEXT_MAX_CHARS=50_000)

    text = build_planner_context({"context": ""})
    assert "另有 20 个文件未展示" in text
    assert "展示前 30 个" in text
    assert text.count("  - src/module_") == 30
    assert len(text) < 50_000


def test_planner_context_no_index_fallback():
    text = build_planner_context({"context": "用户工作区说明"})
    assert text == "用户工作区说明"


def test_coder_context_bfs_scope(tmp_path, monkeypatch):
    data = {
        "nodes": [
            {"id": "auth_login", "label": "Login Handler", "file_type": "code",
             "source_file": "src/auth.py", "source_location": "L42-L68"},
            {"id": "db_query", "label": "Query User", "file_type": "code",
             "source_file": "src/db.py", "source_location": "L10-L25"},
            {"id": "other", "label": "Other", "file_type": "code",
             "source_file": "src/other.py", "source_location": "L1-L5"},
        ],
        "links": [
            {"source": "auth_login", "target": "db_query", "relation": "calls",
             "confidence": "EXTRACTED", "confidence_score": 1.0,
             "source_file": "src/auth.py"},
        ],
        "hyperedges": [],
    }
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    get_graph_index().load(path)
    _settings_patch(monkeypatch, CODER_CONTEXT_DEPTH=2, CONTEXT_MAX_CHARS=50_000)

    task = Task(
        task_id="t1",
        description="auth",
        estimated_minutes=5,
        file_scope=["src/auth.py"],
        acceptance_conditions=[AcceptanceCondition(id="AC-1", description="x")],
    )
    text = build_coder_context({"context": ""}, task)

    assert "db_query" in text
    assert "Login Handler" in text
    assert "src/other.py" not in text
    assert "module_49" not in text


def test_coder_context_empty_scope_degraded(tmp_path, monkeypatch):
    _load_graph(tmp_path, 50)
    _settings_patch(monkeypatch, CODER_CONTEXT_MAX_FILES=15, CONTEXT_MAX_CHARS=50_000)

    task = Task(
        task_id="t1",
        description="d",
        estimated_minutes=5,
        file_scope=[],
        acceptance_conditions=[],
    )
    text = build_coder_context({"context": ""}, task)

    assert "未指定 file_scope" in text
    assert text.count("  - src/module_") == 15
    assert "module_49" not in text


def test_coder_context_unknown_scope_shows_hint(tmp_path, monkeypatch):
    _load_graph(tmp_path, 3)
    _settings_patch(monkeypatch, CONTEXT_MAX_CHARS=50_000)

    task = Task(
        task_id="t1",
        description="d",
        estimated_minutes=5,
        file_scope=["src/missing.py"],
        acceptance_conditions=[],
    )
    text = build_coder_context({"context": ""}, task)
    assert "未找到匹配节点" in text


def test_coder_context_no_index_fallback():
    task = Task(
        task_id="t1",
        description="d",
        estimated_minutes=5,
        file_scope=["src/a.py"],
        acceptance_conditions=[],
    )
    text = build_coder_context({"context": "fallback ctx"}, task)
    assert text == "fallback ctx"


def test_context_respects_max_chars(monkeypatch):
    nodes = [
        {
            "id": f"n{i}",
            "label": f"Label{i}" * 20,
            "source_file": f"f{i}.py",
            "source_location": "L1",
        }
        for i in range(50)
    ]
    result = {"nodes": nodes, "edges": [], "file_summaries": {}}
    _settings_patch(monkeypatch, CONTEXT_MAX_CHARS=200)
    text = format_subgraph(result)
    assert "已截断" in text
    assert len(text) <= 200 + 20


def test_format_subgraph_edges_and_summaries():
    result = {
        "file_summaries": {"src/a.py": "Foo"},
        "nodes": [{"id": "a", "label": "A", "source_file": "src/a.py", "source_location": ""}],
        "edges": [{"source": "a", "target": "b", "relation": "calls"}],
    }
    text = format_subgraph(result, max_chars=10_000)
    assert "## 相关文件摘要" in text
    assert "## 符号节点" in text
    assert "--calls-->" in text
