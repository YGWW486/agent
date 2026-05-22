"""WorkspaceGuard 单元测试"""

import os
import pytest
from pathlib import Path

from agent.tools.workspace import WorkspaceGuard, WorkspaceError, resolve_workspace_root


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    return WorkspaceGuard(tmp_path)


def test_resolve_relative_file(ws, tmp_path):
    p = ws.resolve("src/main.py")
    assert p == (tmp_path / "src" / "main.py").resolve()


def test_resolve_dot_parent_rejected(ws):
    with pytest.raises(WorkspaceError, match="\\.\\."):
        ws.resolve("../outside")


def test_resolve_env_denied(ws):
    with pytest.raises(WorkspaceError, match="敏感"):
        ws.resolve(".env")


def test_resolve_env_nested_denied(ws, tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / ".env.local").write_text("x=1", encoding="utf-8")
    with pytest.raises(WorkspaceError):
        ws.resolve("config/.env.local")


def test_is_denied_pem(ws, tmp_path):
    (tmp_path / "certs").mkdir()
    key = tmp_path / "certs" / "server.pem"
    key.write_text("-----", encoding="utf-8")
    assert ws.is_denied(key)


def test_resolve_workspace_root_defaults_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    root = resolve_workspace_root()
    assert root == Path(tmp_path).resolve()


def test_from_state_overrides_settings(tmp_path, monkeypatch):
    other = tmp_path / "project"
    other.mkdir()
    guard = WorkspaceGuard.from_state({"workspace_root": str(other)})
    assert guard.root == other.resolve()
