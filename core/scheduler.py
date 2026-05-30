# -*- coding: utf-8 -*-
"""
Ezy-RAG — 统一任务调度器
支持 Embedding 的优先级队列调度，确保建库和查询请求互不阻塞

功能:
  - 优先级队列：priority=0 (VIP查询) / priority=100 (建库)
  - 委托 core.api.EmbeddingAPI 执行实际向量化
用法:
  from core.scheduler import get_scheduler

  scheduler = get_scheduler()
  embeddings = scheduler.embed_sync(["文本1", "文本2"], priority=100)
  vec = await scheduler.embed_async(["查询文本"], priority=0)
"""
import sys
import threading
import queue
import uuid
import asyncio
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logger = logging.getLogger("Scheduler")

_global_scheduler = None
_global_lock = threading.Lock()


class TaskScheduler:
    """优先级队列调度器，委托 EmbeddingAPI 执行向量化"""

    def __init__(self, emb_api):
        self._api = emb_api
        self._queue = queue.PriorityQueue()
        self._results = {}
        self._results_lock = threading.Lock()
        self._running = False
        self._thread = None
        self.start()
        logger.info(f"调度器已启动 (model={emb_api.get_info()['model']})")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True, name="SchedulerWorker")
        self._thread.start()

    def stop(self):
        self._running = False

    def _worker(self):
        while self._running:
            try:
                priority, task_id, texts, event = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                vectors = self._api.embed(texts)
                with self._results_lock:
                    self._results[task_id] = vectors
            except Exception as e:
                with self._results_lock:
                    self._results[task_id] = e
            finally:
                event.set()

    def embed_sync(self, texts, priority=100, timeout=300):
        """同步 embedding"""
        task_id = uuid.uuid4().hex
        event = threading.Event()
        self._queue.put((priority, task_id, texts, event))
        if not event.wait(timeout=timeout):
            raise TimeoutError(f"Embedding 服务超时 ({timeout}s)")
        with self._results_lock:
            result = self._results.pop(task_id, None)
        if isinstance(result, Exception):
            raise result
        return result

    async def embed_async(self, texts, priority=0, timeout=60):
        """异步 embedding"""
        return await asyncio.to_thread(self.embed_sync, texts, priority=priority, timeout=timeout)


def get_scheduler():
    """获取全局单例调度器"""
    global _global_scheduler
    if _global_scheduler is not None:
        return _global_scheduler

    with _global_lock:
        if _global_scheduler is not None:
            return _global_scheduler

        from core.api import EmbeddingAPI
        emb_api = EmbeddingAPI()
        _global_scheduler = TaskScheduler(emb_api)
        return _global_scheduler
