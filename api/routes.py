"""API 路由 — Agent 工作流的 HTTP 接口"""

import uuid
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.orchestrator import get_workflow
from agent.llm import get_llm
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
    """精简节点输出用于 SSE 推送"""
    if node_name == "planner":
        plan = output.get("plan", "")
        try:
            from agent.models import dag_from_json
            dag = dag_from_json(plan)
            return {
                "task_count": dag.task_count,
                "status": output.get("status"),
                "_tasks": [t.model_dump() for t in dag.tasks],  # 完整任务列表
            }
        except Exception:
            return {"status": output.get("status"), "plan_len": len(plan)}
    elif node_name == "coder":
        code = output.get("code", "")
        task_idx = output.get("current_task_index", 0)
        summary = {"status": output.get("status"), "code_len": len(code), "task_index": task_idx}
        try:
            from agent.models import coder_output_from_json
            co = coder_output_from_json(code)
            summary["_diff"] = co.diff
            summary["_code"] = co.diff  # DiffViewer 需要
            summary["_self_check"] = [s.model_dump() for s in co.self_check.items]
            summary["_files"] = [f.model_dump() for f in co.files]
        except Exception:
            pass
        return summary
    elif node_name == "reviewer":
        review = output.get("review", "")
        summary = {"status": output.get("status")}
        try:
            from agent.models import review_from_json
            r = review_from_json(review)
            summary["verdict"] = r.verdict
            summary["test_count"] = len(r.test_cases)
            summary["_test_cases"] = [t.model_dump() for t in r.test_cases]
        except Exception:
            pass
        return summary
    elif node_name == "merge":
        result = {"status": output.get("status")}
        if "written_files" in output:
            result["_written_files"] = output["written_files"]
        return result
    return {}


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
            await queue.put({
                "event": "node_complete",
                "node": "merge",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {"status": "approved"},
            })
            await queue.put({"event": "workflow_complete", "thread_id": thread_id})
        elif action == "rejected":
            if result.get("suspended"):
                await queue.put({
                    "event": "interrupt",
                    "message": "工作流已暂停，等待人工审批",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
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

    workflow = get_workflow()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        timeout = get_settings().WORKFLOW_TIMEOUT
        async with asyncio.timeout(timeout):
            async for event in workflow.astream_events(initial_state, config, version="v2"):
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
                        # Keep _workflows updated with latest state from each node
                        if isinstance(output, dict):
                            _workflows[thread_id] = {**_workflows.get(thread_id, {}), **output}
                            store_save(thread_id, _workflows[thread_id])
                        payload = {
                            "event": "node_complete",
                            "node": node_name,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "summary": _summarize_node_output(node_name, output),
                        }
                        # Check for suspension
                        if output.get("suspended"):
                            payload["suspended"] = True
                            payload["failure_reason"] = output.get("failure_reason", "")
                        await event_queue.put(payload)

                if kind == "on_chain_interrupt":
                    await event_queue.put({
                        "event": "interrupt",
                        "message": "工作流已暂停，等待人工审批",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

        await event_queue.put({"event": "workflow_complete", "thread_id": thread_id})

    except asyncio.TimeoutError:
        logger.error(f"[SSE] Workflow {thread_id} timed out after {timeout}s")
        _workflows[thread_id] = {**_workflows.get(thread_id, {}), "status": "timeout", "error": "Workflow timed out"}
        await event_queue.put({
            "event": "workflow_error",
            "thread_id": thread_id,
            "error": f"Workflow timed out after {timeout}s",
        })
    except Exception as e:
        logger.error(f"[SSE] Workflow {thread_id} error: {e}")
        await event_queue.put({
            "event": "workflow_error",
            "thread_id": thread_id,
            "error": str(e),
        })
    finally:
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
    }

    # Store initial state so get_workflow_status works immediately
    _workflows[thread_id] = dict(initial_state)
    store_save(thread_id, _workflows[thread_id])

    asyncio.create_task(
        _run_workflow_with_events(thread_id, initial_state, event_queue)
    )

    logger.info(f"[API] Workflow {thread_id} started: {req.spec[:60]}...")

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
        review_summary = {"verdict": rev.verdict, "reason": rev.reason[:200]}
    except Exception:
        review_summary = None

    return {
        "thread_id": thread_id,
        "status": wf.get("status"),
        "plan_summary": plan_summary,
        "code": wf.get("code", "")[:2000],
        "review_summary": review_summary,
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
        reject_review = review_to_json(
            ReviewResult(
                verdict="REJECT",
                reason=f"人工审查拒绝: {req.comment}",
                test_cases=[],
            )
        )
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
            "coder → reviewer 审查循环（最多 3 轮）",
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
    llm = get_llm()
    return {
        "status": "ok",
        "model": llm.model,
        "token_usage": llm.token_usage(),
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
