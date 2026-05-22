"""只读工具注册表 — read_file / list_dir / search_repo"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any, Literal, TypedDict

from agent.context import GraphIndex
from agent.tools.workspace import WorkspaceError, WorkspaceGuard
from config.settings import get_settings

logger = logging.getLogger(__name__)


class ToolResult(TypedDict):
    status: Literal["success", "warning", "error"]
    summary: str
    data: dict[str, Any]
    next_actions: list[str]


READ_ONLY_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "读取工作区内文本文件内容（相对项目根路径）",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对路径，如 src/main.py"},
                "offset": {"type": "integer", "description": "起始行号（1-based），可选"},
                "limit": {"type": "integer", "description": "最多读取行数，可选"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_dir",
        "description": "列出工作区内目录内容（非递归）",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对路径，默认 ."},
            },
        },
    },
    {
        "name": "search_repo",
        "description": "在仓库中搜索：mode=text 用 ripgrep；mode=graph 用知识图谱邻域",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词或文件名片段"},
                "mode": {
                    "type": "string",
                    "enum": ["text", "graph", "auto"],
                    "description": "text=ripgrep, graph=GraphIndex, auto=有索引则 graph 否则 text",
                },
            },
            "required": ["query"],
        },
    },
]


def _ok(summary: str, data: dict | None = None) -> ToolResult:
    return {
        "status": "success",
        "summary": summary,
        "data": data or {},
        "next_actions": [],
    }


def _warn(summary: str, data: dict | None = None) -> ToolResult:
    return {
        "status": "warning",
        "summary": summary,
        "data": data or {},
        "next_actions": [],
    }


def _err(summary: str, data: dict | None = None) -> ToolResult:
    return {
        "status": "error",
        "summary": summary,
        "data": data or {},
        "next_actions": [],
    }


class ToolRegistry:
    """执行只读工具调用"""

    def __init__(self, workspace: WorkspaceGuard, index: GraphIndex | None = None):
        self.workspace = workspace
        self.index = index

    def execute(self, name: str, tool_input: dict[str, Any]) -> ToolResult:
        handlers = {
            "read_file": self._read_file,
            "list_dir": self._list_dir,
            "search_repo": self._search_repo,
        }
        handler = handlers.get(name)
        if not handler:
            return _err(f"未知工具: {name}")
        try:
            return handler(tool_input or {})
        except WorkspaceError as e:
            return _err(str(e))
        except Exception as e:
            logger.exception(f"[ToolRegistry] {name} failed")
            return _err(f"{name} 执行失败: {e}")

    def _read_file(self, inp: dict[str, Any]) -> ToolResult:
        settings = get_settings()
        path = inp.get("path", "")
        resolved = self.workspace.resolve(path)

        if not resolved.is_file():
            return _err(f"不是文件: {path}")

        raw = resolved.read_bytes()
        max_bytes = settings.READ_FILE_MAX_BYTES
        truncated = len(raw) > max_bytes
        if truncated:
            raw = raw[:max_bytes]

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return _err(f"非 UTF-8 文本文件: {path}")

        lines = text.splitlines()
        offset = int(inp.get("offset") or 1)
        limit = inp.get("limit")
        if offset < 1:
            offset = 1
        start = offset - 1
        if limit is not None:
            end = start + int(limit)
            slice_lines = lines[start:end]
        else:
            slice_lines = lines[start:]

        numbered = "\n".join(
            f"{start + i + 1}|{line}" for i, line in enumerate(slice_lines)
        )
        summary = f"已读取 {path}（{len(slice_lines)} 行）"
        if truncated:
            summary += f"，文件已截断至 {max_bytes} 字节"
            return _warn(
                summary,
                {"path": path, "content": numbered, "truncated": True},
            )
        return _ok(summary, {"path": path, "content": numbered, "truncated": False})

    def _list_dir(self, inp: dict[str, Any]) -> ToolResult:
        rel = inp.get("path") or "."
        resolved = self.workspace.resolve(rel)

        if not resolved.is_dir():
            return _err(f"不是目录: {rel}")

        entries: list[dict[str, str]] = []
        for child in sorted(resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name.startswith("."):
                continue
            rel_child = child.relative_to(self.workspace.root).as_posix()
            if self.workspace.is_denied(child):
                entries.append({"name": child.name, "type": "denied"})
            else:
                entries.append({
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "path": rel_child,
                })

        return _ok(
            f"列出 {rel}：{len(entries)} 项",
            {"path": rel, "entries": entries},
        )

    def _search_repo(self, inp: dict[str, Any]) -> ToolResult:
        query = (inp.get("query") or "").strip()
        if not query:
            return _err("query 不能为空")

        mode = (inp.get("mode") or "auto").lower()
        index_loaded = self.index is not None and self.index.is_loaded()

        if mode == "graph" or (mode == "auto" and index_loaded):
            result = self._search_graph(query)
            if result["status"] != "error" and (
                result["data"].get("matches") or result["data"].get("file_summaries")
            ):
                return result
            if mode == "graph":
                return result

        return self._search_ripgrep(query)

    def _search_graph(self, query: str) -> ToolResult:
        if self.index is None or not self.index.is_loaded():
            return _warn("GraphIndex 未加载", {"matches": []})

        settings = get_settings()
        overview = self.index.query([], depth=0)
        summaries = overview.get("file_summaries", {})
        q_lower = query.lower()
        matched_files = [
            f for f in summaries if q_lower in f.lower() or q_lower in summaries[f].lower()
        ][: settings.CODER_CONTEXT_MAX_FILES]

        if not matched_files:
            return _warn(f"图谱未找到与 '{query}' 相关的文件", {"matches": []})

        subgraph = self.index.query(matched_files, depth=settings.CODER_CONTEXT_DEPTH)
        return _ok(
            f"图谱搜索 '{query}'：{len(matched_files)} 个文件",
            {
                "mode": "graph",
                "files": matched_files,
                "file_summaries": subgraph.get("file_summaries", {}),
                "node_count": len(subgraph.get("nodes", [])),
                "edge_count": len(subgraph.get("edges", [])),
            },
        )

    def _search_ripgrep(self, query: str) -> ToolResult:
        settings = get_settings()
        root = str(self.workspace.root)
        cmd = [
            "rg",
            "--line-number",
            "--no-heading",
            "--max-count",
            str(settings.SEARCH_RG_MAX_RESULTS),
            query,
            ".",
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=settings.SEARCH_RG_TIMEOUT_SEC,
            )
        except FileNotFoundError:
            return _err("ripgrep (rg) 未安装，请使用 mode=graph 或安装 rg")
        except subprocess.TimeoutExpired:
            return _warn(f"ripgrep 超时（>{settings.SEARCH_RG_TIMEOUT_SEC}s）", {"matches": []})

        if proc.returncode not in (0, 1):
            return _err(f"ripgrep 失败: {proc.stderr.strip() or proc.returncode}")

        lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
        matches = []
        for ln in lines[: settings.SEARCH_RG_MAX_RESULTS]:
            parts = ln.split(":", 2)
            if len(parts) >= 3:
                matches.append({
                    "path": parts[0],
                    "line": int(parts[1]) if parts[1].isdigit() else parts[1],
                    "text": parts[2],
                })
            else:
                matches.append({"raw": ln})

        if not matches:
            return _warn(f"未找到与 '{query}' 匹配的文本", {"mode": "text", "matches": []})

        return _ok(
            f"文本搜索 '{query}'：{len(matches)} 条",
            {"mode": "text", "matches": matches},
        )


def tool_result_to_text(name: str, result: ToolResult) -> str:
    """供 LLM tool_result 消息使用的紧凑文本"""
    payload = {"tool": name, **result}
    return json.dumps(payload, ensure_ascii=False)
