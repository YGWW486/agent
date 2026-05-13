"""GraphIndex 单元测试"""
import json
import pytest
from pathlib import Path
from agent.context import GraphIndex


@pytest.fixture
def sample_graph_json(tmp_path):
    """创建最小合法 graph.json"""
    data = {
        "nodes": [
            {"id": "auth_login", "label": "Login Handler", "file_type": "code",
             "source_file": "src/auth.py", "source_location": "L42-L68"},
            {"id": "db_query", "label": "Query User", "file_type": "code",
             "source_file": "src/db.py", "source_location": "L10-L25"},
            {"id": "auth_model", "label": "User Model", "file_type": "code",
             "source_file": "src/models.py", "source_location": "L1-L15"},
        ],
        "links": [
            {"source": "auth_login", "target": "db_query", "relation": "calls",
             "confidence": "EXTRACTED", "confidence_score": 1.0,
             "source_file": "src/auth.py"},
            {"source": "db_query", "target": "auth_model", "relation": "references",
             "confidence": "EXTRACTED", "confidence_score": 1.0,
             "source_file": "src/db.py"},
        ],
        "hyperedges": []
    }
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(data))
    return graph_path


def test_load_valid_graph_json(sample_graph_json):
    """加载合法 graph.json，验证 node/edge 计数"""
    index = GraphIndex()
    result = index.load(sample_graph_json)

    assert result["node_count"] == 3
    assert result["edge_count"] == 2
    assert result["files_indexed"] == 3
    assert result["status"] == "ok"


def test_query_by_files_bfs(sample_graph_json):
    """按文件查询，BFS 扩展 1 层"""
    index = GraphIndex()
    index.load(sample_graph_json)

    result = index.query(["src/auth.py"], depth=1)

    assert len(result["nodes"]) == 2  # auth_login + db_query
    assert len(result["edges"]) == 1  # auth_login → db_query
    node_ids = {n["id"] for n in result["nodes"]}
    assert node_ids == {"auth_login", "db_query"}


def test_query_by_files_bfs_depth2(sample_graph_json):
    """BFS 扩展 2 层，覆盖全图"""
    index = GraphIndex()
    index.load(sample_graph_json)

    result = index.query(["src/auth.py"], depth=2)

    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2


def test_query_unknown_file(sample_graph_json):
    """查询不存在的文件，返回空结果"""
    index = GraphIndex()
    index.load(sample_graph_json)

    result = index.query(["src/nonexistent.py"], depth=2)

    assert len(result["nodes"]) == 0
    assert len(result["edges"]) == 0
    assert result["file_summaries"] == {}


def test_load_invalid_json(tmp_path):
    """加载损坏的 JSON，抛出 LoadError"""
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("not json {{{")

    index = GraphIndex()
    with pytest.raises(index.LoadError):
        index.load(bad_path)


def test_load_missing_keys(tmp_path):
    """有 nodes 但缺 links 键"""
    data = {"nodes": [{"id": "x", "label": "X", "file_type": "code",
                       "source_file": "f.py", "source_location": ""}]}
    path = tmp_path / "partial.json"
    path.write_text(json.dumps(data))

    index = GraphIndex()
    with pytest.raises(index.LoadError, match="links"):
        index.load(path)


def test_file_summaries(sample_graph_json):
    """验证摘要聚合 — 每文件的所有节点 label 拼接"""
    index = GraphIndex()
    index.load(sample_graph_json)

    result = index.query(["src/auth.py", "src/db.py"], depth=0)

    assert "src/auth.py" in result["file_summaries"]
    assert "Login Handler" in result["file_summaries"]["src/auth.py"]
    assert "src/db.py" in result["file_summaries"]
    assert "Query User" in result["file_summaries"]["src/db.py"]


def test_query_no_index():
    """索引未加载时查询，返回 no_index 状态"""
    index = GraphIndex()
    result = index.query(["src/auth.py"])
    assert result["status"] == "no_index"


def test_load_twice_overwrites(sample_graph_json, tmp_path):
    """第二次加载覆盖第一次的索引"""
    index = GraphIndex()
    index.load(sample_graph_json)

    data2 = {
        "nodes": [{"id": "single", "label": "Only", "file_type": "code",
                   "source_file": "a.py", "source_location": ""}],
        "links": []
    }
    path2 = tmp_path / "graph2.json"
    path2.write_text(json.dumps(data2))

    index.load(path2)
    result = index.query(["a.py"], depth=0)
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["id"] == "single"
