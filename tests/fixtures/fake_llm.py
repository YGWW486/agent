"""Stateful fake LLM for workflow integration tests — no network calls"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from agent.models import CoderOutput, ReviewResult, TaskDAG

from tests.fixtures.workflow_fixtures import (
    minimal_coder_output,
    pass_review,
    reject_review,
    single_task_dag,
)


class _FakeToolBlock:
    def __init__(self, id: str, name: str, input: dict):
        self.type = "tool_use"
        self.id = id
        self.name = name
        self.input = input


class StatefulFakeLLM:
    """Returns fixed structured outputs; reviewer verdicts consumed in order."""

    def __init__(
        self,
        *,
        dag: TaskDAG | None = None,
        coder_out: CoderOutput | None = None,
        reviewer_verdicts: list[str] | None = None,
        coder_raises: int = 0,
        tool_rounds: list[list[dict]] | None = None,
    ):
        self._dag = dag or single_task_dag()
        self._coder_out = coder_out or minimal_coder_output()
        self._reviewer_verdicts = list(reviewer_verdicts or ["PASS"])
        self._reviewer_index = 0
        self._coder_raises = coder_raises
        self._coder_calls = 0
        self._tool_round_index = 0
        self._tool_rounds = tool_rounds or []
        self._usage = {"input": 10, "output": 5, "cache_read": 0, "reasoning": 0}

    def _next_review(self) -> ReviewResult:
        if self._reviewer_index >= len(self._reviewer_verdicts):
            verdict = self._reviewer_verdicts[-1]
        else:
            verdict = self._reviewer_verdicts[self._reviewer_index]
        self._reviewer_index += 1
        if verdict == "REJECT":
            return reject_review()
        return pass_review()

    async def chat_with_structured_output(
        self,
        *,
        output_model,
        **kwargs,
    ):
        if output_model is TaskDAG:
            return self._dag
        if output_model is CoderOutput:
            if self._coder_calls < self._coder_raises:
                self._coder_calls += 1
                raise RuntimeError("coder fail")
            self._coder_calls += 1
            return self._coder_out
        if output_model is ReviewResult:
            return self._next_review()
        raise TypeError(f"Unexpected output_model: {output_model}")

    async def chat_with_tools(self, system: str, messages: list, tools: list, **kwargs) -> Any:
        """Return Anthropic-shaped Message with tool_use blocks or empty tools."""
        if self._tool_round_index < len(self._tool_rounds):
            round_tools = self._tool_rounds[self._tool_round_index]
            self._tool_round_index += 1
            blocks = [
                _FakeToolBlock(
                    id=f"toolu_fake_{self._tool_round_index}_{i}",
                    name=t["name"],
                    input=t.get("input", {}),
                )
                for i, t in enumerate(round_tools)
            ]
            return SimpleNamespace(content=blocks)

        return SimpleNamespace(content=[])

    def reset_usage(self) -> None:
        self._usage = {"input": 10, "output": 5, "cache_read": 0, "reasoning": 0}

    def token_usage(self) -> dict:
        return dict(self._usage)
