"""API 路由 — Agent 工作流的 HTTP 接口"""

import uuid
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.orchestrator import get_workflow
from agent.llm import get_llm
from agent.budget import (
    BudgetExceeded,
    check_daily_budget,
    check_task_budget,
    record_node_usage,
    add_task_tokens_to_daily,
)
from agent.models import (
    review_to_json,
    review_from_json,
    dag_from_json,
    coder_output_from_json,
    human_reject_review,
)
from agent.observation import (
    build_interrupt_observation,
    build_node_detail,
    build_observation,
    build_workflow_error_observation,
    observation_to_sse_payload,
)
from agent.models import review_to_json, review_from_json, dag_from_json, coder_output_from_json, ReviewResult
from config.settings import get_settings
from api.index_routes import router as index_router
import asyncio
import json
from datetime import datetime, timezone
from sse_starlette.sse import EventSourceResponse
from langgraph.types import Command

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["agent"])

# ── 请求模型 ──────────────────────────────────────────

class WorkflowRequest(BaseModel):
    spec: str
    context: str = ""
    workspace_path: str = ""  # 可选，覆盖 WORKSPACE_ROOT / 进程 CWD

class ApproveRequest(BaseModel):
    approved: bool = True
    comment: str = ""

# ── 运行时存储 + 持久化 ────────────────────────────────

from bridge.store import save as store_save, load_all as store_load_all

_workflows: dict[str, Any] = store_load_all()  # 启动时从磁盘恢复
_event_queues: dict[str, asyncio.Queue] = {}

logger.info(f"[Store] Loaded {len(_workflows)} workflow(s) from disk")


# ── SSE 辅助 ────────────────────────────────────────────

def _summarize_node_output(node_name: str, output: dict) -> dict:
    """兼容别名：返回 detail 字典（旧前端读 event.summary 作 detail）"""
    return build_node_detail(node_name, output)


def _node_complete_payload(
    node_name: str,
    output: dict,
    *,
    thread_id: str,
) -> dict:
    """node_complete SSE 载荷 — 顶层 Observation + detail"""
    obs = build_observation(node_name, output, thread_id=thread_id)
    payload = {
        "event": "node_complete",
        "node": node_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **observation_to_sse_payload(obs),
    }
    if output.get("suspended"):
        payload["suspended"] = True
        payload["failure_reason"] = output.get("failure_reason", "")
    return payload


def _push_resume_events(thread_id: str, result: dict, action: str) -> None:
    """Push SSE events for workflow resumed after HITL approval/rejection."""
    queue = _event_queues.get(thread_id)
    if queue is None:
        queue = asyncio.Queue()
        _event_queues[thread_id] = queue

    async def _push():
        status = result.get("status", "")
        if action == "approved" and status == "approved":
            await queue.put({
                "event": "node_start",
                "node": "merge",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            merge_out = {"status": "approved", "written_files": result.get("written_files", [])}
            await queue.put(_node_complete_payload("merge", merge_out, thread_id=thread_id))
            await queue.put({"event": "workflow_complete", "thread_id": thread_id})
        elif action == "rejected":
            if result.get("suspended"):
                await queue.put({
                    "event": "interrupt",
                    "message": "工作流已暂停，等待人工审批",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **build_interrupt_observation(),
                })
            elif status == "approved":
                await queue.put({"event": "workflow_complete", "thread_id": thread_id})
        await queue.put({"event": "stream_end"})

    asyncio.ensure_future(_push())


async def _run_workflow_with_events(
    thread_id: str,
    initial_state: dict,
    event_queue: asyncio.Queue,
):
    """后台任务：运行工作流，通过 astream_events 推送 SSE 事件"""
    from agent.orchestrator import get_workflow
    from agent.runtime_events import reset_event_queue, set_event_queue

    workflow = get_workflow()
    config = {"configurable": {"thread_id": thread_id}}
    llm = get_llm()
    llm.reset_usage()
    budget_exceeded = False
    queue_token = set_event_queue(event_queue)

    try:
        timeout = get_settings().WORKFLOW_TIMEOUT
        async with asyncio.timeout(timeout):
            async for event in workflow.astream_events(initial_state, config, version="v2"):
                if budget_exceeded:
                    break

                kind = event.get("event", "")
                node_name = event.get("name", "")

                if node_name in ("planner", "coder", "reviewer", "merge"):
                    if kind == "on_chain_start":
                        await event_queue.put({
                            "event": "node_start",
                            "node": node_name,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    elif kind == "on_chain_end":
                        output = event.get("data", {}).get("output", {})
                        prev_wf = dict(_workflows.get(thread_id, {}))
                        if isinstance(output, dict):
                            token_patch = record_node_usage(
                                {**prev_wf, **output}, llm
                            )
                            merged = {**prev_wf, **output, **token_patch}
                            add_task_tokens_to_daily(merged, prev_wf)
                            try:
                                check_task_budget(merged)
                            except BudgetExceeded as be:
                                merged.update({
                                    "suspended": True,
                                    "status": "suspended",
                                    "failure_reason": str(be),
                                    "failed_node": node_name,
                                })
                                _workflows[thread_id] = merged
                                store_save(thread_id, merged)
                                await event_queue.put({
                                    "event": "workflow_error",
                                    "thread_id": thread_id,
                                    "error": str(be),
                                    "suspended": True,
                                    "failure_reason": str(be),
                                    **build_workflow_error_observation(
                                        str(be), suspended=True, failure_reason=str(be)
                                    ),
                                })
                                budget_exceeded = True
                                break
                            _workflows[thread_id] = merged
                            store_save(thread_id, merged)
                            output = merged
                        await event_queue.put(
                            _node_complete_payload(node_name, output, thread_id=thread_id)
                        )

                if kind == "on_chain_interrupt":
                    await event_queue.put({
                        "event": "interrupt",
                        "message": "工作流已暂停，等待人工审批",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        **build_interrupt_observation(),
                    })

        if not budget_exceeded:
            await event_queue.put({"event": "workflow_complete", "thread_id": thread_id})

    except asyncio.TimeoutError:
        logger.error(f"[SSE] Workflow {thread_id} timed out after {timeout}s")
        _workflows[thread_id] = {**_workflows.get(thread_id, {}), "status": "timeout", "error": "Workflow timed out"}
        await event_queue.put({
            "event": "workflow_error",
            "thread_id": thread_id,
            "error": f"Workflow timed out after {timeout}s",
            **build_workflow_error_observation(f"Workflow timed out after {timeout}s"),
        })
    except Exception as e:
        logger.error(f"[SSE] Workflow {thread_id} error: {e}")
        await event_queue.put({
            "event": "workflow_error",
            "thread_id": thread_id,
            "error": str(e),
            **build_workflow_error_observation(str(e)),
        })
    finally:
        reset_event_queue(queue_token)
        await event_queue.put({"event": "stream_end"})


# ── 端点 ───────────────────────────────────────────────

@router.get("/workflows")
async def list_workflows():
    """列出所有已持久化的工作流（含历史）"""
    from bridge.store import load_all as store_load

    saved = store_load()
    # 合并内存中的运行时状态（可能有更新的数据）
    result = []
    seen = set()
    for tid, wf in {**saved, **_workflows}.items():
        if tid in seen:
            continue
        seen.add(tid)
        result.append({
            "thread_id": tid,
            "spec": str(wf.get("spec", ""))[:200],
            "status": wf.get("status", "unknown"),
            "suspended": wf.get("suspended", False),
            "error": wf.get("error", ""),
        })
    return sorted(result, key=lambda x: x["thread_id"], reverse=True)


@router.post("/workflow")
async def start_workflow(req: WorkflowRequest):
    """提交 spec，启动后台工作流"""
    try:
        check_daily_budget()
    except BudgetExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))

    thread_id = str(uuid.uuid4())[:8]
    event_queue = asyncio.Queue()
    _event_queues[thread_id] = event_queue

    initial_state = {
        "spec": req.spec,
        "context": req.context,
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
        "workspace_root": req.workspace_path.strip(),
        "test_results": "",
    }

    # Store initial state so get_workflow_status works immediately
    _workflows[thread_id] = dict(initial_state)
    store_save(thread_id, _workflows[thread_id])

    from bridge.request_queue import request_queue

    job = {
        "thread_id": thread_id,
        "initial_state": initial_state,
        "event_queue": event_queue,
    }
    enqueued = await request_queue.put(job, timeout=2.0)
    if not enqueued:
        _event_queues.pop(thread_id, None)
        _workflows.pop(thread_id, None)
        from bridge.store import remove as store_remove
        store_remove(thread_id)
        raise HTTPException(
            status_code=503,
            detail="工作流队列已满，请稍后重试",
        )

    logger.info(f"[API] Workflow {thread_id} enqueued: {req.spec[:60]}...")

    return {
        "thread_id": thread_id,
        "status": "started",
        "stream_url": f"/api/workflow/{thread_id}/stream",
    }


@router.get("/workflow/{thread_id}")
async def get_workflow_status(thread_id: str):
    """查询工作流当前状态"""
    wf = _workflows.get(thread_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Try to parse structured outputs for display
    plan_summary = None
    try:
        from agent.models import dag_from_json
        dag = dag_from_json(wf.get("plan", ""))
        plan_summary = {
            "task_count": dag.task_count,
            "current_task": dag.current_task(wf.get("current_task_index", 0)),
        }
        if plan_summary["current_task"]:
            plan_summary["current_task"] = plan_summary["current_task"].task_id
    except Exception:
        plan_summary = None

    review_summary = None
    try:
        from agent.models import review_from_json
        rev = review_from_json(wf.get("review", ""))
        review_summary = {
            "verdict": rev.verdict,
            "reason": rev.reason[:200],
            "test_count": len(rev.test_cases),
            "test_cases": [t.model_dump() for t in rev.test_cases],
        }
    except Exception:
        review_summary = None

    self_check = None
    try:
        from agent.models import coder_output_from_json
        co = coder_output_from_json(wf.get("code", ""))
        self_check = [s.model_dump() for s in co.self_check.items]
    except Exception:
        self_check = None

    test_results = None
    tr = wf.get("test_results", "")
    if tr:
        import json as _json
        try:
            test_results = _json.loads(tr) if isinstance(tr, str) else tr
        except Exception:
            pass

    return {
        "thread_id": thread_id,
        "status": wf.get("status"),
        "plan_summary": plan_summary,
        "code": wf.get("code", "")[:2000],
        "review_summary": review_summary,
        "self_check": self_check,
        "test_results": test_results,
        "revision_count": wf.get("revision_count"),
        "current_task_index": wf.get("current_task_index"),
        "suspended": wf.get("suspended", False),
        "failure_reason": wf.get("failure_reason", ""),
        "error": wf.get("error", ""),
    }


@router.post("/workflow/{thread_id}/approve")
async def approve_workflow(thread_id: str, req: ApproveRequest):
    """人工审批 — 通过后执行 merge；拒绝则打回 coder"""
    wf = _workflows.get(thread_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = get_workflow()
    config = {"configurable": {"thread_id": thread_id}}

    if req.approved:
        logger.info(f"[API] Workflow {thread_id} APPROVED — merging")
        result = await workflow.ainvoke(Command(resume={"approved": True}), config)
        _workflows[thread_id] = {**wf, **result}
        store_save(thread_id, _workflows[thread_id])
        # Push SSE events for the resumed merge so the client sees progress
        _push_resume_events(thread_id, result, "approved")
        return {
            "thread_id": thread_id,
            "status": result.get("status"),
            "code": result.get("code", ""),
            "message": "Workflow completed",
        }
    else:
        logger.info(f"[API] Workflow {thread_id} REJECTED: {req.comment}")
        # Build a valid ReviewResult JSON so coder can parse it
        reject_review = review_to_json(human_reject_review(req.comment))
        result = await workflow.ainvoke(
            Command(resume={"approved": False, "review": reject_review}),
            config,
        )
        _workflows[thread_id] = {**wf, **result}
        store_save(thread_id, _workflows[thread_id])
        _push_resume_events(thread_id, result, "rejected")
        return {
            "thread_id": thread_id,
            "status": result.get("status"),
            "message": "Sent back to coder for revision",
        }


class ResumeRequest(BaseModel):
    target_node: str = "coder"  # 从哪个节点恢复


@router.get("/workflow/{thread_id}/stream")
async def stream_workflow(thread_id: str):
    """SSE 端点：推送节点级别的实时状态更新"""
    queue = _event_queues.get(thread_id)
    if not queue:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found or already completed",
        )

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                yield {
                    "event": event.get("event", "message"),
                    "data": json.dumps(event, default=str, ensure_ascii=False),
                }
                queue.task_done()
                if event.get("event") in ("stream_end", "workflow_complete", "workflow_error"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": "{}"}

        _event_queues.pop(thread_id, None)

    return EventSourceResponse(event_generator())


@router.post("/workflow/{thread_id}/resume")
async def resume_workflow(thread_id: str, req: ResumeRequest):
    """恢复挂起的工作流"""
    from agent.orchestrator import get_workflow

    workflow = get_workflow()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = await workflow.ainvoke(
            Command(resume={"target_node": req.target_node}),
            config,
        )
        _workflows[thread_id] = {**_workflows.get(thread_id, {}), **result}
        store_save(thread_id, _workflows[thread_id])
        return {
            "thread_id": thread_id,
            "status": result.get("status"),
            "message": "Workflow resumed",
        }
    except Exception as e:
        logger.error(f"[API] Resume {thread_id} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills")
async def list_capabilities():
    """列出 Agent 系统的能力（从 SkillDispatcher 读取）"""
    from agent.skill_dispatcher import get_dispatcher

    settings = get_settings()
    dispatcher = get_dispatcher()
    registered = dispatcher.list_skills()
    dispatch_stats = dispatcher.get_stats()

    return {
        "workflow": "planner → coder → reviewer → merge",
        "hitl": "merge 前需要人工审批",
        "models": settings.MODEL_ROUTING,
        "max_revisions": settings.MAX_REVISIONS,
        "features": [
            "spec → plan 自动拆解",
            "coder → reviewer 审查循环（MAX_REVISIONS=0 不限，>0 超限挂起）",
            "merge 前人工审批（HITL）",
            "LangSmith 全链路追踪",
            "token 用量追踪",
        ],
        "registered_skills": registered,
        "dispatch_stats": dispatch_stats,
    }


@router.get("/health")
async def health():
    """健康检查"""
    from agent.llm import get_llm_info
    info = get_llm_info()
    return {
        "status": "ok",
        "model": info["model"],
        "token_usage": info["token_usage"],
    }


@router.delete("/workflow/{thread_id}")
async def delete_workflow(thread_id: str):
    """删除工作流及其持久化数据"""
    from bridge.store import remove as store_remove

    _workflows.pop(thread_id, None)
    _event_queues.pop(thread_id, None)
    store_remove(thread_id)

    return {"thread_id": thread_id, "deleted": True}


@router.post("/workflow/{thread_id}/restore")
async def restore_workflow_files(thread_id: str):
    """恢复最近一次 merge 写入的所有文件到修改前状态"""
    from agent.orchestrator import restore_files

    wf = _workflows.get(thread_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    result = restore_files(thread_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return {
        "thread_id": thread_id,
        "restored": result["restored"],
        "backup_dir": result["backup_dir"],
    }


# 注册 index 路由
router.include_router(index_router)
