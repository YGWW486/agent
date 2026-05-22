"""P1 — Token 预算测试"""
import json
from pathlib import Path

import pytest

from agent.budget import (
    BudgetExceeded,
    add_task_tokens_to_daily,
    check_daily_budget,
    check_task_budget,
    record_node_usage,
    task_tokens_from_state,
    usage_total,
    DAILY_BUDGET_PATH,
)


class FakeLLM:
    def __init__(self, usage: dict):
        self._usage = usage

    def token_usage(self) -> dict:
        return dict(self._usage)


def test_usage_total_anthropic_style():
    assert usage_total({"input": 100, "output": 50, "cache_read": 10}) == 160


def test_record_node_usage_from_llm():
    llm = FakeLLM({"input": 100, "output": 20, "cache_read": 5, "reasoning": 0})
    patch = record_node_usage({}, llm)
    assert patch["tokens_input"] == 105
    assert patch["tokens_output"] == 20


def test_check_task_budget_raises(monkeypatch):
    monkeypatch.setattr(
        "agent.budget.get_settings",
        lambda: type("S", (), {"TASK_TOKEN_LIMIT": 100})(),
    )
    with pytest.raises(BudgetExceeded) as exc:
        check_task_budget({"tokens_input": 80, "tokens_output": 30})
    assert exc.value.kind == "task"


def test_daily_budget_reset_on_new_day(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.budget.DAILY_BUDGET_PATH", tmp_path / "token_budget.json")
    monkeypatch.setattr(
        "agent.budget.get_settings",
        lambda: type("S", (), {"DAILY_TOKEN_BUDGET": 1000})(),
    )

    old = {"date": "2000-01-01", "total_tokens": 9999}
    Path(tmp_path / "token_budget.json").write_text(json.dumps(old), encoding="utf-8")

    check_daily_budget()  # should not raise — date rolled over

    add_task_tokens_to_daily(
        {"tokens_input": 10, "tokens_output": 0},
        {"tokens_input": 0, "tokens_output": 0},
    )
    data = json.loads((tmp_path / "token_budget.json").read_text(encoding="utf-8"))
    assert data["total_tokens"] == 10


def test_daily_budget_exceeded(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.budget.DAILY_BUDGET_PATH", tmp_path / "token_budget.json")
    monkeypatch.setattr(
        "agent.budget.get_settings",
        lambda: type("S", (), {"DAILY_TOKEN_BUDGET": 100})(),
    )
    from agent.budget import _today_utc

    (tmp_path / "token_budget.json").write_text(
        json.dumps({"date": _today_utc(), "total_tokens": 100}),
        encoding="utf-8",
    )
    with pytest.raises(BudgetExceeded) as exc:
        check_daily_budget()
    assert exc.value.kind == "daily"


def test_task_tokens_from_state():
    assert task_tokens_from_state({"tokens_input": 3, "tokens_output": 7}) == 10
