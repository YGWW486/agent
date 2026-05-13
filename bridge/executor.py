import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Optional
import logging
import time

logger = logging.getLogger(__name__)


class AsyncExecutor:
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="agent_worker"
        )
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "active_workers": 0,
            "total_execution_time": 0,
            "avg_execution_time": 0
        }
        logger.info(f"AsyncExecutor initialized with {self.max_workers} workers")

    async def run(self, func: Callable, *args, **kwargs) -> Any:
        self._stats["tasks_submitted"] += 1
        start_time = time.time()
        try:
            self._stats["active_workers"] += 1
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                lambda: func(*args, **kwargs)
            )
        finally:
            execution_time = time.time() - start_time
            self._stats["active_workers"] -= 1
            self._stats["tasks_completed"] += 1
            self._stats["total_execution_time"] += execution_time
            if self._stats["tasks_completed"] > 0:
                self._stats["avg_execution_time"] = (
                    self._stats["total_execution_time"] / self._stats["tasks_completed"]
                )

    async def run_with_timeout(
        self,
        func: Callable,
        timeout: float,
        *args,
        **kwargs
    ) -> Any:
        return await asyncio.wait_for(
            self.run(func, *args, **kwargs),
            timeout=timeout
        )

    def shutdown(self, wait: bool = True):
        try:
            self.executor.shutdown(wait=wait)
            logger.info("AsyncExecutor shutdown")
        except Exception as e:
            logger.error(f"Error shutting down executor: {e}")

    def get_stats(self) -> dict:
        queue_size = 0
        if hasattr(self.executor, '_work_queue'):
            queue_size = self.executor._work_queue.qsize()

        return {
            "max_workers": self.max_workers,
            "active_workers": self._stats["active_workers"],
            "tasks_submitted": self._stats["tasks_submitted"],
            "tasks_completed": self._stats["tasks_completed"],
            "queue_size": queue_size,
            "total_execution_time": self._stats["total_execution_time"],
            "avg_execution_time": self._stats["avg_execution_time"]
        }


_executor: Optional[AsyncExecutor] = None


def get_executor() -> AsyncExecutor:
    global _executor
    if _executor is None:
        _executor = AsyncExecutor()
    return _executor
