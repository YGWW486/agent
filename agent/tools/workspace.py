"""工作区路径沙箱 — 所有只读工具的唯一路径入口"""

from __future__ import annotations

import os
import re
from pathlib import Path

from config.settings import get_settings


class WorkspaceError(Exception):
    """路径解析或访问策略违规"""


# 敏感路径模式（相对 workspace root）
_DENY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(^|/)\.env$"),
    re.compile(r"(^|/)\.env\.[^/]+$"),
    re.compile(r"(^|/)credentials\.json$"),
    re.compile(r".*\.pem$"),
    re.compile(r".*\.key$"),
]


def resolve_workspace_root(
    *,
    state_root: str = "",
    settings_root: str | None = None,
) -> Path:
    """解析工作区根：state > settings > cwd"""
    raw = (state_root or "").strip()
    if not raw:
        settings = get_settings()
        raw = (settings_root if settings_root is not None else settings.WORKSPACE_ROOT).strip()
    if not raw:
        raw = os.getcwd()
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise WorkspaceError(f"工作区根目录不存在或不是目录: {root}")
    return root


class WorkspaceGuard:
    """将相对路径解析为 workspace 内的绝对路径，并执行敏感文件策略"""

    def __init__(self, root: Path):
        self.root = root.resolve()

    @classmethod
    def from_state(cls, state: dict) -> WorkspaceGuard:
        return cls(resolve_workspace_root(state_root=state.get("workspace_root", "")))

    def resolve(self, rel_path: str) -> Path:
        """解析相对路径；拒绝越界与敏感文件"""
        if not rel_path or not str(rel_path).strip():
            rel_path = "."

        normalized = str(rel_path).replace("\\", "/").strip()
        if ".." in Path(normalized).parts:
            raise WorkspaceError(f"路径不允许包含 '..': {rel_path}")

        candidate = (self.root / normalized).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise WorkspaceError(f"路径越出工作区: {rel_path}") from None

        if self.is_denied(candidate):
            raise WorkspaceError(f"敏感文件不可读取: {rel_path}")

        return candidate

    def is_denied(self, path: Path) -> bool:
        """检查路径是否命中敏感文件策略（基于相对路径）"""
        try:
            rel = path.resolve().relative_to(self.root)
        except ValueError:
            return True
        rel_posix = rel.as_posix()
        for pat in _DENY_PATTERNS:
            if pat.search(rel_posix):
                return True
        return False
