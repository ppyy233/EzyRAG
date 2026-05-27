# -*- coding: utf-8 -*-
"""
Embedding 代理 — 优先级队列 + 工作线程
确保建库和查询的 embedding 请求互不阻塞：
  - priority=0: MCP 查询 (VIP, 插队)
  - priority=100: 建库切片 (普通, 排队)

用法:
  from core.embedder import get_lm_proxy

  # core/builder.py (同步)
  proxy = get_lm_proxy()
  embeddings = proxy.embed_sync(["文本1", "文本2"], priority=100)

  # servers/mcp.py (异步)
  proxy = get_lm_proxy()
  vec = await proxy.embed_async(["查询文本"], priority=0)
"""
import os
import sys
import threading, queue, uuid, time, logging
from pathlib import Path
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import settings  # 加载 .env

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
        self.start()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True, name="EmbedderWorker")
        self._thread.start()
        logger.info("Embedding 代理已启动")

    def stop(self):
        self._running = False

    def _worker(self):
        while self._running:
            try:
                priority, task_id, texts, event = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                resp = self._client.embeddings.create(model=self._model, input=texts)
                vectors = []
                for item in resp.data:
                    vec = item.embedding
                    if len(vec) != self._dim:
                        raise ValueError(f"Embedding 服务返回向量维度 {len(vec)}，期望 {self._dim}")
                    vectors.append(vec)
                with self._results_lock:
                    self._results[task_id] = vectors
            except Exception as e:
                with self._results_lock:
                    self._results[task_id] = e
            finally:
                event.set()

    def embed_sync(self, texts, priority=100, timeout=300):
        """同步 embedding——core/builder.py 使用"""
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
        """异步 embedding——servers/mcp.py 使用"""
        import asyncio
        return await asyncio.to_thread(self.embed_sync, texts, priority=priority, timeout=timeout)


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
            api_key=api_key or os.getenv("EMBEDDING_API_KEY", ""),
            base_url=base_url or embedding_url.rsplit("/v1/", 1)[0] + "/v1/",
            model=model or os.getenv("EMBEDDING_MODEL", "text-embedding-qwen3-embedding-4b"),
            dim=dim or int(os.getenv("EMBEDDING_DIM", "2560")),
        )
        return _global_proxy
