# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 — Embedding 代理
支持本地/云端两种模式，兼容多种API格式：
  - 本地模式：LM Studio、Ollama 等本地服务
  - 云端模式：OpenAI、SiliconFlow、自定义 API

优先级队列 + 工作线程，确保建库和查询的 embedding 请求互不阻塞：
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

logger = logging.getLogger("Embedder")

_global_proxy = None
_global_lock = threading.Lock()

# 云端提供商 URL 映射
CLOUD_URL_MAP = {
    "openai": "https://api.openai.com/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "moonshot": "https://api.moonshot.cn/v1",
}


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

        # 读取模式配置
        mode = os.getenv("EMBEDDING_MODE", "cloud").lower()

        if mode == "local":
            # 本地模式：直接使用完整 URL
            local_url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
            # 从 URL 中提取 base_url（去掉 /embeddings 后缀）
            if local_url.endswith("/embeddings"):
                base = local_url.rsplit("/embeddings", 1)[0]
            elif local_url.endswith("/v1/embeddings"):
                base = local_url.rsplit("/embeddings", 1)[0]
            else:
                base = local_url.rstrip("/")

            _global_proxy = EmbedderProxy(
                api_key="",
                base_url=base,
                model=model or os.getenv("EMBEDDING_LOCAL_MODEL", "text-embedding-qwen3-embedding-4b"),
                dim=dim or int(os.getenv("EMBEDDING_LOCAL_DIM", "2560")),
            )
            logger.info(f"Embedding 本地模式: {base}")
        else:
            # 云端模式
            provider = os.getenv("EMBEDDING_CLOUD_PROVIDER", "siliconflow").lower()

            if base_url:
                url = base_url.rstrip("/")
            elif provider in CLOUD_URL_MAP:
                url = CLOUD_URL_MAP[provider]
            else:
                url = os.getenv("EMBEDDING_CLOUD_URL", "https://api.siliconflow.cn/v1").rstrip("/")

            _global_proxy = EmbedderProxy(
                api_key=api_key or os.getenv("EMBEDDING_CLOUD_API_KEY", ""),
                base_url=url,
                model=model or os.getenv("EMBEDDING_CLOUD_MODEL", "BAAI/bge-m3"),
                dim=dim or int(os.getenv("EMBEDDING_CLOUD_DIM", "1024")),
            )
            logger.info(f"Embedding 云端模式: {provider} @ {url}")

        return _global_proxy
