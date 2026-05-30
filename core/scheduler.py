# -*- coding: utf-8 -*-
"""
Ezy-RAG 鈥?缁熶竴浠诲姟璋冨害鍣?鏀寔 Embedding 鐨勪紭鍏堢骇闃熷垪璋冨害锛岀‘淇濆缓搴撳拰鏌ヨ璇锋眰浜掍笉闃诲

鍔熻兘锛?  - 浼樺厛绾ч槦鍒楋細priority=0 (VIP鏌ヨ) / priority=100 (寤哄簱)
  - 濮旀墭 core.api.EmbeddingAPI 鎵ц瀹為檯鍚戦噺鍖?
鐢ㄦ硶:
  from core.scheduler import get_scheduler

  scheduler = get_scheduler()
  embeddings = scheduler.embed_sync(["鏂囨湰1", "鏂囨湰2"], priority=100)
  vec = await scheduler.embed_async(["鏌ヨ鏂囨湰"], priority=0)
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
    """浼樺厛绾ч槦鍒楄皟搴﹀櫒锛屽鎵?EmbeddingAPI 鎵ц鍚戦噺鍖?""

    def __init__(self, emb_api):
        self._api = emb_api
        self._queue = queue.PriorityQueue()
        self._results = {}
        self._results_lock = threading.Lock()
        self._running = False
        self._thread = None
        self.start()
        logger.info(f"璋冨害鍣ㄥ凡鍚姩 (model={emb_api.get_info()['model']})")

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
        """鍚屾 embedding"""
        task_id = uuid.uuid4().hex
        event = threading.Event()
        self._queue.put((priority, task_id, texts, event))
        if not event.wait(timeout=timeout):
            raise TimeoutError(f"Embedding 鏈嶅姟瓒呮椂 ({timeout}s)")
        with self._results_lock:
            result = self._results.pop(task_id, None)
        if isinstance(result, Exception):
            raise result
        return result

    async def embed_async(self, texts, priority=0, timeout=60):
        """寮傛 embedding"""
        return await asyncio.to_thread(self.embed_sync, texts, priority=priority, timeout=timeout)


def get_scheduler():
    """鑾峰彇鍏ㄥ眬鍗曚緥璋冨害鍣?""
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
