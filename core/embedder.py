# -*- coding: utf-8 -*-
"""
Ezy-RAG V1.0.0 — Embedding 代理
优先级队列 + 工作线程，确保建库和查询的 embedding 请求互不阻塞：
  - priority=0: MCP 查询 (VIP, 插队)
  - priority=100: 建库切片 (普通, 排队)
"""
import os
import sys
import threading, queue, uuid, time, logging
from pathlib import Path
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logger = logging.getLogger("Embedder")

_global_proxy = None
_global_lock = threading.Lock()


class EmbedderProxy:
    def __init__(self, api_key: str, base_url: str, model: str, dim: int):
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=30)
        self._model = model
        self._dim = dim
        self._queue = queue.PriorityQueue()
        self._results = {}
        self._results_lock = threading.Lock()
        self._running = False
        self._thread = None
        self._cancelled = threading.Event()  # 标记是否已取消
        self._current_task_id = None  # 当前正在处理的任务
        self._current_task_lock = threading.Lock()
        self.start()

    def start(self):
        if self._running:
            return
        self._running = True
        self._cancelled.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="EmbedderWorker")
        self._thread.start()
        logger.info("Embedding 代理已启动")

    def stop(self):
        self._running = False

    def cancel_all(self):
        """取消所有待处理任务，并标记丢弃当前任务结果"""
        self._cancelled.set()
        cancelled = 0

        # 清空队列中的待处理任务
        while not self._queue.empty():
            try:
                priority, task_id, texts, event = self._queue.get_nowait()
                with self._results_lock:
                    self._results[task_id] = Exception("向量化已取消")
                event.set()
                cancelled += 1
            except queue.Empty:
                break

        # 如果有正在运行的任务，解除其阻塞
        with self._current_task_lock:
            if self._current_task_id:
                with self._results_lock:
                    if self._current_task_id not in self._results:
                        self._results[self._current_task_id] = Exception("向量化已取消")
                # 不需要 set event，因为 worker 会自己 set

        if cancelled > 0:
            logger.info(f"已取消 {cancelled} 个待处理任务")
        logger.info("取消标志已设置，当前任务完成后将丢弃结果")

    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self._cancelled.is_set()

    def _worker(self):
        while self._running:
            try:
                priority, task_id, texts, event = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            with self._current_task_lock:
                self._current_task_id = task_id

            try:
                # 如果已取消，直接标记失败
                if self._cancelled.is_set():
                    with self._results_lock:
                        self._results[task_id] = Exception("向量化已取消")
                    event.set()
                    continue

                resp = self._client.embeddings.create(model=self._model, input=texts)
                vectors = []
                for item in resp.data:
                    vec = item.embedding
                    while isinstance(vec, list) and len(vec) > 0 and isinstance(vec[0], list):
                        vec = vec[0]
                    if len(vec) != self._dim:
                        raise ValueError(f"Embedding 服务返回向量维度 {len(vec)}，期望 {self._dim}")
                    vectors.append(vec)

                # 如果在 API 调用期间被取消，丢弃结果
                if self._cancelled.is_set():
                    with self._results_lock:
                        self._results[task_id] = Exception("向量化已取消")
                    logger.info("任务在 API 调用期间被取消，丢弃结果")
                else:
                    with self._results_lock:
                        self._results[task_id] = vectors

            except Exception as e:
                with self._results_lock:
                    self._results[task_id] = e
            finally:
                with self._current_task_lock:
                    self._current_task_id = None
                event.set()

    def embed_sync(self, texts, priority=100, timeout=300):
        """同步 embedding"""
        # 如果已取消，直接抛出异常
        if self._cancelled.is_set():
            raise Exception("向量化已取消")

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
        import asyncio
        return await asyncio.to_thread(self.embed_sync, texts, priority=priority, timeout=timeout)


def _resolve_base_url(api_url: str) -> str:
    """从 EMBEDDING_API_URL 推导 OpenAI SDK 需要的 base_url"""
    url = api_url.rstrip("/")
    if url.endswith("/embeddings"):
        url = url[:-len("/embeddings")]
    if not url.endswith("/v1"):
        url = url + "/v1"
    return url + "/"


def get_lm_proxy(api_key=None, base_url=None, model=None, dim=None):
    """获取全局单例 Embedding 代理"""
    global _global_proxy
    if _global_proxy is not None:
        return _global_proxy

    with _global_lock:
        if _global_proxy is not None:
            return _global_proxy

        embedding_url = os.getenv("EMBEDDING_API_URL", "http://127.0.0.1:5000/v1/embeddings")
        _global_proxy = EmbedderProxy(
            api_key=api_key or os.getenv("EMBEDDING_API_KEY", "") or "no-key",
            base_url=base_url or _resolve_base_url(embedding_url),
            model=model or os.getenv("EMBEDDING_MODEL", "text-embedding-qwen3-embedding-4b"),
            dim=dim or int(os.getenv("EMBEDDING_DIM", "2560")),
        )
        return _global_proxy
