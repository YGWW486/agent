"""LangGraph Agent 编排器 — Planner → Coder → Reviewer 三节点流水线（Phase 1 加固版）"""

import logging
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.context import get_graph_index
from agent.llm import get_llm
from agent.retry import retry_async, RetryConfig, CircuitBreaker
from agent.models import (
    TaskDAG, CoderOutput, ReviewResult,
    dag_to_json, dag_from_json,
    coder_output_to_json, coder_output_from_json,
    review_to_json, review_from_json,
)
from config.settings import get_settings

logger = logging.getLogger(__name__)

# Global circuit breaker for LLM calls — prevents cascading failures
_llm_circuit = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=Exception,
)

# ── State ──────────────────────────────────────────────

class AgentState(TypedDict):
    # ── existing fields ──
    spec: str
    context: str
    plan: str                # Now: TaskDAG serialized as JSON string
    code: str                # Now: CoderOutput serialized as JSON string
    review: str              # Now: ReviewResult serialized as JSON string
    revision_count: int
    status: str
    error: str

    # ── new: task iteration ──
    current_task_index: int

    # ── new: failure tracking ──
    retry_count: int
    suspended: bool
    failure_reason: str
    failed_node: str
    consecutive_coder_failures: int

# ── Prompts ────────────────────────────────────────────

PLANNER_SYSTEM = """你是一个资深系统架构师。你的唯一输出方式是调用 `output_plan` 工具。

你需要将需求规格拆解为结构化的任务 DAG（有向无环图）。调用 output_plan 工具时，必须遵循以下约束：

1. 每个任务的预估工作量 ≤ 15 分钟
2. 每个任务有 2-5 条明确的、可验证的验收条件
3. 同一 DAG 层级的任务操作的文件集不能重叠（避免编辑冲突）
4. 任务之间的依赖关系必须显式声明（dependencies 字段）

Task 的 acceptance_conditions 数组中，每个元素包含 id（如 "AC-1"）和 description。

只输出工具调用，不要输出任何其他文字。"""


CODER_SYSTEM = """你是一个资深软件工程师。你的唯一输出方式是调用 `output_code` 工具。

你会收到一个任务定义（描述、文件范围、验收条件）和项目上下文。

你必须：
1. 生成完整、可运行的代码变更，并通过 `files` 字段列出所有变更文件：
   - `path`：文件路径（相对于项目根目录，如 "src/auth.py"）
   - `content`：文件的完整新内容（不是 diff，是完整文件）
   - `original_content`：如果是修改已有文件，填写修改前的内容；新建文件填空字符串
2. 在 `diff` 字段中给出可读的变更摘要
3. 对每一条验收条件进行自检，声明为下列状态之一：
   - "satisfied"：代码明确满足该条件
   - "not_satisfied"：代码未满足该条件
   - "uncertain"：不运行代码无法确定
4. 每项自检提供具体的证据（引用行号、逻辑路径、测试用例等）

如果收到了审查反馈（revision），先解决所有反馈问题再输出。

只输出 output_code 工具调用，不要输出任何其他文字。"""


REVIEWER_SYSTEM = """你是一个严格的代码审查者。你的唯一输出方式是调用 `output_review` 工具。

你会收到：
- 原始验收条件
- Coder 的代码变更（diff）
- Coder 的自检报告

你必须：
1. 对照实际代码，逐条核实 Coder 的自检声明
2. 得出审查结论：verdict = "PASS" 或 "REJECT"
3. 如果 PASS：确认所有验收条件已满足
4. 如果 REJECT：给出具体的、可操作的修改意见，引用代码位置
5. 无论 PASS 还是 REJECT，都必须附带至少一个可运行的测试用例（pytest 函数或 shell 脚本），用于验证关键路径

只输出 output_review 工具调用，不要输出任何其他文字。"""

# ── Node Functions ─────────────────────────────────────

async def planner_node(state: AgentState) -> dict:
    """将 spec 拆解为结构化 TaskDAG"""
    logger.info("[Planner] Decomposing spec into TaskDAG...")
    settings = get_settings()
    llm = get_llm()

    user_prompt = f"""## 需求规格
{state['spec']}

## 项目上下文
{_build_context(state)}"""

    retry_cfg = RetryConfig(
        max_retries=settings.PLANNER_RETRY_MAX,
        initial_delay=settings.PLANNER_RETRY_DELAY,
        max_delay=3.0,
    )

    async def _do_plan():
        return await llm.chat_with_structured_output(
            system=PLANNER_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
            output_model=TaskDAG,
            tool_name="output_plan",
            tool_description="输出实现计划的任务 DAG（有向无环图）",
        )

    try:
        dag: TaskDAG = await _llm_circuit.call(
            lambda: retry_async(_do_plan, retry_cfg),
        )
        logger.info(f"[Planner] TaskDAG: {dag.task_count} tasks")
        return {
            "plan": dag_to_json(dag),
            "status": "coding",
            "current_task_index": 0,
            "revision_count": 0,
            "retry_count": 0,
            "suspended": False,
            "consecutive_coder_failures": 0,
        }
    except Exception as e:
        logger.error(f"[Planner] Failed: {e}")
        return {
            "error": str(e),
            "status": "failed",
            "suspended": False,
            "failure_reason": f"Planner 失败: {e}",
        }


async def coder_node(state: AgentState) -> dict:
    """根据当前任务生成/修改代码，支持 next_task 和 revise 两种模式"""
    settings = get_settings()

    # 解析结构和当前进度
    dag = dag_from_json(state.get("plan", "{}"))
    review_raw = state.get("review", "")

    # 判断是否从上一任务 PASS 而来（next_task 模式）
    is_next_task = False
    try:
        prev_review = review_from_json(review_raw)
        is_next_task = (prev_review.verdict == "PASS")
    except Exception:
        prev_review = None

    # 确定任务索引
    task_idx = state.get("current_task_index", 0)
    if is_next_task:
        task_idx += 1

    if dag.is_complete(task_idx):
        logger.info(f"[Coder] All {dag.task_count} tasks done")
        return {"status": "reviewing", "current_task_index": task_idx}

    current_task = dag.current_task(task_idx)
    logger.info(f"[Coder] Task {task_idx + 1}/{dag.task_count}: {current_task.task_id} "
                f"(revision {state.get('revision_count', 0)})")

    llm = get_llm()

    # 构建上下文
    task_context = f"""## 当前任务
- ID: {current_task.task_id}
- 描述: {current_task.description}
- 文件范围: {', '.join(current_task.file_scope) if current_task.file_scope else '不限'}
- 预估时间: {current_task.estimated_minutes} min

## 验收条件
"""
    for ac in current_task.acceptance_conditions:
        task_context += f"- {ac.id}: {ac.description}\n"

    # 项目级别的文件摘要
    project_overview = _build_context(state)

    if is_next_task:
        user_prompt = f"""## 项目上下文
{project_overview}

{task_context}

请生成完整代码。"""
    elif prev_review is not None and prev_review.verdict == "REJECT":
        user_prompt = f"""## 审查反馈（请修改代码以解决以下问题）
{review_raw}

{task_context}

## 项目上下文
{project_overview}

## 之前的代码
{state.get('code', '')}"""
    else:
        user_prompt = f"""## 项目上下文
{project_overview}

{task_context}

请生成完整代码。"""

    retry_cfg = RetryConfig(
        max_retries=settings.CODER_RETRY_MAX,
        initial_delay=settings.CODER_RETRY_DELAY,
        max_delay=3.0,
    )

    async def _do_code():
        return await llm.chat_with_structured_output(
            system=CODER_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
            output_model=CoderOutput,
            tool_name="output_code",
            tool_description="输出代码变更和自检报告",
        )

    try:
        coder_out: CoderOutput = await _llm_circuit.call(
            lambda: retry_async(_do_code, retry_cfg),
        )
        logger.info(f"[Coder] Output: {len(coder_out.diff)} chars, "
                    f"self_check: {len(coder_out.self_check.items)} items")
        return {
            "code": coder_output_to_json(coder_out),
            "status": "reviewing",
            "current_task_index": task_idx,
            "retry_count": 0,
            "consecutive_coder_failures": 0,
        }
    except Exception as e:
        logger.error(f"[Coder] Failed: {e}")
        consecutive = state.get("consecutive_coder_failures", 0) + 1
        return {
            "error": str(e),
            "status": "suspended",
            "suspended": True,
            "failed_node": "coder",
            "failure_reason": f"Coder 失败（{settings.CODER_RETRY_MAX + 1} 次尝试后）: {e}",
            "consecutive_coder_failures": consecutive,
        }


async def reviewer_node(state: AgentState) -> dict:
    """审查 Coder 产出，输出结构化 ReviewResult"""
    logger.info("[Reviewer] Reviewing code...")
    llm = get_llm(model=get_settings().MODEL_ROUTING["complex"])

    coder_code = state.get("code", "")
    try:
        coder_out = coder_output_from_json(coder_code)
        self_check_summary = coder_out.self_check.model_dump_json(indent=2)
    except Exception:
        self_check_summary = "无法解析"

    # 获取当前任务验收条件
    try:
        dag = dag_from_json(state.get("plan", "{}"))
        task = dag.current_task(state.get("current_task_index", 0))
        ac_text = "\n".join(f"- {ac.id}: {ac.description}" for ac in task.acceptance_conditions) if task else "无"
    except Exception:
        ac_text = "无法解析"

    user_prompt = f"""## 验收条件
{ac_text}

## Coder 自检报告
{self_check_summary}

## 代码
{coder_code if len(coder_code) <= 8000 else coder_code[:8000] + '...'}

## 需求规格
{state['spec'][:2000]}"""

    try:
        result_raw = await llm.chat_with_structured_output(
            system=REVIEWER_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
            output_model=ReviewResult,
            tool_name="output_review",
            tool_description="输出代码审查结论（PASS/REJECT）和测试用例",
        )
        result: ReviewResult = result_raw
        new_count = state.get("revision_count", 0) + 1
        logger.info(f"[Reviewer] Verdict: {result.verdict} (revision {new_count})")
        return {
            "review": review_to_json(result),
            "revision_count": new_count,
        }
    except Exception as e:
        logger.error(f"[Reviewer] Failed: {e}")
        return {"error": str(e), "status": "failed"}


def merge_node(state: AgentState) -> dict:
    """合并通过审查的代码 — 原子写盘 + Git 优先恢复"""
    import os
    import subprocess
    from datetime import datetime, timezone

    logger.info("[Merge] Writing files to disk...")

    code_raw = state.get("code", "")
    written_files: list[dict] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(".aec-backup", timestamp)

    try:
        coder_out = coder_output_from_json(code_raw)
    except Exception:
        logger.warning("[Merge] Cannot parse coder output, skipping file write")
        return {"status": "approved", "suspended": False, "written_files": []}

    for fc in coder_out.files:
        filepath = fc.path
        dirpath = os.path.dirname(filepath)

        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

        # 备份：优先用 git show（能拿到提交后的版本），回退到文件复制
        backup_path = os.path.join(backup_dir, os.path.basename(filepath))
        os.makedirs(backup_dir, exist_ok=True)
        backed_up = False

        if os.path.exists(filepath):
            # 尝试从 git 取原始内容（最可靠的恢复源）
            try:
                result = subprocess.run(
                    ["git", "show", f"HEAD:{fc.path}"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    os.makedirs(os.path.dirname(backup_path) if os.path.dirname(backup_path) else backup_dir, exist_ok=True)
                    with open(backup_path, "w", encoding="utf-8") as bf:
                        bf.write(result.stdout)
                    backed_up = True
                    logger.info(f"[Merge] Git backup: {filepath}")
            except Exception:
                pass

            # 回退：文件级备份
            if not backed_up:
                import shutil
                shutil.copy2(filepath, backup_path)
                backed_up = True
                logger.info(f"[Merge] File backup: {filepath} → {backup_path}")

        # 原子写入：先写临时文件，再 rename
        tmp_path = filepath + f".aec-tmp-{timestamp}"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(fc.content)
            os.replace(tmp_path, filepath)  # 原子操作，Windows/Linux 都支持
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

        written_files.append({
            "path": filepath,
            "backup": backup_path if backed_up else None,
            "size": len(fc.content),
        })
        logger.info(f"[Merge] Written: {filepath} ({len(fc.content)} chars)" + (" [atomic]" if backed_up else " [new]"))

    return {
        "status": "approved",
        "suspended": False,
        "written_files": written_files,
        "backup_dir": backup_dir,
    }


def restore_files(thread_id: str) -> dict:
    """恢复最近一次 merge 写入的文件 — 优先 git checkout，回退到文件备份"""
    import os
    import shutil
    import glob
    import subprocess

    backups = sorted(glob.glob(".aec-backup/*"), reverse=True)
    if not backups:
        return {"success": False, "error": "没有找到备份"}

    latest = backups[0]
    restored = []
    git_used = False

    for filename in os.listdir(latest):
        backup_path = os.path.join(latest, filename)

        # 优先用 git 恢复（如果文件在 git 跟踪范围内）
        try:
            result = subprocess.run(
                ["git", "checkout", "--", filename],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                restored.append(filename)
                git_used = True
                logger.info(f"[Restore] Git checkout: {filename}")
                continue
        except Exception:
            pass

        # 回退：文件级恢复
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, filename)
            restored.append(filename)
            logger.info(f"[Restore] File copy: {backup_path} → {filename}")

    return {
        "success": True,
        "restored": restored,
        "backup_dir": latest,
        "method": "git checkout" if git_used else "file backup",
    }


# ── Router ─────────────────────────────────────────────

def route_after_review(state: AgentState) -> str:
    """根据审查结果决定下一步：next_task / revise / approve / suspend / fail"""
    status = state.get("status", "")
    review_raw = state.get("review", "")
    task_idx = state.get("current_task_index", 0)

    if status == "failed":
        return "fail"

    if state.get("suspended", False):
        return "suspend"

    if state.get("consecutive_coder_failures", 0) >= 2:
        logger.warning("[Router] Planner 不合理 → suspend_planner")
        return "suspend_planner"

    # 解析结构化 ReviewResult
    try:
        review = review_from_json(review_raw)
    except Exception:
        logger.error("[Router] 无法解析 ReviewResult → fail")
        return "fail"

    if review.verdict == "PASS":
        try:
            dag = dag_from_json(state.get("plan", "{}"))
        except Exception:
            return "approve"

        next_idx = task_idx + 1
        if dag.is_complete(next_idx):
            logger.info(f"[Router] 全部 {dag.task_count} 个任务 PASS → merge")
            return "approve"
        else:
            logger.info(f"[Router] Task {task_idx} PASS → next task {next_idx + 1}/{dag.task_count}")
            return "next_task"

    logger.info(f"[Router] REJECT → revise (revision {state.get('revision_count', 0)})")
    return "revise"


# ── Context Helper ────────────────────────────────────

def _build_context(state: dict) -> str:
    """从 GraphIndex 获取项目上下文摘要。

    Planner 阶段获取全仓概览（所有文件的 node 摘要列表）。
    若索引未加载，回退到 state 中传入的 context 字符串。
    """
    index = get_graph_index()
    if not index.is_loaded():
        return state.get("context", "无额外上下文")

    stats = index.stats()
    if stats["files_indexed"] == 0:
        return "已加载索引但未找到文件上下文"

    result = index.query(files=[], depth=0)
    if result.get("status") == "no_index":
        return "索引不可用"

    summaries = result.get("file_summaries", {})
    if not summaries:
        return "已加载索引但未找到文件摘要"

    lines = [f"项目共 {stats['files_indexed']} 个文件，{stats['node_count']} 个符号节点："]
    for filepath, summary in sorted(summaries.items()):
        lines.append(f"  - {filepath}: {summary}")
    return "\n".join(lines)


# ── Graph Builder ──────────────────────────────────────

def build_workflow() -> StateGraph:
    """构建并编译 LangGraph 工作流

    图结构:
        START → planner → coder → reviewer → [router] → merge → END
                                      ↑_________________|
                                      (REJECT / next_task)
    """
    workflow = StateGraph(AgentState)

    # 注册节点
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("merge", merge_node)

    # 主流程边
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "coder")
    workflow.add_edge("coder", "reviewer")

    # 审查后的条件路由
    workflow.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "approve": "merge",
            "next_task": "coder",
            "revise": "coder",
            "fail": END,
            "suspend": END,
            "suspend_planner": END,
        },
    )

    workflow.add_edge("merge", END)

    # 编译（带 checkpoint 持久化，支持 HITL）
    memory = MemorySaver()
    compiled = workflow.compile(
        checkpointer=memory,
        interrupt_before=["merge"],  # 合并前暂停 → 人工审批
    )
    logger.info("Workflow compiled successfully")
    return compiled


# 全局单例
_workflow: StateGraph | None = None


def get_workflow() -> StateGraph:
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow
