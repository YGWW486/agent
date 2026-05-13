import logging
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from pydantic import BaseModel

from config.settings import get_settings

logger = logging.getLogger(__name__)


class StructuredOutputError(Exception):
    """LLM 未能产出有效的 tool_use 结构化输出"""


# ── Provider 协议（鸭子类型，接口一致即可互换） ──

class AnthropicLLM:
    """Anthropic SDK 封装 — tool use / thinking / prompt caching / token tracking"""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.ANTHROPIC_DEFAULT_MODEL
        self.max_tokens = settings.ANTHROPIC_MAX_TOKENS
        self._client: AsyncAnthropic | None = None
        self._token_usage: dict[str, int] = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}

    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    def _track_usage(self, usage: Any) -> None:
        if hasattr(usage, "input_tokens"):
            self._token_usage["input"] += usage.input_tokens
            self._token_usage["output"] += getattr(usage, "output_tokens", 0)
            self._token_usage["cache_read"] += getattr(usage, "cache_read_input_tokens", 0)
            self._token_usage["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0)

    def token_usage(self) -> dict[str, int]:
        return dict(self._token_usage)

    def reset_usage(self) -> None:
        self._token_usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}

    async def chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> str:
        response: Message = await self.client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        )
        self._track_usage(response.usage)
        return response.content[0].text

    async def chat_with_thinking(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        thinking_budget: int | None = None,
    ) -> dict[str, str]:
        settings = get_settings()
        response: Message = await self.client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system,
            messages=messages,
            thinking={"type": "enabled", "budget_tokens": thinking_budget or settings.ANTHROPIC_THINKING_BUDGET},
        )
        self._track_usage(response.usage)
        thinking = ""
        text = ""
        for block in response.content:
            if block.type == "thinking":
                thinking = block.thinking
            elif block.type == "text":
                text = block.text
        return {"thinking": thinking, "response": text}

    async def chat_with_tools(
        self,
        system: str,
        messages: list[dict[str, str]],
        tools: list[dict],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> Message:
        response: Message = await self.client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        self._track_usage(response.usage)
        return response

    async def chat_with_cache(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        cache_system: bool = True,
    ) -> str:
        system_block: dict[str, Any] = {"type": "text", "text": system}
        if cache_system:
            system_block["cache_control"] = {"type": "ephemeral"}

        cached_messages: list[dict[str, Any]] = []
        for i, msg in enumerate(messages):
            content: Any = msg["content"]
            if i == len(messages) - 1:
                cached_messages.append({
                    "role": msg["role"],
                    "content": [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}],
                })
            else:
                cached_messages.append({"role": msg["role"], "content": content})

        response: Message = await self.client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=[system_block],
            messages=cached_messages,
        )
        self._track_usage(response.usage)
        return response.content[0].text

    async def chat_with_structured_output(
        self,
        system: str,
        messages: list[dict[str, str]],
        output_model: type[BaseModel],
        tool_name: str,
        tool_description: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.4,
    ) -> BaseModel:
        import json as _json

        tool_definition = {
            "name": tool_name,
            "description": tool_description,
            "input_schema": output_model.model_json_schema(),
        }

        response: Message = await self.client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
            tools=[tool_definition],
            tool_choice={"type": "tool", "name": tool_name},
        )
        self._track_usage(response.usage)

        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                raw_input = getattr(block, "input", {})
                if isinstance(raw_input, str):
                    raw_input = _json.loads(raw_input)
                try:
                    return output_model.model_validate(raw_input)
                except Exception as e:
                    raise StructuredOutputError(
                        f"输出校验失败（{tool_name}）: {e}. Raw input: {str(raw_input)[:200]}"
                    )

        raise StructuredOutputError(
            f"LLM 未调用 {tool_name} tool。Content blocks: {[getattr(b, 'type', 'unknown') for b in response.content]}"
        )


# ── DeepSeek Provider ────────────────────────────

class DeepSeekLLM:
    """DeepSeek V4 API 封装 — OpenAI 兼容接口 + thinking_mode + reasoning_content 回传

    V4 关键规范 (api-docs.deepseek.com):
    - 模型: deepseek-v4-pro (1.6T/49B) | deepseek-v4-flash (284B/13B)
    - 上下文: 1M tokens
    - 推理模式: non-thinking | thinking | thinking_max
    - temperature: 官方推荐 1.0（非 0.4-0.7）
    - reasoning_content: 必须回传，否则 400 错误
    - 旧 ID deepseek-chat/reasoner 将于 2026-07-24 下线
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.model = model or settings.DEEPSEEK_DEFAULT_MODEL
        self.max_tokens = settings.DEEPSEEK_MAX_TOKENS
        self.temperature = settings.DEEPSEEK_TEMPERATURE
        self.thinking_mode = settings.DEEPSEEK_THINKING_MODE
        self._client: Any = None  # AsyncOpenAI, 懒加载
        self._token_usage: dict[str, int] = {"input": 0, "output": 0, "reasoning": 0}

    @property
    def client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI  # 懒加载，仅 DeepSeek 用户需要
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=get_settings().DEEPSEEK_BASE_URL,
            )
        return self._client

    def _track_usage(self, usage: Any) -> None:
        if hasattr(usage, "prompt_tokens"):
            self._token_usage["input"] += usage.prompt_tokens
            self._token_usage["output"] += getattr(usage, "completion_tokens", 0)
        # V4 reasoning tokens (如果存在)
        if hasattr(usage, "completion_tokens_details") and usage.completion_tokens_details:
            rt = getattr(usage.completion_tokens_details, "reasoning_tokens", 0)
            if rt:
                self._token_usage["reasoning"] += rt

    def token_usage(self) -> dict[str, int]:
        return dict(self._token_usage)

    def reset_usage(self) -> None:
        self._token_usage = {"input": 0, "output": 0, "reasoning": 0}

    def _build_messages(self, system: str, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        """构建消息列表，保留 reasoning_content 用于多轮回传"""
        msgs: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for m in messages:
            entry: dict[str, Any] = {"role": m["role"], "content": m["content"]}
            # 回传 reasoning_content（V4 多轮必需）
            if "reasoning_content" in m:
                entry["reasoning_content"] = m["reasoning_content"]
            if "tool_calls" in m:
                entry["tool_calls"] = m["tool_calls"]
            if "tool_call_id" in m:
                entry["tool_call_id"] = m["tool_call_id"]
            msgs.append(entry)
        return msgs

    def _resolve_model(self, model: str | None) -> str:
        """将 Claude 模型名映射为 DeepSeek V4 等价模型"""
        m = model or self.model
        # 如果 MODEL_ROUTING 里还是 Claude 模型名，自动映射
        if "claude" in m.lower():
            if "haiku" in m.lower():
                return "deepseek-v4-flash"
            elif "opus" in m.lower():
                return "deepseek-v4-pro"
            return "deepseek-v4-pro"
        return m

    def _extra_body(self, thinking_mode: str | None = None) -> dict[str, str]:
        """构建 extra_body，注入 thinking_mode"""
        mode = thinking_mode or self.thinking_mode
        return {"thinking_mode": mode}

    async def chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        msgs = self._build_messages(system, messages)
        response = await self.client.chat.completions.create(
            model=self._resolve_model(model),
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            messages=msgs,
            extra_body=self._extra_body("non-thinking"),
        )
        self._track_usage(response.usage)
        return response.choices[0].message.content or ""

    async def chat_with_thinking(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        thinking_budget: int | None = None,
    ) -> dict[str, str]:
        """V4 thinking 模式 — 返回 reasoning_content + content"""
        msgs = self._build_messages(system, messages)
        mode = "thinking_max" if (thinking_budget and thinking_budget > 16000) else "thinking"
        response = await self.client.chat.completions.create(
            model=self._resolve_model(model),
            max_tokens=max_tokens or self.max_tokens,
            temperature=self.temperature,
            messages=msgs,
            extra_body=self._extra_body(mode),
        )
        self._track_usage(response.usage)
        choice = response.choices[0]
        return {
            "thinking": getattr(choice.message, "reasoning_content", "") or "",
            "response": choice.message.content or "",
        }

    async def chat_with_tools(
        self,
        system: str,
        messages: list[dict[str, str]],
        tools: list[dict],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]
        msgs = self._build_messages(system, messages)
        response = await self.client.chat.completions.create(
            model=self._resolve_model(model),
            max_tokens=max_tokens or self.max_tokens,
            temperature=self.temperature,
            messages=msgs,
            tools=openai_tools,
            extra_body={"thinking_mode": "non-thinking"},  # tool calling 不用 thinking
        )
        self._track_usage(response.usage)
        return response

    async def chat_with_cache(
        self,
        system: str,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        cache_system: bool = True,
    ) -> str:
        # V4 暂无显式 prompt caching API，回退为普通 chat
        return await self.chat(system, messages, model=model, max_tokens=max_tokens)

    async def chat_with_structured_output(
        self,
        system: str,
        messages: list[dict[str, str]],
        output_model: type[BaseModel],
        tool_name: str,
        tool_description: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        """V4 tool calling — tool_choice="auto" + non-thinking

        DeepSeek 限制:
        - deepseek-reasoner 不支持 tool_choice 参数
        - V4 thinking 模式内部路由到 reasoner 后端
        - 仅 "auto" / "any" / 不设 tool_choice 可用
        ∴ 工具调用时关闭 thinking，用 tool_choice="auto"
        """
        import json as _json

        resolved_model = self._resolve_model(model)
        logger.info(f"[DeepSeek] structured_output model={resolved_model} tool={tool_name}")

        openai_tools = [{
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_description,
                "parameters": output_model.model_json_schema(),
            },
        }]
        msgs = self._build_messages(system, messages)
        try:
            response = await self.client.chat.completions.create(
                model=resolved_model,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
                messages=msgs,
                tools=openai_tools,
                extra_body={"thinking_mode": "non-thinking"},
            )
        except Exception as e:
            logger.error(f"[DeepSeek] API 调用异常: {e}")
            raise
        self._track_usage(response.usage)

        choice = response.choices[0]
        finish_reason = choice.finish_reason
        content = choice.message.content or ""
        tool_calls = choice.message.tool_calls or []
        logger.info(f"[DeepSeek] finish={finish_reason} tool_calls={len(tool_calls)} content_len={len(content)}")

        if tool_calls:
            raw_args = tool_calls[0].function.arguments
            try:
                return output_model.model_validate(_json.loads(raw_args))
            except Exception as e:
                raise StructuredOutputError(f"输出校验失败（{tool_name}）: {e}. Raw: {raw_args[:200]}")

        # tool_calls 为空，检查 finish_reason
        if finish_reason == "stop":
            # LLM 返回了纯文字，尝试从中解析 JSON
            logger.warning(f"[DeepSeek] 未调用 tool，返回文字: {content[:200]}")
            if content.strip():
                try:
                    return output_model.model_validate(_json.loads(content))
                except Exception:
                    pass
            raise StructuredOutputError(
                f"LLM 返回文字而非 tool 调用（{tool_name}）: {content[:200]}"
            )
        else:
            raise StructuredOutputError(
                f"LLM 调用异常 finish={finish_reason}（{tool_name}）: {content[:200]}"
            )


# ── Provider 工厂 ──────────────────────────────

_llm: AnthropicLLM | DeepSeekLLM | None = None


def get_llm(model: str | None = None) -> AnthropicLLM | DeepSeekLLM:
    global _llm
    settings = get_settings()
    if _llm is None:
        if settings.LLM_PROVIDER == "deepseek":
            _llm = DeepSeekLLM(model=model)
        else:
            _llm = AnthropicLLM(model=model)
    return _llm
