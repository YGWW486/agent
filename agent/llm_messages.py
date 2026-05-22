"""多轮 tool calling 消息组装 — Anthropic / OpenAI(DeepSeek) 双格式"""

from __future__ import annotations

import json
import uuid
from typing import Any

from agent.llm import AnthropicLLM, DeepSeekLLM


class ToolUseRequest:
    """统一的 tool_use 请求"""

    def __init__(self, *, id: str, name: str, input: dict[str, Any]):
        self.id = id
        self.name = name
        self.input = input


def is_anthropic_llm(llm: Any) -> bool:
    return isinstance(llm, AnthropicLLM)


def uses_anthropic_messages(llm: Any) -> bool:
    """Anthropic 消息格式（含测试 FakeLLM）；DeepSeek 用 OpenAI tool 格式"""
    return not isinstance(llm, DeepSeekLLM)


def _is_anthropic_response(response: Any) -> bool:
    return hasattr(response, "content") and not hasattr(response, "choices")


def extract_tool_uses(response: Any, llm: Any) -> list[ToolUseRequest]:
    """从 LLM 响应中提取 tool_use / tool_calls"""
    if is_anthropic_llm(llm) or _is_anthropic_response(response):
        uses: list[ToolUseRequest] = []
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                uses.append(
                    ToolUseRequest(
                        id=block.id,
                        name=block.name,
                        input=dict(block.input) if block.input else {},
                    )
                )
        return uses

    # DeepSeek / OpenAI
    choice = response.choices[0]
    tool_calls = choice.message.tool_calls or []
    uses = []
    for tc in tool_calls:
        raw = tc.function.arguments
        try:
            inp = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            inp = {}
        uses.append(
            ToolUseRequest(
                id=tc.id,
                name=tc.function.name,
                input=inp if isinstance(inp, dict) else {},
            )
        )
    return uses


def append_assistant_tool_uses(
    messages: list[dict[str, Any]],
    response: Any,
    llm: Any,
) -> None:
    """将含 tool_use 的 assistant 消息追加到 messages"""
    if is_anthropic_llm(llm) or _is_anthropic_response(response):
        content: list[dict[str, Any]] = []
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "text" and getattr(block, "text", ""):
                content.append({"type": "text", "text": block.text})
            elif btype == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": dict(block.input) if block.input else {},
                })
        messages.append({"role": "assistant", "content": content})
        return

    choice = response.choices[0]
    msg = choice.message
    entry: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        entry["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    messages.append(entry)


def append_tool_results(
    messages: list[dict[str, Any]],
    tool_uses: list[ToolUseRequest],
    results_text: list[str],
    llm: Any,
) -> None:
    """追加 tool 执行结果"""
    if uses_anthropic_messages(llm):
        content = [
            {
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": text,
            }
            for tu, text in zip(tool_uses, results_text)
        ]
        messages.append({"role": "user", "content": content})
        return

    for tu, text in zip(tool_uses, results_text):
        messages.append({
            "role": "tool",
            "tool_call_id": tu.id,
            "content": text,
        })


def synthetic_tool_use(name: str, input: dict[str, Any]) -> ToolUseRequest:
    """测试用 synthetic tool_use"""
    return ToolUseRequest(id=f"toolu_{uuid.uuid4().hex[:12]}", name=name, input=input)
