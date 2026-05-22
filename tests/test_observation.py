"""Observation 契约单元测试"""

from agent.observation import (
    build_interrupt_observation,
    build_node_detail,
    build_observation,
    build_workflow_error_observation,
)
from tests.fixtures.workflow_fixtures import (
    minimal_coder_output,
    pass_review,
    reject_review,
    single_task_dag,
)
from agent.models import coder_output_to_json, dag_to_json, review_to_json


def test_planner_observation():
    dag = single_task_dag()
    out = {"plan": dag_to_json(dag), "status": "coding"}
    obs = build_observation("planner", out, thread_id="t1")
    assert obs["status"] == "success"
    assert "1" in obs["summary"]
    assert obs["next_actions"] == []
    assert obs["detail"]["task_count"] == 1


def test_coder_observation():
    co = minimal_coder_output()
    out = {
        "code": coder_output_to_json(co),
        "current_task_index": 0,
        "status": "reviewing",
    }
    obs = build_observation("coder", out, thread_id="t2")
    assert obs["status"] == "success"
    assert "代码已生成" in obs["summary"]
    assert "paths" in obs["artifacts"]


def test_reviewer_reject_next_actions():
    out = {"review": review_to_json(reject_review()), "status": "coding"}
    obs = build_observation("reviewer", out)
    assert obs["status"] == "warning"
    assert obs["next_actions"] == ["revise"]


def test_reviewer_pass():
    out = {"review": review_to_json(pass_review()), "status": "reviewing"}
    obs = build_observation("reviewer", out)
    assert obs["status"] == "success"
    assert obs["next_actions"] == []


def test_suspended_resume_action():
    out = {
        "suspended": True,
        "failure_reason": "Token 超限",
        "status": "suspended",
    }
    obs = build_observation("coder", out, thread_id="t3")
    assert obs["status"] == "error"
    assert obs["next_actions"] == ["resume"]


def test_interrupt_observation():
    payload = build_interrupt_observation()
    assert payload["next_actions"] == ["approve", "revise"]
    assert payload["status"] == "warning"


def test_workflow_error_suspended():
    payload = build_workflow_error_observation("err", suspended=True)
    assert payload["next_actions"] == ["resume"]


def test_build_node_detail_has_diff():
    co = minimal_coder_output()
    detail = build_node_detail("coder", {"code": coder_output_to_json(co)})
    assert "_diff" in detail
