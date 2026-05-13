"""工作流持久化 — JSON 文件存储，重启可恢复"""
import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STORE_DIR = Path("data/workflows")


def _ensure_dir() -> None:
    os.makedirs(STORE_DIR, exist_ok=True)


def save(thread_id: str, state: dict) -> None:
    """保存工作流状态到磁盘"""
    _ensure_dir()
    try:
        # 不持久化 event_queue（不可序列化）
        clean = {k: v for k, v in state.items() if k != "_event_queue"}
        (STORE_DIR / f"{thread_id}.json").write_text(
            json.dumps(clean, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"[Store] Failed to save {thread_id}: {e}")


def load(thread_id: str) -> dict | None:
    """从磁盘加载工作流状态"""
    path = STORE_DIR / f"{thread_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[Store] Failed to load {thread_id}: {e}")
        return None


def load_all() -> dict[str, dict]:
    """加载所有已保存的工作流"""
    _ensure_dir()
    result: dict[str, dict] = {}
    for path in sorted(STORE_DIR.glob("*.json")):
        tid = path.stem
        state = load(tid)
        if state:
            result[tid] = state
    return result


def remove(thread_id: str) -> None:
    """删除工作流"""
    path = STORE_DIR / f"{thread_id}.json"
    if path.exists():
        path.unlink()
