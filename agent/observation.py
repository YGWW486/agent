"""统一 SSE 观测契约 — 对齐 ECC Observation（status / summary / next_actions / artifacts）"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from agent.models import coder_output_from_json, dag_from_json, review_from_json

ObsStatus = Literal["success", "warning", "error"]


class Observation(TypedDict):
    status: ObsStatus
    summary: str
    next_actions: list[str]
    artifacts: dict[str, Any]
    detail: dict[str, Any]


def build_node_detail(node_name: str, output: dict) -> dict[str, Any]:
    """节点专用 detail 载荷（供 Timeline 深度展示，保留 _diff 等字段）"""
    if node_name == "planner":
        plan = output.get("plan", "")
        try:
            dag = dag_from_json(plan)
            return {
                "task_count": dag.task_count,
                "status": output.get("status"),
                "_tasks": [t.model_dump() for t in dag.tasks],
            }
        except Exception:
            return {"status": output.get("status"), "plan_len": len(plan)}

    if node_name == "coder":
        code = output.get("code", "")
        task_idx = output.get("current_task_index", 0)
        detail: dict[str, Any] = {
            "status": output.get("status"),
            "code_len": len(code),
            "task_index": task_idx,
        }
        try:
            co = coder_output_from_json(code)
            detail["_diff"] = co.diff
            detail["_code"] = co.diff
            detail["_self_check"] = [s.model_dump() for s in co.self_check.items]
            detail["_files"] = [f.model_dump() for f in co.files]
        except Exception:
            pass
        return detail

    if node_name == "reviewer":
        review = output.get("review", "")
        detail = {"status": output.get("status")}
        try:
            r = review_from_json(review)
            detail["verdict"] = r.verdict
            detail["test_count"] = len(r.test_cases)
            detail["_test_cases"] = [t.model_dump() for t in r.test_cases]
        except Exception:
            pass
        return detail

    if node_name == "merge":
        detail = {"status": output.get("status")}
        if "written_files" in output:
            detail["_written_files"] = output["written_files"]
        return detail

    return {}


def build_observation(
    node_name: str,
    output: dict,
    *,
    thread_id: str = "",
) -> Observation:
    """根据节点输出构建统一 Observation"""
    detail = build_node_detail(node_name, output)
    artifacts: dict[str, Any] = {"thread_id": thread_id, "node": node_name}

    if output.get("suspended"):
        reason = output.get("failure_reason") or output.get("error") or "工作流已挂起"
        return Observation(
            status="error",
            summary=str(reason)[:500],
            next_actions=["resume"],
            artifacts=artifacts,
            detail=detail,
        )

    if node_name == "planner":
        tc = detail.get("task_count", "?")
        return Observation(
            status="success",
            summary=f"已拆解 {tc} 个任务",
            next_actions=[],
            artifacts=artifacts,
            detail=detail,
        )

    if node_name == "coder":
        idx = detail.get("task_index", 0)
        clen = detail.get("code_len", 0)
        paths = [f.get("path") for f in detail.get("_files", []) if isinstance(f, dict)]
        if paths:
            artifacts["paths"] = paths
        return Observation(
            status="success",
            summary=f"任务 {int(idx) + 1} 代码已生成（{clen} 字符）",
            next_actions=[],
            artifacts=artifacts,
            detail=detail,
        )

    if node_name == "reviewer":
        verdict = detail.get("verdict", "")
        if verdict == "REJECT":
            reason = ""
            try:
                r = review_from_json(output.get("review", "{}"))
                reason = (r.reason or "")[:200]
            except Exception:
                pass
            return Observation(
                status="warning",
                summary=f"审查拒绝{('：' + reason) if reason else ''}",
                next_actions=["revise"],
                artifacts=artifacts,
                detail=detail,
            )
        return Observation(
            status="success",
            summary="审查通过",
            next_actions=[],
            artifacts=artifacts,
            detail=detail,
        )

    if node_name == "merge":
        written = detail.get("_written_files") or output.get("written_files") or []
        n = len(written) if isinstance(written, list) else 0
        paths = []
        if isinstance(written, list):
            for w in written:
                if isinstance(w, dict) and w.get("path"):
                    paths.append(w["path"])
        if paths:
            artifacts["paths"] = paths
        st = output.get("status", detail.get("status", "approved"))
        return Observation(
            status="success",
            summary=f"已写入 {n} 个文件" if n else f"合并完成（{st}）",
            next_actions=[],
            artifacts=artifacts,
            detail=detail,
        )

    return Observation(
        status="success",
        summary=f"{node_name} 完成",
        next_actions=[],
        artifacts=artifacts,
        detail=detail,
    )


def observation_to_sse_payload(obs: Observation) -> dict[str, Any]:
    """Observation → SSE 顶层字段（含兼容 detail 别名 summary_legacy）"""
    return {
        "status": obs["status"],
        "summary": obs["summary"],
        "next_actions": obs["next_actions"],
        "artifacts": obs["artifacts"],
        "detail": obs["detail"],
    }


def build_interrupt_observation(message: str = "") -> dict[str, Any]:
    msg = message or "工作流已暂停，等待人工审批"
    return observation_to_sse_payload(
        Observation(
            status="warning",
            summary=msg,
            next_actions=["approve", "revise"],
            artifacts={},
            detail={"message": msg},
        )
    )


def build_workflow_error_observation(
    error: str,
    *,
    suspended: bool = False,
    failure_reason: str = "",
) -> dict[str, Any]:
    reason = failure_reason or error
    return observation_to_sse_payload(
        Observation(
            status="error",
            summary=reason[:500],
            next_actions=["resume"] if suspended else [],
            artifacts={},
            detail={"error": error, "failure_reason": failure_reason},
        )
    )


def build_tool_result_observation(
    tool: str,
    result: dict[str, Any],
    *,
    thread_id: str = "",
) -> dict[str, Any]:
    status = result.get("status", "success")
    if status not in ("success", "warning", "error"):
        status = "success"
    return observation_to_sse_payload(
        Observation(
            status=status,  # type: ignore[arg-type]
            summary=result.get("summary", ""),
            next_actions=list(result.get("next_actions") or []),
            artifacts={"thread_id": thread_id, "tool": tool},
            detail={"tool": tool, "data": result.get("data", {})},
        )
    )
