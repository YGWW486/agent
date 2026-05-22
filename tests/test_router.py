"""P1+P3 — route_after_review 路由回归"""
import pytest

from agent.models import review_to_json, ReviewResult
from agent.models import TestCase as ReviewTestCase
from agent.orchestrator import route_after_review


def _reject_review() -> str:
    return review_to_json(
        ReviewResult(
            verdict="REJECT",
            reason="needs fix",
            test_cases=[ReviewTestCase(name="t", code="def test_t(): pass")],
        )
    )


def _pass_review() -> str:
    return review_to_json(
        ReviewResult(
            verdict="PASS",
            reason="ok",
            test_cases=[ReviewTestCase(name="t", code="def test_t(): pass")],
        )
    )


def _minimal_plan() -> str:
    import json
    return json.dumps({
        "tasks": [{
            "task_id": "t1",
            "description": "d",
            "estimated_minutes": 5,
            "file_scope": [],
            "acceptance_conditions": [{"id": "AC-1", "description": "x"}],
            "dependencies": [],
        }]
    })


@pytest.fixture
def base_state():
    return {
        "spec": "test",
        "plan": _minimal_plan(),
        "review": "",
        "status": "reviewing",
        "current_task_index": 0,
        "revision_count": 0,
        "suspended": False,
        "consecutive_coder_failures": 0,
    }


def test_route_failed_status(base_state):
    base_state["status"] = "failed"
    assert route_after_review(base_state) == "fail"


def test_route_suspended(base_state):
    base_state["suspended"] = True
    assert route_after_review(base_state) == "suspend"


def test_route_suspend_planner(base_state):
    base_state["consecutive_coder_failures"] = 2
    assert route_after_review(base_state) == "suspend_planner"


def test_route_reject_revise(base_state, monkeypatch):
    monkeypatch.setattr(
        "agent.orchestrator.get_settings",
        lambda: type("S", (), {"MAX_REVISIONS": 0})(),
    )
    base_state["review"] = _reject_review()
    base_state["revision_count"] = 1
    assert route_after_review(base_state) == "revise"


def test_route_revision_cap_suspend(base_state, monkeypatch):
    monkeypatch.setattr(
        "agent.orchestrator.get_settings",
        lambda: type("S", (), {"MAX_REVISIONS": 2})(),
    )
    base_state["review"] = _reject_review()
    base_state["revision_count"] = 2
    assert route_after_review(base_state) == "suspend"


def test_route_pass_single_task_approve(base_state, monkeypatch):
    monkeypatch.setattr(
        "agent.orchestrator.get_settings",
        lambda: type("S", (), {"MAX_REVISIONS": 0})(),
    )
    base_state["review"] = _pass_review()
    assert route_after_review(base_state) == "approve"


def test_route_pass_next_task(base_state, monkeypatch):
    monkeypatch.setattr(
        "agent.orchestrator.get_settings",
        lambda: type("S", (), {"MAX_REVISIONS": 0})(),
    )
    import json
    plan = {
        "tasks": [
            {
                "task_id": "t1",
                "description": "d1",
                "estimated_minutes": 5,
                "file_scope": [],
                "acceptance_conditions": [{"id": "AC-1", "description": "x"}],
                "dependencies": [],
            },
            {
                "task_id": "t2",
                "description": "d2",
                "estimated_minutes": 5,
                "file_scope": [],
                "acceptance_conditions": [{"id": "AC-1", "description": "y"}],
                "dependencies": [],
            },
        ]
    }
    base_state["plan"] = json.dumps(plan)
    base_state["review"] = _pass_review()
    assert route_after_review(base_state) == "next_task"


def test_route_invalid_review_fails(base_state, monkeypatch):
    monkeypatch.setattr(
        "agent.orchestrator.get_settings",
        lambda: type("S", (), {"MAX_REVISIONS": 0})(),
    )
    base_state["review"] = "not json"
    assert route_after_review(base_state) == "fail"
