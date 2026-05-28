# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.14 — MCP 服务器 (Client-Server 模式)
通过 HTTP 暴露 search_knowledge_base 工具，供 opencode 等 MCP 客户端调用
使用 AsyncHttpClient 连接 ChromaDB Server 实现异步查询

用法: python -m servers.mcp
"""
import os
import sys
import json
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import get_collection_name, get_retrieval_config
import chromadb
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

import time as _time
from core.embedder import get_lm_proxy

# 从配置文件读取
COLLECTION_NAME = get_collection_name()
RETRIEVAL_CONFIG = get_retrieval_config()
RETRIEVAL_K = RETRIEVAL_CONFIG["k"]
RETRIEVAL_FETCH_K = RETRIEVAL_CONFIG["fetch_k"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(
            str(ROOT / "runtime" / "logs" / "mcp_server.log"),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    ],
)
logger = logging.getLogger("Ezy-RAG-MCP")

app = FastAPI(title="Ezy-RAG MCP Server", version="0.0.14")

_oai_client = None
_chroma_client = None
_chroma_collection = None

POINTER_FILE = ROOT / "runtime" / "state" / "collection_pointer.json"
_active_collection_name = None


def get_active_collection_name() -> str:
    """读取指针文件中的活跃集合名"""
    if POINTER_FILE.exists():
        with open(POINTER_FILE, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            return data.get(COLLECTION_NAME, COLLECTION_NAME)
    return COLLECTION_NAME


async def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = await chromadb.AsyncHttpClient(
            host=os.getenv("CHROMA_SERVER_HOST") or "127.0.0.1",
            port=int(os.getenv("CHROMA_SERVER_PORT") or "9898"),
        )
    return _chroma_client


async def get_collection_async():
    global _chroma_collection, _active_collection_name
    current = get_active_collection_name()
    if _chroma_collection is None or current != _active_collection_name:
        client = await get_chroma_client()
        try:
            _chroma_collection = await client.get_collection(name=current)
        except Exception:
            logger.warning(f"指针集合 {current} 不存在，回退到 {COLLECTION_NAME}")
            _chroma_collection = await client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
            )
            current = COLLECTION_NAME
        _active_collection_name = current
        logger.info(f"活跃集合: {current}")
    return _chroma_collection


async def check_lm_studio_health() -> tuple[bool, str]:
    base_url = os.getenv("EMBEDDING_API_URL", "http://127.0.0.1:5000/v1/embeddings").rsplit("/v1/", 1)[0]
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{base_url}/v1/models", headers={
                "Authorization": f"Bearer {os.getenv('EMBEDDING_API_KEY', '')}"
            })
            if r.status_code == 200:
                return True, ""
            return False, f"Embedding 服务返回状态码 {r.status_code}"
    except Exception as e:
        return False, f"Embedding 服务未启动或不可访问: {e}"


_health_cache = {"ok": False, "err": "", "last_check": 0.0}
_health_lock = asyncio.Lock()


async def check_lm_studio_cached():
    now = _time.time()
    if now - _health_cache["last_check"] < 30:
        return _health_cache["ok"], _health_cache["err"]
    async with _health_lock:
        if now - _health_cache["last_check"] < 30:
            return _health_cache["ok"], _health_cache["err"]
        _health_cache["ok"], _health_cache["err"] = await check_lm_studio_health()
        _health_cache["last_check"] = _time.time()
        return _health_cache["ok"], _health_cache["err"]


async def embed_query_async(query: str) -> list[float]:
    """异步向量化——通过 Embedding 代理，VIP 优先级"""
    proxy = get_lm_proxy()
    vectors = await proxy.embed_async([query], priority=0)
    return vectors[0]


async def rerank_async(query: str, documents: list[str]) -> list[float]:
    """调用重排 API，返回分数列表"""
    mode = os.getenv("RERANK_MODE", "local").lower()

    if mode == "cloud":
        # 云端模式：调用 Cohere/Jina 等云端 Rerank API
        return await _rerank_cloud(query, documents)
    else:
        # 本地模式：调用本地 CrossEncoder 服务
        return await _rerank_local(query, documents)


async def _rerank_local(query: str, documents: list[str]) -> list[float]:
    """本地 Rerank 服务"""
    url = os.getenv("RERANK_LOCAL_URL", "http://127.0.0.1:5001").rstrip("/") + "/rerank"
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={"query": query, "documents": documents}, headers=headers)
        r.raise_for_status()
        return r.json()["scores"]


async def _rerank_cloud(query: str, documents: list[str]) -> list[float]:
    """云端 Rerank API（Cohere/Jina 等）"""
    provider = os.getenv("RERANK_CLOUD_PROVIDER", "cohere").lower()
    api_key = os.getenv("RERANK_CLOUD_API_KEY", "")
    model = os.getenv("RERANK_CLOUD_MODEL", "rerank-multilingual-v3.0")

    if provider == "cohere":
        url = "https://api.cohere.com/v1/rerank"
        payload = {
            "query": query,
            "documents": documents,
            "model": model,
            "top_n": len(documents),
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            # Cohere 返回 {"results": [{"index": 0, "relevance_score": 0.9}, ...]}
            scores = [0.0] * len(documents)
            for item in data["results"]:
                scores[item["index"]] = item["relevance_score"]
            return scores

    elif provider == "jina":
        url = "https://api.jina.ai/v1/rerank"
        payload = {
            "query": query,
            "documents": documents,
            "model": model,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            # Jina 返回 {"results": [{"index": 0, "relevance_score": 0.9}, ...]}
            scores = [0.0] * len(documents)
            for item in data["results"]:
                scores[item["index"]] = item["relevance_score"]
            return scores

    else:
        # 自定义云端 API（兼容本地格式）
        url = os.getenv("RERANK_CLOUD_URL", "").rstrip("/") + "/rerank"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, json={"query": query, "documents": documents}, headers=headers)
            r.raise_for_status()
            return r.json()["scores"]


async def search_async(query: str) -> str:
    ok, err = await check_lm_studio_cached()
    if not ok:
        return f"[错误] {err}\n请启动 Embedding 服务后重试。"

    try:
        query_vec = await embed_query_async(query)
        collection = await get_collection_async()

        do_rerank = os.getenv("RERANK_ENABLED", "false").lower() == "true"
        fetch_k = RETRIEVAL_FETCH_K if do_rerank else RETRIEVAL_K

        results = await collection.query(
            query_embeddings=[query_vec],
            n_results=fetch_k,
            include=["documents", "metadatas", "distances"],
        )

        if not results or not results["ids"] or not results["ids"][0]:
            return "知识库中未找到相关内容。"

        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        if do_rerank and len(docs) > RETRIEVAL_K:
            try:
                scores = await rerank_async(query, docs)
                ranked = sorted(zip(range(len(docs)), scores), key=lambda x: x[1], reverse=True)
                top_indices = [i for i, _ in ranked[:RETRIEVAL_K]]
                ids = [ids[i] for i in top_indices]
                docs = [docs[i] for i in top_indices]
                metas = [metas[i] for i in top_indices]
                dists = [dists[i] for i in top_indices]
                logger.info(f"重排完成，取 top-{RETRIEVAL_K}")
            except Exception as e:
                logger.warning(f"重排失败，使用原始结果: {e}")
                docs = docs[:RETRIEVAL_K]
                metas = metas[:RETRIEVAL_K]
                dists = dists[:RETRIEVAL_K]
                ids = ids[:RETRIEVAL_K]

        parts = [f"找到 {len(docs)} 条相关文档:\n"]
        if do_rerank:
            parts = [f"找到 {len(docs)} 条相关文档（已通过重排优化）:\n"]
        for i, (doc_id, doc_text, meta, dist) in enumerate(zip(
            ids, docs, metas, dists
        ), 1):
            source = meta.get("source", "未知来源")
            fname = os.path.basename(source)
            similarity = max(0, 1 - dist)
            part = f"[{i}] 来源: {fname} | 相似度: {similarity:.2%}\n{doc_text.strip()}"
            parts.append(part)
        return "\n\n".join(parts)

    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return f"[错误] 搜索过程出错: {e}"


# ============================================================
# MCP 协议端点
# ============================================================

@app.get("/health")
async def health_check():
    ok, err = await check_lm_studio_health()
    try:
        coll = await get_collection_async()
        db_count = await coll.count()
    except Exception:
        db_count = 0
    return {
        "status": "ok",
        "embedding_service": {"online": ok, "error": err},
        "chromadb": {
            "server": f"{os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}",
            "collection": get_active_collection_name(),
            "documents": db_count,
        },
    }


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    method = body.get("method", "")
    req_id = body.get("id", 0)

    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [{
                    "name": "search_knowledge_base",
                    "description": "【优先调用】遇到以下情况应优先使用此工具搜索本地知识库：① 用户询问的信息可能属于个人私有数据或特定工作环境；② 问题涉及你训练数据中可能不存在的特定人物、地点或事件；③ 你对答案不确定，需要从本地文档中查找事实依据。调用此工具来检索本地知识库中的文档信息。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "要搜索的问题或关键词，使用中文或英文均可。"
                            }
                        },
                        "required": ["query"]
                    }
                }]
            }
        })

    elif method == "tools/call":
        tool_name = body.get("params", {}).get("name", "")
        arguments = body.get("params", {}).get("arguments", {})

        if tool_name == "search_knowledge_base":
            query_text = arguments.get("query", "")
            if not query_text:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": "缺少 query 参数"}
                }, status_code=400)
            logger.info(f"搜索: {query_text[:100]}")
            result_text = await search_async(query_text)
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}]
                }
            })

        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"未知工具: {tool_name}"}
        }, status_code=404)

    elif method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "Ezy-RAG", "version": "0.0.14"},
                "capabilities": {"tools": {}}
            }
        })

    elif method == "notifications/initialized":
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {}})

    else:
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"未知方法: {method}"}
        }, status_code=404)


def main():
    logger.info("Ezy-RAG MCP Server V0.0.14 启动中...")
    logger.info(f"Embedding 服务: {os.getenv('EMBEDDING_API_URL', 'http://127.0.0.1:5000/v1/embeddings')}")
    logger.info(f"ChromaDB Server: {os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}")
    logger.info(f"监听: http://{os.getenv('MCP_SERVER_HOST', '127.0.0.1')}:{os.getenv('MCP_SERVER_PORT', '9766')}")

    async def startup_checks():
        ok, err = await check_lm_studio_health()
        if ok:
            logger.info("Embedding 服务: 在线")
        else:
            logger.warning(f"Embedding 服务: {err}")

        try:
            client = await get_chroma_client()
            await client.heartbeat()
            logger.info("ChromaDB Server: 在线")
        except Exception as e:
            logger.warning(f"ChromaDB Server 不可用: {e}")

    asyncio.run(startup_checks())

    uvicorn.run(
        app,
        host=os.getenv("MCP_SERVER_HOST") or "127.0.0.1",
        port=int(os.getenv("MCP_SERVER_PORT") or "9766"),
        log_level="info",
    )


if __name__ == "__main__":
    main()
