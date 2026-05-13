import asyncio
import logging
from typing import Callable, Any, TypeVar, Optional, Dict
from functools import wraps
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_delay: float = 0.5
    max_delay: float = 5.0
    exponential_base: float = 2.0
    exceptions: tuple = (Exception,)


async def retry_async(
    func: Callable[..., Any],
    config: Optional[RetryConfig] = None,
    *args,
    **kwargs
) -> Any:
    config = config or RetryConfig()
    last_exception = None
    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except config.exceptions as e:
            last_exception = e
            if attempt < config.max_retries:
                delay = min(
                    config.initial_delay * (config.exponential_base ** attempt),
                    config.max_delay
                )
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {config.max_retries + 1} attempts failed")
    raise last_exception


def with_retry(config: Optional[RetryConfig] = None):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(func, config, *args, **kwargs)
        return wrapper
    return decorator


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == "open":
            if self.last_failure_time and \
               (asyncio.get_running_loop().time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "half_open"
                logger.info("Circuit breaker: opening half-open")
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
    def __init__(self):
        self.fallbacks: Dict[str, Callable] = {}
    
    def register_fallback(self, func_name: str, fallback: Callable):
        self.fallbacks[func_name] = fallback
    
    async def execute_with_fallback(
        self, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            func_name = getattr(func, '__name__', 'unknown')
            fallback = self.fallbacks.get(func_name)
            if fallback:
                logger.info(f"Executing fallback for {func_name}")
                return await fallback(*args, **kwargs)
            else:
                logger.error(f"No fallback for {func_name}")
                raise
