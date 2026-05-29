# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 — MCP 服务器 (Client-Server 模式)
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
from core.scheduler import get_scheduler

# 从配置文件读取
COLLECTION_NAME = get_collection_name()
RETRIEVAL_CONFIG = get_retrieval_config()
RETRIEVAL_K = RETRIEVAL_CONFIG["k"]
RETRIEVAL_FETCH_K = RETRIEVAL_CONFIG["fetch_k"]

# 创建日志目录
LOG_DIR = ROOT / "runtime" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(
            str(LOG_DIR / "mcp_server.log"),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    ],
)
logger = logging.getLogger("Ezy-RAG-MCP")

app = FastAPI(title="Ezy-RAG MCP Server", version="0.0.17")

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
    # 根据模式读取对应的 URL
    mode = os.getenv("EMBEDDING_MODE", "cloud").lower()
    if mode == "local":
        url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
        api_key = ""
    else:
        url = os.getenv("EMBEDDING_CLOUD_URL", "https://api.siliconflow.cn/v1/embeddings")
        api_key = os.getenv("EMBEDDING_CLOUD_API_KEY", "")
    
    base_url = url.rsplit("/v1/", 1)[0]
    
    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{base_url}/v1/models", headers=headers)
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
    """异步向量化——通过调度器，VIP 优先级"""
    scheduler = get_scheduler()
    vectors = await scheduler.embed_async([query], priority=0)
    return vectors[0]


async def rerank_async(query: str, documents: list[str]) -> tuple[list[float], list[int]]:
    """调用重排 API，返回 (scores, indices)
    - scores: 分数列表
    - indices: 对应的原始索引列表
    """
    mode = os.getenv("RERANK_MODE", "local").lower()

    if mode == "cloud":
        # 云端模式
        return await _rerank_cloud(query, documents)
    else:
        # 本地模式
        return await _rerank_local(query, documents)


async def _rerank_local(query: str, documents: list[str]) -> tuple[list[float], list[int]]:
    """本地 Rerank 服务
    返回: (scores, indices) - 分数和对应的原始索引
    """
    url = os.getenv("RERANK_LOCAL_URL", "http://127.0.0.1:5001").rstrip("/") + "/rerank"
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json={"query": query, "documents": documents}, headers=headers)
        r.raise_for_status()
        all_scores = r.json()["scores"]
        
        # 按分数排序，取 top-k
        indexed_scores = list(enumerate(all_scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        
        top_k = indexed_scores[:RETRIEVAL_K]
        indices = [i for i, _ in top_k]
        scores = [s for _, s in top_k]
        
        logger.info(f"本地 Rerank 返回 {len(scores)} 个结果，top-k={RETRIEVAL_K}")
        return scores, indices


async def _rerank_cloud(query: str, documents: list[str]) -> tuple[list[float], list[int]]:
    """云端 Rerank API（根据 URL 自动适配格式）
    返回: (scores, indices) - 分数和对应的原始索引
    """
    url = os.getenv("RERANK_CLOUD_URL", "https://api.cohere.com/v1/rerank").rstrip("/")
    api_key = os.getenv("RERANK_CLOUD_API_KEY", "")
    model = os.getenv("RERANK_CLOUD_MODEL", "rerank-multilingual-v3.0")

    payload = {
        "model": model,
        "query": query,
        "documents": documents,
        "top_n": RETRIEVAL_K,
        "return_documents": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    # 根据 URL 判断格式
    if "cohere.com" in url:
        # Cohere 格式：不传 return_documents
        payload.pop("return_documents", None)
    
    if not url.endswith("/rerank"):
        url = url + "/rerank"
    
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        
        # 标准格式：Cohere/Jina/SiliconFlow
        if "results" in data:
            # API 返回的结果已经按 relevance_score 排序
            scores = [item["relevance_score"] for item in data["results"]]
            indices = [item["index"] for item in data["results"]]
            logger.info(f"云端 Rerank 返回 {len(scores)} 个结果，top_n={RETRIEVAL_K}")
            return scores, indices
        # 非标准格式
        elif "scores" in data:
            all_scores = data["scores"]
            # 按分数排序，取 top-k
            indexed_scores = list(enumerate(all_scores))
            indexed_scores.sort(key=lambda x: x[1], reverse=True)
            top_k = indexed_scores[:RETRIEVAL_K]
            indices = [i for i, _ in top_k]
            scores = [s for _, s in top_k]
            return scores, indices
        else:
            raise ValueError(f"未知的 rerank 响应格式: {list(data.keys())}")


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

        # 重排状态跟踪
        rerank_executed = False
        rerank_scores = []

        if do_rerank and len(docs) > 1:
            try:
                scores, indices = await rerank_async(query, docs)
                rerank_executed = True
                rerank_scores = scores
                
                # 使用 indices 重新排列文档
                ids = [ids[i] for i in indices]
                docs = [docs[i] for i in indices]
                metas = [metas[i] for i in indices]
                dists = [dists[i] for i in indices]
                
                logger.info(f"重排完成，返回 {len(scores)} 条，分数: {rerank_scores}")
            except Exception as e:
                logger.warning(f"重排失败: {e}")
                # 重排失败时，取前 RETRIEVAL_K 个
                docs = docs[:RETRIEVAL_K]
                metas = metas[:RETRIEVAL_K]
                dists = dists[:RETRIEVAL_K]
                ids = ids[:RETRIEVAL_K]
        else:
            # 不重排时，取前 RETRIEVAL_K 个
            docs = docs[:RETRIEVAL_K]
            metas = metas[:RETRIEVAL_K]
            dists = dists[:RETRIEVAL_K]
            ids = ids[:RETRIEVAL_K]

        # 显示搜索结果
        if rerank_executed:
            score_str = ", ".join([f"{s:.2f}" for s in rerank_scores])
            parts = [f"找到 {len(docs)} 条相关文档（✓ 已重排 | 分数: {score_str}）:\n"]
        elif do_rerank:
            parts = [f"找到 {len(docs)} 条相关文档（⚠ 重排跳过，文档数不足）:\n"]
        else:
            parts = [f"找到 {len(docs)} 条相关文档:\n"]
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
                "serverInfo": {"name": "Ezy-RAG", "version": "0.0.17"},
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
    # 读取配置
    embedding_mode = os.getenv("EMBEDDING_MODE", "cloud").lower()
    if embedding_mode == "local":
        embedding_model = os.getenv("EMBEDDING_LOCAL_MODEL", "text-embedding-qwen3-embedding-4b")
        embedding_dim = os.getenv("EMBEDDING_LOCAL_DIM", "2560")
    else:
        embedding_model = os.getenv("EMBEDDING_CLOUD_MODEL", "BAAI/bge-m3")
        embedding_dim = os.getenv("EMBEDDING_CLOUD_DIM", "1024")
    
    rerank_enabled = os.getenv("RERANK_ENABLED", "false").lower() == "true"
    rerank_mode = os.getenv("RERANK_MODE", "local").lower()
    if rerank_enabled:
        if rerank_mode == "local":
            rerank_model = "本地模型"
        else:
            rerank_model = os.getenv("RERANK_CLOUD_MODEL", "rerank-multilingual-v3.0")
    else:
        rerank_model = "未启用"
    
    logger.info("=" * 50)
    logger.info("Ezy-RAG MCP Server V0.0.17 启动中...")
    logger.info(f"Embedding: {'本地' if embedding_mode == 'local' else '云端'} ({embedding_model}, {embedding_dim}维)")
    logger.info(f"Rerank: {'未启用' if not rerank_enabled else ('本地' if rerank_mode == 'local' else '云端')} ({rerank_model})")
    logger.info(f"ChromaDB: {os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}")
    logger.info(f"监听: http://{os.getenv('MCP_SERVER_HOST', '127.0.0.1')}:{os.getenv('MCP_SERVER_PORT', '9766')}")
    logger.info("=" * 50)

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
