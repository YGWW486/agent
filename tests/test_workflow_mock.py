"""P3 — LangGraph workflow integration tests with mock LLM (no network)"""
from __future__ import annotations

import pytest
from langgraph.types import Command

from agent.models import review_from_json, review_to_json, human_reject_review
from tests.fixtures.fake_llm import StatefulFakeLLM
from tests.fixtures.workflow_fixtures import make_initial_state


@pytest.mark.asyncio
async def test_happy_path_interrupts_before_merge(
    patched_workflow,
    workflow_config,
    initial_state,
):
    workflow = patched_workflow(StatefulFakeLLM(reviewer_verdicts=["PASS"]))
    result = await workflow.ainvoke(initial_state, workflow_config)

    snapshot = await workflow.aget_state(workflow_config)
    assert snapshot.next, "expected interrupt before merge"
    assert any("merge" in str(n).lower() for n in snapshot.next)

    review = review_from_json(result.get("review", "{}"))
    assert review.verdict == "PASS"
    assert result.get("status") != "approved"


@pytest.mark.asyncio
async def test_hitl_resume_approved(
    patched_workflow,
    workflow_config,
    initial_state,
):
    workflow = patched_workflow(StatefulFakeLLM(reviewer_verdicts=["PASS"]))
    await workflow.ainvoke(initial_state, workflow_config)

    final = await workflow.ainvoke(
        Command(resume={"approved": True}),
        workflow_config,
    )
    assert final.get("status") == "approved"


@pytest.mark.asyncio
async def test_reject_loop_then_pass(
    patched_workflow,
    workflow_config,
    initial_state,
):
    workflow = patched_workflow(
        StatefulFakeLLM(reviewer_verdicts=["REJECT", "REJECT", "PASS"])
    )
    result = await workflow.ainvoke(initial_state, workflow_config)

    assert result.get("revision_count") == 2
    assert not result.get("suspended", False)

    snapshot = await workflow.aget_state(workflow_config)
    assert snapshot.next


@pytest.mark.asyncio
async def test_coder_suspend_after_failures(
    patched_workflow,
    workflow_config,
    initial_state,
):
    workflow = patched_workflow(
        StatefulFakeLLM(reviewer_verdicts=["PASS"], coder_raises=99)
    )
    result = await workflow.ainvoke(initial_state, workflow_config)

    assert result.get("suspended") is True
    assert result.get("failed_node") == "coder"
    assert result.get("status") == "suspended"


@pytest.mark.xfail(
    strict=False,
    reason="interrupt_before merge always continues to merge on resume; "
    "HITL reject routing needs dedicated orchestrator branch (API uses same Command)",
)
@pytest.mark.asyncio
async def test_hitl_resume_rejected_goes_back_to_coder(
    patched_workflow,
    workflow_config,
    initial_state,
):
    """Target behavior: human reject should return to coder with source=human."""
    workflow = patched_workflow(StatefulFakeLLM(reviewer_verdicts=["PASS"]))
    await workflow.ainvoke(initial_state, workflow_config)

    reject_json = review_to_json(human_reject_review("please fix"))
    result = await workflow.ainvoke(
        Command(resume={"approved": False, "review": reject_json}),
        workflow_config,
    )

    review = review_from_json(result.get("review", "{}"))
    assert review.source == "human"
    assert review.verdict == "REJECT"
    assert result.get("status") == "reviewing"
