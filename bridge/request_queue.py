import asyncio
from typing import Any, Optional, Dict
import logging
import time

from config.settings import get_settings

logger = logging.getLogger(__name__)


class RequestQueue:
    def __init__(self, maxsize: Optional[int] = None):
        settings = get_settings()
        self.maxsize = maxsize or settings.QUEUE_MAXSIZE
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=self.maxsize)
        self._stats = {
            "enqueued": 0,
            "dequeued": 0,
            "rejected": 0,
            "full_count": 0,
            "total_wait_time": 0,
            "total_process_time": 0,
            "tasks_processed": 0
        }
        self._task_metadata: Dict[str, Dict] = {}
    
    async def put(self, item: Any, timeout: Optional[float] = None, priority: int = 0) -> bool:
        """添加任务到队列，支持优先级"""
        self._stats["enqueued"] += 1
        # 添加优先级信息
        if isinstance(item, dict):
            item["priority"] = priority
            item["enqueue_time"] = time.time()
        
        try:
            await asyncio.wait_for(self.queue.put(item), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            self._stats["rejected"] += 1
            self._stats["full_count"] += 1
            logger.warning(f"Queue full, rejecting request. Total rejections: {self._stats['rejected']}")
            return False
    
    async def get(self) -> Any:
        """从队列获取任务"""
        item = await self.queue.get()
        self._stats["dequeued"] += 1
        
        # 计算等待时间
        if isinstance(item, dict) and "enqueue_time" in item:
            wait_time = time.time() - item["enqueue_time"]
            self._stats["total_wait_time"] += wait_time
        
        return item
    
    def qsize(self) -> int:
        return self.queue.qsize()
    
    def is_full(self) -> bool:
        return self.queue.full()
    
    def is_empty(self) -> bool:
        return self.queue.empty()
    
    def get_stats(self) -> dict:
        """获取队列统计信息"""
        current_size = self.qsize()
        utilization = current_size / self.maxsize * 100 if self.maxsize > 0 else 0
        avg_wait_time = self._stats["total_wait_time"] / self._stats["tasks_processed"] if self._stats["tasks_processed"] > 0 else 0
        
        return {
            **self._stats,
            "current_size": current_size,
            "max_size": self.maxsize,
            "utilization": utilization,  # 数值类型
            "avg_wait_time": avg_wait_time
        }
    
    def task_done(self):
        """标记任务完成"""
        self.queue.task_done()
        self._stats["tasks_processed"] += 1
    
    def clear(self):
        """清空队列"""
        cleared_count = 0
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break
        logger.warning(f"Queue cleared, {cleared_count} tasks removed")


# 创建全局队列实例
request_queue = RequestQueue()
