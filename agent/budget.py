"""Token 预算治理 — 日累计与单任务上限"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import get_settings

logger = logging.getLogger(__name__)

DAILY_BUDGET_PATH = Path("data/token_budget.json")


class BudgetExceeded(Exception):
    """Token 预算超限"""

    def __init__(self, message: str, kind: str = "task"):
        super().__init__(message)
        self.kind = kind  # "task" | "daily"


def usage_total(usage: dict[str, int]) -> int:
    """将 LLM provider 的 usage 字典折合为单一 token 计数"""
    return (
        usage.get("input", 0)
        + usage.get("output", 0)
        + usage.get("cache_read", 0)
        + usage.get("reasoning", 0)
    )


def task_tokens_from_state(state: dict[str, Any]) -> int:
    return int(state.get("tokens_input", 0)) + int(state.get("tokens_output", 0))


def record_node_usage(state: dict[str, Any], llm: Any) -> dict[str, int]:
    """根据 LLM 累计 usage（workflow 启动时已 reset）更新 state 中的 token 字段"""
    usage = llm.token_usage()
    tokens_input = usage.get("input", 0) + usage.get("cache_read", 0)
    tokens_output = usage.get("output", 0) + usage.get("reasoning", 0)
    return {
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
    }


def check_task_budget(state: dict[str, Any]) -> None:
    settings = get_settings()
    total = task_tokens_from_state(state)
    if total >= settings.TASK_TOKEN_LIMIT:
        raise BudgetExceeded(
            f"任务 Token 超限 ({total} >= {settings.TASK_TOKEN_LIMIT})",
            kind="task",
        )


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_daily_record() -> dict[str, Any]:
    if not DAILY_BUDGET_PATH.exists():
        return {"date": _today_utc(), "total_tokens": 0}
    try:
        data = json.loads(DAILY_BUDGET_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[Budget] Failed to load daily record: {e}")
        return {"date": _today_utc(), "total_tokens": 0}

    if data.get("date") != _today_utc():
        return {"date": _today_utc(), "total_tokens": 0}
    return data


def _save_daily_record(data: dict[str, Any]) -> None:
    DAILY_BUDGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    DAILY_BUDGET_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def check_daily_budget() -> None:
    """启动新 workflow 前检查日预算"""
    settings = get_settings()
    data = _load_daily_record()
    if data["total_tokens"] >= settings.DAILY_TOKEN_BUDGET:
        raise BudgetExceeded(
            f"每日 Token 预算已用尽 ({data['total_tokens']} >= {settings.DAILY_TOKEN_BUDGET})",
            kind="daily",
        )


def add_task_tokens_to_daily(state: dict[str, Any], prev_state: dict[str, Any]) -> None:
    """将本节点新增的 token 计入日累计"""
    prev_total = task_tokens_from_state(prev_state)
    new_total = task_tokens_from_state(state)
    delta = max(0, new_total - prev_total)
    if delta == 0:
        return

    data = _load_daily_record()
    data["total_tokens"] = int(data.get("total_tokens", 0)) + delta
    _save_daily_record(data)
    logger.debug(f"[Budget] Daily +{delta} → {data['total_tokens']}")
