"""Coder 只读 tool 子循环 — explore → output_code"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from agent.budget import BudgetExceeded, task_tokens_from_state, usage_total
from agent.context import GraphIndex, get_graph_index
from agent.llm_messages import (
    append_assistant_tool_uses,
    append_tool_results,
    extract_tool_uses,
)
from agent.models import CoderOutput
from agent.observation import build_tool_result_observation
from agent.runtime_events import emit_sse
from agent.tools.registry import (
    READ_ONLY_TOOL_DEFINITIONS,
    ToolRegistry,
    tool_result_to_text,
)
from agent.tools.workspace import WorkspaceGuard
from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

CODER_SYSTEM_TOOLS = """你是一个资深软件工程师。在输出最终代码前，你可以使用只读工具探索代码库：
- read_file：读取文件内容
- list_dir：列出目录
- search_repo：搜索代码（text=ripgrep，graph=知识图谱）

此阶段请勿调用 output_code。根据探索结果理解项目结构后，将在下一轮输出代码。"""

CODER_SYSTEM_FINAL = """你是一个资深软件工程师。你的唯一输出方式是调用 `output_code` 工具。

你会收到一个任务定义（描述、文件范围、验收条件）、项目上下文，以及你可能已通过工具探索到的信息。

你必须：
1. 生成完整、可运行的代码变更，并通过 `files` 字段列出所有变更文件：
   - `path`：文件路径（相对于项目根目录）
   - `content`：文件的完整新内容
   - `original_content`：修改已有文件时填修改前内容；新建文件填空字符串
2. 在 `diff` 字段中给出可读的变更摘要
3. 对每一条验收条件进行自检（satisfied / not_satisfied / uncertain）并给出证据

如果收到了审查反馈（revision），先解决所有反馈问题再输出。

只输出 output_code 工具调用，不要输出任何其他文字。"""


EmitFn = Callable[[dict[str, Any]], Awaitable[None]]


def coder_tools_enabled(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.CODER_TOOLS_ENABLED)


def _check_loop_budget(state: dict[str, Any], llm: Any) -> None:
    settings = get_settings()
    base = task_tokens_from_state(state)
    used = usage_total(llm.token_usage())
    total = base + used
    if total >= settings.TASK_TOKEN_LIMIT:
        raise BudgetExceeded(
            f"任务 Token 超限 ({total} >= {settings.TASK_TOKEN_LIMIT})",
            kind="task",
        )


async def _emit_tool_events(
    emit: EmitFn | None,
    *,
    phase: str,
    tool: str,
    tool_input: dict,
    result: dict | None = None,
) -> None:
    if emit is None:
        return
    if phase == "call":
        await emit({
            "event": "tool_call",
            "node": "coder",
            "tool": tool,
            "input": tool_input,
        })
    else:
        tool_obs = build_tool_result_observation(
            tool,
            result or {},
            thread_id="",
        )
        await emit({
            "event": "tool_result",
            "node": "coder",
            "tool": tool,
            "tool_summary": result.get("summary", "") if result else "",
            **tool_obs,
        })


async def run_coder_with_tools(
    *,
    llm: Any,
    user_prompt: str,
    state: dict[str, Any],
    settings: Settings | None = None,
    index: GraphIndex | None = None,
    emit: EmitFn | None = None,
) -> CoderOutput:
    """多轮只读 tool 探索后 structured output_code"""
    settings = settings or get_settings()
    workspace = WorkspaceGuard.from_state(state)
    if index is None:
        index = get_graph_index()
    registry = ToolRegistry(workspace, index=index if index.is_loaded() else None)

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    sse_emit = emit or emit_sse

    for round_idx in range(settings.CODER_TOOL_MAX_ROUNDS):
        _check_loop_budget(state, llm)

        try:
            response = await llm.chat_with_tools(
                system=CODER_SYSTEM_TOOLS,
                messages=messages,
                tools=READ_ONLY_TOOL_DEFINITIONS,
            )
        except Exception as e:
            logger.warning(f"[CoderLoop] chat_with_tools round {round_idx} failed: {e}")
            break

        tool_uses = extract_tool_uses(response, llm)
        if not tool_uses:
            break

        append_assistant_tool_uses(messages, response, llm)

        results_text: list[str] = []
        for tu in tool_uses:
            await _emit_tool_events(
                sse_emit, phase="call", tool=tu.name, tool_input=tu.input
            )
            result = registry.execute(tu.name, tu.input)
            await _emit_tool_events(
                sse_emit, phase="result", tool=tu.name, tool_input=tu.input, result=result
            )
            results_text.append(tool_result_to_text(tu.name, result))

        append_tool_results(messages, tool_uses, results_text, llm)

    messages.append({
        "role": "user",
        "content": "探索完成。请调用 output_code 工具输出完整代码变更与自检报告。",
    })

    _check_loop_budget(state, llm)
    return await llm.chat_with_structured_output(
        system=CODER_SYSTEM_FINAL,
        messages=messages,
        output_model=CoderOutput,
        tool_name="output_code",
        tool_description="输出代码变更和自检报告",
    )


async def run_coder_single_shot(
    *,
    llm: Any,
    user_prompt: str,
    system: str,
) -> CoderOutput:
    """无工具 — 与现网一致的单次 structured 调用"""
    return await llm.chat_with_structured_output(
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
        output_model=CoderOutput,
        tool_name="output_code",
        tool_description="输出代码变更和自检报告",
    )
