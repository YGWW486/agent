"""LLM Provider — LangChain 原生抽象 + TokenTracker 回调"""

import logging
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.callbacks import BaseCallbackHandler

from config.settings import get_settings

logger = logging.getLogger(__name__)


class StructuredOutputError(Exception):
    """LLM 未能产出有效的结构化输出"""


# ── Token 追踪（全局单例回调，替代旧 AnthropicLLM / DeepSeekLLM 各自的 _track_usage）──

class TokenTracker(BaseCallbackHandler):
    """跨所有 LLM 调用的统一 token 追踪器"""

    def __init__(self):
        self._usage: dict[str, int] = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}

    @property
    def model(self) -> str:
        settings = get_settings()
        if settings.LLM_PROVIDER == "deepseek":
            return settings.DEEPSEEK_DEFAULT_MODEL
        return settings.ANTHROPIC_DEFAULT_MODEL

    def token_usage(self) -> dict[str, int]:
        return dict(self._usage)

    def reset_usage(self) -> None:
        self._usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}

    def on_llm_end(self, response, **kwargs) -> None:
        try:
            token_usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
            if not token_usage:
                return
            self._usage["input"] += (
                token_usage.get("input_tokens", 0)
                or token_usage.get("prompt_tokens", 0)
            )
            self._usage["output"] += (
                token_usage.get("output_tokens", 0)
                or token_usage.get("completion_tokens", 0)
            )
            self._usage["cache_read"] += token_usage.get("cache_read_input_tokens", 0)
            self._usage["cache_write"] += token_usage.get("cache_creation_input_tokens", 0)
        except Exception:
            pass


_tracker = TokenTracker()


def get_llm_info() -> dict:
    """供 health check 使用：返回当前模型名 + token 用量"""
    return {
        "model": _tracker.model,
        "token_usage": _tracker.token_usage(),
    }


def reset_usage() -> None:
    _tracker.reset_usage()


# ── DeepSeek 模型名映射 ────────────────────────────

def _map_model_name(model: str) -> str:
    """将 Claude 模型名映射为 DeepSeek V4 等价模型"""
    m = model.lower()
    if "haiku" in m:
        return "deepseek-v4-flash"
    elif "opus" in m:
        return "deepseek-v4-pro"
    return "deepseek-v4-pro"


# ── 工厂函数 ──────────────────────────────────────

def create_llm(
    model: str | None = None,
    mode: Literal["chat", "thinking", "structured"] = "chat",
    thinking_budget: int | None = None,
) -> BaseChatModel:
    """根据 LLM_PROVIDER 返回 ChatAnthropic 或 ChatOpenAI 实例。

    mode:
      - "chat":       普通对话
      - "thinking":   启用 extended thinking（DeepSeek 走 thinking/thinking_max）
      - "structured": 配合 with_structured_output() 使用，DeepSeek 强制 non-thinking
    """
    settings = get_settings()

    if settings.LLM_PROVIDER == "deepseek":
        resolved_model = _map_model_name(model or settings.DEEPSEEK_DEFAULT_MODEL)

        extra_body: dict[str, str] = {}
        if mode == "structured":
            extra_body["thinking_mode"] = "non-thinking"
        elif mode == "thinking":
            extra_body["thinking_mode"] = (
                "thinking_max" if (thinking_budget and thinking_budget > 16000) else "thinking"
            )

        return ChatOpenAI(
            model=resolved_model,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            max_tokens=settings.DEEPSEEK_MAX_TOKENS,
            temperature=settings.DEEPSEEK_TEMPERATURE,
            model_kwargs=extra_body,
            callbacks=[_tracker],
        )

    # Anthropic
    resolved_model = model or settings.ANTHROPIC_DEFAULT_MODEL

    kwargs: dict = dict(
        model=resolved_model,
        api_key=settings.ANTHROPIC_API_KEY,
        max_tokens=settings.ANTHROPIC_MAX_TOKENS,
        callbacks=[_tracker],
    )

    if mode == "thinking":
        kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": thinking_budget or settings.ANTHROPIC_THINKING_BUDGET,
        }
    elif mode == "structured":
        kwargs["temperature"] = 0.4
    else:
        kwargs["temperature"] = 0.7

    return ChatAnthropic(**kwargs)
