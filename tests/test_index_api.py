"""index 端点集成测试"""
import json
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from bridge.server import app
from agent.context import reset_graph_index


@pytest.fixture(autouse=True)
def _reset_index():
    """每个测试前重置单例索引，保证测试隔离"""
    reset_graph_index()


@pytest.fixture
def sample_graph_json(tmp_path):
    """创建最小合法 graph.json"""
    data = {
        "nodes": [
            {"id": "n1", "label": "Node One", "file_type": "code",
             "source_file": "src/a.py", "source_location": "L1"},
            {"id": "n2", "label": "Node Two", "file_type": "code",
             "source_file": "src/b.py", "source_location": "L5"},
        ],
        "links": [
            {"source": "n1", "target": "n2", "relation": "calls",
             "confidence": "EXTRACTED", "confidence_score": 1.0,
             "source_file": "src/a.py"},
        ],
        "hyperedges": []
    }
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(data))
    return path


@pytest.mark.asyncio
async def test_rebuild_ok(sample_graph_json):
    """合法路径 → 200 + 统计字段"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/index/rebuild", json={
            "graph_path": str(sample_graph_json)
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["node_count"] == 2
    assert body["edge_count"] == 1
    assert body["files_indexed"] == 2


@pytest.mark.asyncio
async def test_rebuild_file_not_found():
    """不存在路径 → 400"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/index/rebuild", json={
            "graph_path": "Z:/nonexistent/graph.json"
        })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_context_no_index():
    """未加载直接查询 → 200 + status: no_index"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/context", params={"files": "src/a.py"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "no_index"


@pytest.mark.asyncio
async def test_context_with_files(sample_graph_json):
    """加载后查询 → 200 + 节点数据"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 先加载
        await client.post("/api/index/rebuild", json={
            "graph_path": str(sample_graph_json)
        })
        # 再查询
        resp = await client.get("/api/context", params={
            "files": "src/a.py", "depth": "1"
        })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["nodes"]) == 2  # n1 + n2 via depth=1
    assert len(body["edges"]) == 1
    assert "src/a.py" in body["file_summaries"]
