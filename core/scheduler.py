# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 — 统一任务调度器
支持 Embedding 的优先级队列调度，确保建库和查询请求互不阻塞

功能：
  - 优先级队列：priority=0 (VIP查询) / priority=100 (建库)
  - 本地/云端自动适配
  - 动态维度支持
  - 多提供商兼容（OpenAI/SiliconFlow/Jina/Cohere）

用法:
  from core.scheduler import get_scheduler

  # core/builder.py (同步)
  scheduler = get_scheduler()
  embeddings = scheduler.embed_sync(["文本1", "文本2"], priority=100)

  # servers/mcp.py (异步)
  scheduler = get_scheduler()
  vec = await scheduler.embed_async(["查询文本"], priority=0)
"""
import os
import sys
import threading, queue, uuid, time, logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logger = logging.getLogger("Scheduler")

_global_scheduler = None
_global_lock = threading.Lock()


def _detect_provider(url: str) -> str:
    """根据 URL 自动检测提供商"""
    if "cohere.com" in url:
        return "cohere"
    elif "jina.ai" in url:
        return "jina"
    else:
        return "openai"  # OpenAI 兼容格式（SiliconFlow、Ollama 等）


class TaskScheduler:
    """统一任务调度器"""
    
    def __init__(self, api_key: str, base_url: str, model: str, dim: int = None):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._dim = dim  # 可以为 None，自动检测
        self._provider = _detect_provider(base_url)
        self._queue = queue.PriorityQueue()
        self._results = {}
        self._results_lock = threading.Lock()
        self._running = False
        self._thread = None
        
        # 初始化客户端（OpenAI 兼容格式）
        if self._provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=30)
        else:
            self._client = None
        
        self.start()
        logger.info(f"调度器已启动 (提供商: {self._provider}, 模型: {model})")

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
                vectors = self._create_embeddings(texts)
                
                # 自动检测维度
                if self._dim is None:
                    self._dim = len(vectors[0])
                    logger.info(f"自动检测维度: {self._dim}")
                
                # 验证维度
                for vec in vectors:
                    if len(vec) != self._dim:
                        raise ValueError(
                            f"Embedding 维度不匹配！\n"
                            f"   服务返回: {len(vec)} 维\n"
                            f"   配置期望: {self._dim} 维\n"
                            f"   修复方法: 修改 config/.env 中的 EMBEDDING_CLOUD_DIM={len(vec)}，"
                            f"或留空让系统自动检测"
                        )
                
                with self._results_lock:
                    self._results[task_id] = vectors
            except Exception as e:
                with self._results_lock:
                    self._results[task_id] = e
            finally:
                event.set()

    def _create_embeddings(self, texts: list) -> list:
        """创建 Embedding（自动适配格式）"""
        if self._provider == "cohere":
            return self._create_cohere_embeddings(texts)
        else:
            return self._create_openai_embeddings(texts)

    def _create_openai_embeddings(self, texts: list) -> list:
        """OpenAI 兼容格式（支持 dimensions 参数）"""
        kwargs = {
            "model": self._model,
            "input": texts
        }
        
        # 如果配置了维度，传给 API
        if self._dim is not None:
            kwargs["dimensions"] = self._dim
        
        resp = self._client.embeddings.create(**kwargs)
        return [item.embedding for item in resp.data]

    def _create_cohere_embeddings(self, texts: list) -> list:
        """Cohere 格式"""
        import requests
        
        payload = {
            "texts": texts,
            "model": self._model,
            "input_type": "search_document",
            "embedding_types": ["float"]
        }
        
        # 如果配置了维度，传给 API
        if self._dim is not None:
            payload["output_dimension"] = self._dim
        
        response = requests.post(
            self._base_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json"
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"]["float"]

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


def get_scheduler(api_key=None, base_url=None, model=None, dim=None):
    """获取全局单例调度器"""
    global _global_scheduler
    if _global_scheduler is not None:
        return _global_scheduler

    with _global_lock:
        if _global_scheduler is not None:
            return _global_scheduler

        # 读取模式
        mode = os.getenv("EMBEDDING_MODE", "cloud").lower()

        if mode == "local":
            # 本地模式
            url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
            _api_key = ""
            _model = model or os.getenv("EMBEDDING_LOCAL_MODEL", "text-embedding-qwen3-embedding-4b")
            _dim_str = dim or os.getenv("EMBEDDING_LOCAL_DIM", "")
            logger.info(f"Embedding 本地模式: {url}")
        else:
            # 云端模式
            url = os.getenv("EMBEDDING_CLOUD_URL", "https://api.siliconflow.cn/v1/embeddings")
            _api_key = api_key or os.getenv("EMBEDDING_CLOUD_API_KEY", "")
            _model = model or os.getenv("EMBEDDING_CLOUD_MODEL", "BAAI/bge-m3")
            _dim_str = dim or os.getenv("EMBEDDING_CLOUD_DIM", "")
            logger.info(f"Embedding 云端模式: {url}")

        # 处理维度（可选）
        _dim = None
        if _dim_str and str(_dim_str).strip():
            try:
                _dim = int(_dim_str)
            except ValueError:
                logger.warning(f"无效的维度配置: {_dim_str}，将自动检测")

        # 从 URL 中提取 base_url（去掉 /embeddings 后缀）
        if url.endswith("/embeddings"):
            _base_url = url.rsplit("/embeddings", 1)[0]
        elif url.endswith("/v1/embeddings"):
            _base_url = url.rsplit("/embeddings", 1)[0]
        else:
            _base_url = url.rstrip("/")

        _global_scheduler = TaskScheduler(
            api_key=_api_key,
            base_url=_base_url,
            model=_model,
            dim=_dim,
        )

        return _global_scheduler
