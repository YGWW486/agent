"""按需组装 Planner/Coder 项目上下文 — 基于 GraphIndex，避免全仓灌 prompt"""

from __future__ import annotations

import logging
from typing import Any

from agent.context import get_graph_index
from agent.models import Task
from config.settings import get_settings

logger = logging.getLogger(__name__)

_TRUNCATION_SUFFIX = "\n...(已截断)"
_MAX_NODES_DISPLAY = 40
_MAX_EDGES_DISPLAY = 60


def _fallback_context(state: dict) -> str:
    return state.get("context") or "无额外上下文"


def _apply_char_cap(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    keep = max_chars - len(_TRUNCATION_SUFFIX)
    if keep < 0:
        keep = 0
    return text[:keep] + _TRUNCATION_SUFFIX


def _format_file_summary_lines(
    summaries: dict[str, str],
    *,
    max_files: int,
    header: str,
    hidden_hint: str,
) -> list[str]:
    items = sorted(summaries.items())
    shown = items[:max_files]
    hidden = len(items) - len(shown)
    lines = [header]
    for filepath, summary in shown:
        lines.append(f"  - {filepath}: {summary}")
    if hidden > 0:
        lines.append(hidden_hint.format(hidden=hidden))
    return lines


def build_planner_context(state: dict) -> str:
    """Planner：全局 stats + capped 文件摘要列表"""
    settings = get_settings()
    index = get_graph_index()

    if not index.is_loaded():
        return _fallback_context(state)

    stats = index.stats()
    if stats["files_indexed"] == 0:
        return "已加载索引但未找到文件上下文"

    result = index.query(files=[], depth=0)
    if result.get("status") == "no_index":
        return "索引不可用"

    summaries = result.get("file_summaries", {})
    if not summaries:
        return "已加载索引但未找到文件摘要"

    max_files = settings.PLANNER_CONTEXT_MAX_FILES
    shown_count = min(len(summaries), max_files)
    header = (
        f"项目共 {stats['files_indexed']} 个文件，{stats['node_count']} 个符号节点"
        f"（展示前 {shown_count} 个）："
    )
    hidden_hint = "另有 {hidden} 个文件未展示；请在 Task file_scope 中指定路径。"
    lines = _format_file_summary_lines(
        summaries,
        max_files=max_files,
        header=header,
        hidden_hint=hidden_hint,
    )
    return _apply_char_cap("\n".join(lines), settings.CONTEXT_MAX_CHARS)


def _build_capped_overview(
    *,
    max_files: int,
    preamble: str,
    hidden_hint: str,
) -> str:
    settings = get_settings()
    index = get_graph_index()
    stats = index.stats()
    result = index.query(files=[], depth=0)
    summaries = result.get("file_summaries", {})
    if not summaries:
        return preamble + "\n已加载索引但未找到文件摘要。"

    shown_count = min(len(summaries), max_files)
    header = (
        f"{preamble}\n"
        f"项目共 {stats['files_indexed']} 个文件，{stats['node_count']} 个符号节点"
        f"（展示前 {shown_count} 个）："
    )
    lines = _format_file_summary_lines(
        summaries,
        max_files=max_files,
        header=header,
        hidden_hint=hidden_hint,
    )
    return _apply_char_cap("\n".join(lines), settings.CONTEXT_MAX_CHARS)


def format_subgraph(
    query_result: dict[str, Any],
    *,
    max_chars: int | None = None,
) -> str:
    """将 BFS 子图格式化为可读文本"""
    settings = get_settings()
    cap = max_chars if max_chars is not None else settings.CONTEXT_MAX_CHARS

    summaries: dict[str, str] = query_result.get("file_summaries", {})
    nodes: list[dict] = query_result.get("nodes", [])
    edges: list[dict] = query_result.get("edges", [])

    lines: list[str] = []

    if summaries:
        lines.append("## 相关文件摘要")
        for filepath, summary in sorted(summaries.items()):
            lines.append(f"- {filepath}: {summary}")

    if nodes:
        total_nodes = len(nodes)
        display_nodes = nodes[:_MAX_NODES_DISPLAY]
        lines.append(f"\n## 符号节点 ({total_nodes})")
        for node in display_nodes:
            nid = node.get("id", "")
            label = node.get("label", nid)
            sf = node.get("source_file", "")
            loc = node.get("source_location", "")
            loc_part = f" {loc}" if loc else ""
            lines.append(f"- {nid} [{sf}{loc_part}]: {label}")
        if total_nodes > _MAX_NODES_DISPLAY:
            lines.append(f"... 另有 {total_nodes - _MAX_NODES_DISPLAY} 个节点已省略")

    if edges:
        total_edges = len(edges)
        display_edges = edges[:_MAX_EDGES_DISPLAY]
        lines.append(f"\n## 关系 ({total_edges})")
        for edge in display_edges:
            rel = edge.get("relation") or "relates"
            lines.append(f"- {edge.get('source')} --{rel}--> {edge.get('target')}")
        if total_edges > _MAX_EDGES_DISPLAY:
            lines.append(f"... 另有 {total_edges - _MAX_EDGES_DISPLAY} 条边已省略")

    if not lines:
        return "子图为空：file_scope 中的路径在索引中未找到匹配节点。"

    return _apply_char_cap("\n".join(lines), cap)


def build_coder_context(state: dict, task: Task) -> str:
    """Coder：按 file_scope BFS；空 scope 时降级为 capped 概览"""
    settings = get_settings()
    index = get_graph_index()

    if not index.is_loaded():
        return _fallback_context(state)

    stats = index.stats()
    if stats["files_indexed"] == 0:
        return _fallback_context(state)

    scope = [f for f in task.file_scope if f and f.strip()]

    if not scope:
        text = _build_capped_overview(
            max_files=settings.CODER_CONTEXT_MAX_FILES,
            preamble="未指定 file_scope，仅提供摘要概览：",
            hidden_hint="另有 {hidden} 个文件未展示。",
        )
        user_ctx = state.get("context", "").strip()
        if user_ctx:
            return f"{text}\n\n## 用户补充上下文\n{user_ctx}"
        return text

    result = index.query(scope, depth=settings.CODER_CONTEXT_DEPTH)
    if result.get("status") == "no_index":
        return _fallback_context(state)

    subgraph = format_subgraph(result)
    if not result.get("nodes") and not result.get("file_summaries"):
        subgraph = (
            f"file_scope {scope!r} 在索引中未找到匹配节点。\n"
            f"{subgraph}"
        )

    user_ctx = state.get("context", "").strip()
    if user_ctx:
        combined = f"{subgraph}\n\n## 用户补充上下文\n{user_ctx}"
        return _apply_char_cap(combined, settings.CONTEXT_MAX_CHARS)
    return subgraph
