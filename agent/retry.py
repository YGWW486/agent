"""容错机制 — CircuitBreaker + FallbackHandler

重试逻辑已迁移至 LangChain 原生的 with_retry()，本模块只保留
LangChain 未提供等价物的组件。
"""

import asyncio
import logging
from typing import Callable, Any, Optional, Dict

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """工作流级熔断器：连续失败 N 次后断路，recovery_timeout 秒后进入半开"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == "open":
            if self.last_failure_time and (
                asyncio.get_running_loop().time() - self.last_failure_time
            ) > self.recovery_timeout:
                self.state = "half_open"
                logger.info("Circuit breaker: half-open")
            else:
                raise Exception("Circuit breaker is open")
        try:
            result = await func(*args, **kwargs)
            if self.state == "half_open":
                self._reset()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise

    def _record_failure(self):
        self.failure_count += 1
        self.last_failure_time = asyncio.get_running_loop().time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def _reset(self):
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        logger.info("Circuit breaker closed")


class FallbackHandler:
    """业务级降级处理器"""

    def __init__(self):
        self.fallbacks: Dict[str, Callable] = {}

    def register_fallback(self, func_name: str, fallback: Callable):
        self.fallbacks[func_name] = fallback

    async def execute_with_fallback(self, func: Callable, *args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            func_name = getattr(func, "__name__", "unknown")
            fallback = self.fallbacks.get(func_name)
            if fallback:
                logger.info(f"Executing fallback for {func_name}")
                return await fallback(*args, **kwargs)
            else:
                logger.error(f"No fallback for {func_name}")
                raise
