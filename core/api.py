# -*- coding: utf-8 -*-
"""
Ezy-RAG — 统一 API 适配器
管理 Embedding 和 Rerank 的 local/cloud 模式，统一对外暴露接口

用法:
  from core.api import EmbeddingAPI, RerankAPI

  emb = EmbeddingAPI()
  vectors = emb.embed(["文本1", "文本2"])
  ok, err = emb.health_check()

  rerank = RerankAPI()
  scores, indices = rerank.rerank("查询", ["文档1", "文档2"])
"""
import os
import sys
import time
import asyncio
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 日志配置 — 统一写入 embedding.log 和 rerank.log
LOG_DIR = ROOT / "runtime" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

emb_logger = logging.getLogger("EmbeddingAPI")
emb_handler = logging.FileHandler(LOG_DIR / "embedding.log", encoding="utf-8")
emb_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
emb_logger.addHandler(emb_handler)
emb_logger.setLevel(logging.INFO)

rerank_logger = logging.getLogger("RerankAPI")
rerank_handler = logging.FileHandler(LOG_DIR / "rerank.log", encoding="utf-8")
rerank_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
rerank_logger.addHandler(rerank_handler)
rerank_logger.setLevel(logging.INFO)


def _detect_provider(url: str) -> str:
    """根据 URL 自动检测提供商"""
    if "cohere.com" in url:
        return "cohere"
    elif "jina.ai" in url:
        return "jina"
    else:
        return "openai"


def _normalize_embedding_url(url: str) -> tuple:
    """
    标准化 Embedding URL
    返回: (base_url, full_url)
    """
    if url.endswith("/v1/embeddings"):
        full_url = url
        base_url = url.rsplit("/embeddings", 1)[0]
    elif url.endswith("/embeddings"):
        full_url = url
        base_url = url.rsplit("/embeddings", 1)[0]
    elif url.endswith("/v1"):
        full_url = url + "/embeddings"
        base_url = url
    else:
        full_url = url.rstrip("/") + "/v1/embeddings"
        base_url = url.rstrip("/") + "/v1"
    return base_url, full_url


# ============================================================
#  EmbeddingAPI
# ============================================================

class EmbeddingAPI:
    """统一的 Embedding API 适配器"""

    def __init__(self):
        mode = os.getenv("EMBEDDING_MODE", "cloud").lower()

        if mode == "local":
            url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
            self._api_key = "local"
            self._model = os.getenv("EMBEDDING_LOCAL_MODEL", "text-embedding-qwen3-embedding-4b")
            dim_str = os.getenv("EMBEDDING_LOCAL_DIM", "")
            self._mode = "local"
        else:
            url = os.getenv("EMBEDDING_CLOUD_URL", "https://api.siliconflow.cn/v1/embeddings")
            self._api_key = os.getenv("EMBEDDING_CLOUD_API_KEY", "")
            self._model = os.getenv("EMBEDDING_CLOUD_MODEL", "BAAI/bge-m3")
            dim_str = os.getenv("EMBEDDING_CLOUD_DIM", "")
            self._mode = "cloud"

        self._dim = None
        if dim_str and dim_str.strip():
            try:
                self._dim = int(dim_str)
            except ValueError:
                emb_logger.warning(f"无效的维度配置: {dim_str}，将自动检测")

        self._provider = _detect_provider(url)
        self._base_url, self._full_url = _normalize_embedding_url(url)

        # 初始化客户端
        if self._provider == "openai":
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url, timeout=30)
        else:
            self._client = None

        emb_logger.info(f"init: mode={self._mode}, model={self._model}, base_url={self._base_url}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """同步向量化"""
        t0 = time.time()
        if self._provider == "cohere":
            result = self._embed_cohere(texts)
        else:
            result = self._embed_openai(texts)
        elapsed = time.time() - t0
        total_chars = sum(len(t) for t in texts)
        dim = len(result[0]) if result else 0
        emb_logger.info(f"embed: {len(texts)} texts, {total_chars} chars, dim={dim}, {elapsed:.2f}s")
        return result

    async def embed_async(self, texts: list[str]) -> list[list[float]]:
        """异步向量化"""
        return await asyncio.to_thread(self.embed, texts)

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """OpenAI 兼容格式"""
        kwargs = {"model": self._model, "input": texts}
        # 只有用户显式配置了维度才传 dimensions（SiliconFlow 不支持自动检测的维度）
        explicit_dim = os.getenv("EMBEDDING_CLOUD_DIM", "").strip()
        if explicit_dim:
            kwargs["dimensions"] = int(explicit_dim)
        resp = self._client.embeddings.create(**kwargs)
        vectors = [item.embedding for item in resp.data]
        # 自动检测维度
        if self._dim is None and vectors:
            self._dim = len(vectors[0])
            emb_logger.info(f"自动检测 Embedding 维度: {self._dim}")
        return vectors

    def _embed_cohere(self, texts: list[str]) -> list[list[float]]:
        """Cohere 格式"""
        import requests as req
        payload = {
            "texts": texts,
            "model": self._model,
            "input_type": "search_document",
            "embedding_types": ["float"],
        }
        if self._dim is not None:
            payload["output_dimension"] = self._dim
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        r = req.post(self._full_url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()["embeddings"]["float"]

    def health_check(self) -> tuple[bool, str]:
        """健康检查"""
        try:
            import httpx
            headers = {}
            if self._api_key and self._api_key != "local":
                headers["Authorization"] = f"Bearer {self._api_key}"
            with httpx.Client(timeout=3) as c:
                r = c.get(f"{self._base_url}/models", headers=headers)
                if r.status_code == 200:
                    return True, ""
                return False, f"状态码 {r.status_code}"
        except Exception as e:
            return False, str(e)

    def get_info(self) -> dict:
        """返回配置信息"""
        return {
            "mode": self._mode,
            "provider": self._provider,
            "model": self._model,
            "dim": self._dim,
            "base_url": self._base_url,
        }


# ============================================================
#  RerankAPI
# ============================================================

class RerankAPI:
    """统一的 Rerank API 适配器（本地/云端接口一致）"""

    def __init__(self):
        self._enabled = os.getenv("RERANK_ENABLED", "true").lower() == "true"
        self._mode = os.getenv("RERANK_MODE", "cloud").lower()

        # 读取 URL 和认证信息（本地和云端的区别只是地址和 key）
        if self._mode == "cloud":
            self._url = os.getenv("RERANK_CLOUD_URL", "https://api.siliconflow.cn/v1/rerank").rstrip("/")
            self._api_key = os.getenv("RERANK_CLOUD_API_KEY", "")
            self._model = os.getenv("RERANK_CLOUD_MODEL", "BAAI/bge-reranker-v2-m3")
        else:
            self._url = os.getenv("RERANK_LOCAL_URL", "http://127.0.0.1:5001").rstrip("/")
            self._api_key = ""
            self._model = "local"

        self._k = 5

        rerank_logger.info(f"init: enabled={self._enabled}, mode={self._mode}, url={self._url}")

    def set_k(self, k: int):
        """设置 top-k"""
        self._k = k

    def rerank(self, query: str, documents: list[str]) -> tuple[list[float], list[int]]:
        """
        同步重排 — 本地和云端统一调用方式
        返回: (scores, indices)
        """
        if not self._enabled:
            return [], list(range(len(documents)))

        t0 = time.time()
        import httpx

        # 拼接 URL（对齐云端格式 /v1/rerank）
        url = self._url
        if not url.endswith("/rerank"):
            url = url + "/rerank"

        # 统一请求格式（本地 server 和云端 API 接受相同的格式）
        payload = {
            "model": self._model,
            "query": query,
            "documents": documents,
            "top_n": self._k,
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key and self._api_key != "local":
            headers["Authorization"] = f"Bearer {self._api_key}"

        with httpx.Client(timeout=30) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        # 统一响应解析（本地 server 和云端 API 返回相同的格式）
        if "results" in data:
            scores = [item["relevance_score"] for item in data["results"]]
            indices = [item["index"] for item in data["results"]]
        elif "scores" in data:
            # 兼容旧格�?
            all_scores = data["scores"]
            indexed_scores = sorted(enumerate(all_scores), key=lambda x: x[1], reverse=True)
            top_k = indexed_scores[:self._k]
            indices = [i for i, _ in top_k]
            scores = [s for _, s in top_k]
        else:
            raise ValueError(f"未知的 rerank 响应格式: {list(data.keys())}")

        elapsed = time.time() - t0
        top_scores = [f"{s:.2f}" for s in scores[:3]]
        rerank_logger.info(f"rerank: {len(documents)} docs, top_scores={top_scores}, {elapsed:.2f}s")
        return scores, indices

    async def rerank_async(self, query: str, documents: list[str]) -> tuple[list[float], list[int]]:
        """异步重排"""
        return await asyncio.to_thread(self.rerank, query, documents)

    def health_check(self) -> tuple[bool, str]:
        """健康检查"""
        if not self._enabled:
            return True, "未启用"
        try:
            import httpx
            headers = {}
            if self._api_key and self._api_key != "local":
                headers["Authorization"] = f"Bearer {self._api_key}"
            with httpx.Client(timeout=3) as c:
                r = c.get(f"{self._url}/health", headers=headers)
                if r.status_code == 200:
                    return True, ""
                # 云端模式 404 也算在线（云端没有 /health 端点）
                if self._mode == "cloud":
                    return True, ""
                return False, f"状态码 {r.status_code}"
        except Exception as e:
            return False, str(e)

    def get_info(self) -> dict:
        """返回配置信息"""
        return {
            "enabled": self._enabled,
            "mode": self._mode,
            "model": self._model,
            "url": self._url,
        }
