# -*- coding: utf-8 -*-
"""
Ezy-RAG V1.0.0 — Reranker 调用工具
支持两种 API 格式：
  1. 本地格式：POST /rerank → {"scores": [...]}
  2. OpenAI 兼容格式（Jina/Cohere 等）：POST /rerank → {"results": [{"relevance_score": ...}]}
"""
import os
import httpx
import logging

logger = logging.getLogger("Ezy-RAG-Reranker")


def _parse_rerank_response(data: dict) -> list[float]:
    """解析 rerank 响应，自动适配两种格式"""
    # 格式 1：本地格式 {"scores": [0.87, 0.32, ...]}
    if "scores" in data and isinstance(data["scores"], list):
        return [float(s) for s in data["scores"]]

    # 格式 2：OpenAI/Jina 兼容格式 {"results": [{"index": 0, "relevance_score": 0.95}, ...]}
    if "results" in data and isinstance(data["results"], list):
        results = data["results"]
        # 按 index 排序后提取 relevance_score
        sorted_results = sorted(results, key=lambda x: x.get("index", 0))
        return [float(r.get("relevance_score", r.get("score", 0))) for r in sorted_results]

    # 格式 3：Cohere 格式 {"results": [{"relevance_score": 0.95}, ...]}（无 index，按顺序）
    if "results" in data and isinstance(data["results"], list) and len(data["results"]) > 0:
        if "relevance_score" in data["results"][0]:
            return [float(r["relevance_score"]) for r in data["results"]]

    raise ValueError(f"无法解析 rerank 响应格式: {list(data.keys())}")


async def rerank_async(query: str, documents: list[str]) -> list[float]:
    """异步调用重排 API，返回分数列表"""
    url = os.getenv("RERANK_API_URL", "http://127.0.0.1:5001").rstrip("/")
    api_key = os.getenv("RERANK_API_KEY", "")
    model = os.getenv("RERANK_MODEL", "")

    # 拼接端点
    if not url.endswith("/rerank"):
        url = url + "/rerank"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # 构建请求体
    payload = {"query": query, "documents": documents}
    if model:
        payload["model"] = model

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return _parse_rerank_response(r.json())


def rerank_sync(query: str, documents: list[str]) -> list[float]:
    """同步调用重排 API，返回分数列表"""
    url = os.getenv("RERANK_API_URL", "http://127.0.0.1:5001").rstrip("/")
    api_key = os.getenv("RERANK_API_KEY", "")
    model = os.getenv("RERANK_MODEL", "")

    if not url.endswith("/rerank"):
        url = url + "/rerank"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {"query": query, "documents": documents}
    if model:
        payload["model"] = model

    with httpx.Client(timeout=30) as client:
        r = client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return _parse_rerank_response(r.json())
