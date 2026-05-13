"""GraphIndex — graph.json 内存索引，提供 BFS 上下文查询"""
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


class GraphIndex:
    """加载 graphify 生成的 graph.json，构建内存索引，按文件-BFS 查询子图"""

    class LoadError(Exception):
        """graph.json 加载失败"""

    def __init__(self):
        self._nodes_by_id: dict[str, dict] = {}
        self._nodes_by_file: dict[str, list[str]] = {}
        self._adjacency: dict[str, list[dict]] = {}
        self._file_summaries: dict[str, str] = {}
        self._loaded_at: Optional[datetime] = None
        self._source_path: Optional[Path] = None

    def load(self, graph_path: str | Path) -> dict:
        """加载 graph.json 到内存索引。"""
        path = Path(graph_path)
        if not path.exists():
            raise self.LoadError(f"graph.json 不存在: {path}")
        if not path.is_file():
            raise self.LoadError(f"不是文件: {path}")

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise self.LoadError(f"JSON 解析失败: {e}")

        if "nodes" not in raw:
            raise self.LoadError("缺少 'nodes' 键")
        if "links" not in raw:
            raise self.LoadError("缺少 'links' 键")

        self._build_index(raw, path)
        self._save_snapshot()

        settings = get_settings()
        settings.GRAPH_JSON_PATH = str(path.resolve())

        return {
            "status": "ok",
            "node_count": len(raw["nodes"]),
            "edge_count": len(raw["links"]),
            "hyperedges_count": len(raw.get("hyperedges", [])),
            "files_indexed": len(self._file_summaries),
            "loaded_at": self._loaded_at.isoformat() if self._loaded_at else None,
        }

    def query(self, files: list[str], depth: int = 2) -> dict:
        """按文件 BFS 查询上下文子图。"""
        if self._loaded_at is None:
            return {"status": "no_index",
                    "message": "索引未加载，请先 POST /api/index/rebuild"}

        depth = max(0, min(depth, 3))

        # files 为空 → 返回全部文件的摘要（Planner 全仓概览模式）
        if not files:
            return {
                "nodes": [],
                "edges": [],
                "file_summaries": dict(self._file_summaries),
            }

        start_ids: set[str] = set()
        for f in files:
            for nid in self._nodes_by_file.get(f, []):
                start_ids.add(nid)

        if not start_ids:
            return {"nodes": [], "edges": [], "file_summaries": {}}

        visited: set[str] = set(start_ids)
        edge_set: set[tuple[str, str]] = set()
        frontier = start_ids

        for _ in range(depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                for edge in self._adjacency.get(nid, []):
                    target = edge["target"]
                    if target not in visited:
                        visited.add(target)
                        next_frontier.add(target)
                        edge_set.add((nid, target))
            frontier = next_frontier
            if not frontier:
                break

        nodes_out = [self._nodes_by_id[nid] for nid in visited if nid in self._nodes_by_id]
        edges_out = [
            {"source": u, "target": v, "relation": "", "confidence": "",
             "confidence_score": 0.0}
            for u, v in edge_set
        ]
        for edge_dict in edges_out:
            u, v = edge_dict["source"], edge_dict["target"]
            for orig in self._adjacency.get(u, []):
                if orig["target"] == v:
                    edge_dict["relation"] = orig.get("relation", "")
                    edge_dict["confidence"] = orig.get("confidence", "")
                    edge_dict["confidence_score"] = orig.get("confidence_score", 0.0)
                    break

        related_files: set[str] = set()
        for node in nodes_out:
            sf = node.get("source_file", "")
            if sf:
                related_files.add(sf)
        summaries = {f: self._file_summaries.get(f, "") for f in related_files}

        return {"nodes": nodes_out, "edges": edges_out, "file_summaries": summaries}

    def is_loaded(self) -> bool:
        return self._loaded_at is not None

    def stats(self) -> dict:
        return {
            "loaded": self._loaded_at is not None,
            "node_count": len(self._nodes_by_id),
            "edge_count": sum(len(v) for v in self._adjacency.values()),
            "files_indexed": len(self._file_summaries),
            "source_path": str(self._source_path) if self._source_path else None,
            "loaded_at": self._loaded_at.isoformat() if self._loaded_at else None,
        }

    def _build_index(self, raw: dict, path: Path) -> None:
        self._nodes_by_id.clear()
        self._nodes_by_file.clear()
        self._adjacency.clear()
        self._file_summaries.clear()

        for node in raw["nodes"]:
            nid = node["id"]
            self._nodes_by_id[nid] = {
                "id": nid,
                "label": node.get("label", nid),
                "file_type": node.get("file_type", ""),
                "source_file": node.get("source_file", ""),
                "source_location": node.get("source_location", ""),
            }
            sf = node.get("source_file", "")
            if sf:
                self._nodes_by_file.setdefault(sf, []).append(nid)

        for link in raw["links"]:
            src = link["source"]
            tgt = link.get("target", "")
            if src not in self._nodes_by_id:
                logger.warning("Skipping link: source node %s not found in nodes", src)
                continue
            if not tgt:
                logger.warning("Skipping link: target is empty for source %s", src)
                continue
            self._adjacency.setdefault(src, []).append({
                "target": tgt,
                "relation": link.get("relation", ""),
                "confidence": link.get("confidence", ""),
                "confidence_score": link.get("confidence_score", 0.0),
            })

        for sf, nids in self._nodes_by_file.items():
            labels = [self._nodes_by_id[n]["label"] for n in nids if n in self._nodes_by_id]
            self._file_summaries[sf] = ", ".join(labels[:20])

        self._loaded_at = datetime.now(timezone.utc)
        self._source_path = path

    def _save_snapshot(self) -> None:
        settings = get_settings()
        db_path = Path(settings.GRAPH_INDEX_DB)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE IF EXISTS graph_snapshot")
        conn.execute(
            "CREATE TABLE graph_snapshot ("
            "  nodes_json TEXT,"
            "  edges_json TEXT,"
            "  source_path TEXT,"
            "  loaded_at TEXT"
            ")"
        )
        nodes_json = json.dumps(list(self._nodes_by_id.values()), ensure_ascii=False)
        edges_json = json.dumps(
            [{"source": k, "target": v["target"], "relation": v.get("relation", ""),
              "confidence": v.get("confidence", ""), "confidence_score": v.get("confidence_score", 0.0)}
             for k, vals in self._adjacency.items() for v in vals],
            ensure_ascii=False,
        )
        conn.execute(
            "INSERT INTO graph_snapshot VALUES (?, ?, ?, ?)",
            (
                nodes_json,
                edges_json,
                str(self._source_path) if self._source_path else "",
                self._loaded_at.isoformat() if self._loaded_at else "",
            ),
        )
        conn.commit()
        conn.close()
        logger.info(f"GraphIndex snapshot saved to {db_path} ({len(self._nodes_by_id)} nodes, "
                    f"{sum(len(v) for v in self._adjacency.values())} edges)")

    def load_snapshot(self) -> dict | None:
        """从 SQLite 恢复上次的索引快照。"""
        settings = get_settings()
        db_path = Path(settings.GRAPH_INDEX_DB)
        if not db_path.exists():
            return None

        try:
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT nodes_json, edges_json, source_path, loaded_at FROM graph_snapshot"
            ).fetchone()
            conn.close()

            if row is None:
                return None

            nodes_json, edges_json, source_path, loaded_at = row
            raw = {
                "nodes": json.loads(nodes_json),
                "links": json.loads(edges_json) if edges_json else [],
                "hyperedges": [],
            }
            self._build_index(raw, Path(source_path) if source_path else Path("."))
            self._loaded_at = datetime.fromisoformat(loaded_at) if loaded_at else None
            logger.info(f"GraphIndex restored from snapshot: {len(self._nodes_by_id)} nodes")
            return {
                "status": "ok",
                "node_count": len(raw["nodes"]),
                "edge_count": len(raw["links"]),
                "loaded_at": loaded_at,
            }
        except Exception as e:
            logger.warning(f"Failed to load snapshot from {db_path}: {e}")
            return None


_index: Optional[GraphIndex] = None


def get_graph_index() -> GraphIndex:
    global _index
    if _index is None:
        _index = GraphIndex()
    return _index


def reset_graph_index() -> None:
    """重置单例索引（用于测试隔离）"""
    global _index
    _index = None
