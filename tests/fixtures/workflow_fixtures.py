"""Workflow test data builders — Pydantic fixtures for mock LLM outputs"""
from __future__ import annotations

from agent.models import (
    AcceptanceCondition,
    CoderOutput,
    FileChange,
    ReviewResult,
    SelfCheckItem,
    SelfCheckReport,
    Task,
    TaskDAG,
    TestCase,
    dag_to_json,
    review_to_json,
)


def single_task_dag(
    *,
    task_id: str = "t1",
    file_scope: list[str] | None = None,
) -> TaskDAG:
    return TaskDAG(
        tasks=[
            Task(
                task_id=task_id,
                description="Implement feature",
                estimated_minutes=5,
                file_scope=file_scope or [],
                acceptance_conditions=[
                    AcceptanceCondition(id="AC-1", description="works"),
                ],
                dependencies=[],
            )
        ]
    )


def dual_task_dag() -> TaskDAG:
    return TaskDAG(
        tasks=[
            Task(
                task_id="t1",
                description="first",
                estimated_minutes=5,
                file_scope=[],
                acceptance_conditions=[AcceptanceCondition(id="AC-1", description="a")],
            ),
            Task(
                task_id="t2",
                description="second",
                estimated_minutes=5,
                file_scope=[],
                acceptance_conditions=[AcceptanceCondition(id="AC-1", description="b")],
            ),
        ]
    )


def minimal_coder_output(
    *,
    path: str = "src/example.py",
    content: str = "def hello():\n    return 'ok'\n",
) -> CoderOutput:
    return CoderOutput(
        diff=f"add {path}",
        files=[FileChange(path=path, content=content, original_content="")],
        self_check=SelfCheckReport(
            items=[
                SelfCheckItem(
                    condition_id="AC-1",
                    status="satisfied",
                    evidence="implemented",
                )
            ],
            summary="done",
        ),
    )


def pass_review() -> ReviewResult:
    return ReviewResult(
        verdict="PASS",
        reason="ok",
        test_cases=[TestCase(name="t", code="def test_t(): pass")],
    )


def reject_review(reason: str = "needs fix") -> ReviewResult:
    return ReviewResult(
        verdict="REJECT",
        reason=reason,
        test_cases=[TestCase(name="t", code="def test_t(): pass")],
    )


def make_initial_state(**overrides) -> dict:
    dag = single_task_dag()
    state = {
        "spec": "test spec",
        "context": "test context",
        "plan": "",
        "code": "",
        "review": "",
        "revision_count": 0,
        "status": "planning",
        "error": "",
        "current_task_index": 0,
        "retry_count": 0,
        "suspended": False,
        "failure_reason": "",
        "failed_node": "",
        "consecutive_coder_failures": 0,
        "tokens_input": 0,
        "tokens_output": 0,
        "workspace_root": "",
    }
    state.update(overrides)
    if "plan" not in overrides:
        state["plan"] = dag_to_json(dag)
    return state
