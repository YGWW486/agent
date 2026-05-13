"""GraphIndex API — graph.json 加载与上下文查询"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.context import get_graph_index

logger = logging.getLogger(__name__)
router = APIRouter(tags=["index"])


class RebuildRequest(BaseModel):
    graph_path: str


@router.post("/index/rebuild")
async def rebuild_index(req: RebuildRequest):
    """加载 graph.json 到内存索引"""
    index = get_graph_index()
    graph_path = Path(req.graph_path)

    if not graph_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"graph.json 不存在: {req.graph_path}",
        )

    try:
        result = index.load(graph_path)
        logger.info(
            f"[Index] Loaded: {result['node_count']} nodes, "
            f"{result['edge_count']} edges, "
            f"{result['files_indexed']} files"
        )
        return result
    except index.LoadError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/context")
async def get_context(files: str, depth: int = 2):
    """按文件 BFS 查询项目上下文子图"""
    index = get_graph_index()
    file_list = [f.strip() for f in files.split(",") if f.strip()]
    if not file_list:
        return {"status": "ok", "nodes": [], "edges": [], "file_summaries": {}}

    result = index.query(file_list, depth=depth)
    return result
