# -*- coding: utf-8 -*-
"""
Ezy-RAG — MCP 服务器
通过 HTTP 暴露 search_knowledge_base 工具，供 opencode 或 MCP 客户端调用

用法: python -m servers.mcp
"""
import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import get_collection_name, get_retrieval_config
from config.pointer import get_active_collection
import chromadb
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# 配置
COLLECTION_NAME = get_collection_name()
RETRIEVAL_CONFIG = get_retrieval_config()
RETRIEVAL_K = RETRIEVAL_CONFIG["k"]
RETRIEVAL_FETCH_K = RETRIEVAL_CONFIG["fetch_k"]

# 日志
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

app = FastAPI(title="Ezy-RAG MCP Server", version="1.0.0")

# 全局实例（启动时初始化）
_emb_api = None
_rerank_api = None
_scheduler = None
_chroma_client = None
_chroma_collection = None
_active_collection_name = None
_env_mtime = 0.0
_env_file = ROOT / "config" / ".env"


def _init_services():
    """初始化所有服务"""
    global _emb_api, _rerank_api, _scheduler, _env_mtime
    from core.api import EmbeddingAPI, RerankAPI
    from core.scheduler import get_scheduler

    _emb_api = EmbeddingAPI()
    _rerank_api = RerankAPI()
    _rerank_api.set_k(RETRIEVAL_K)
    _scheduler = get_scheduler()
    _env_mtime = _env_file.stat().st_mtime if _env_file.exists() else 0.0


def _check_config_reload():
    """检查 .env 是否变化，如果变了就重新加载"""
    global _emb_api, _rerank_api, _scheduler, _env_mtime
    if not _env_file.exists():
        return
    current_mtime = _env_file.stat().st_mtime
    if current_mtime != _env_mtime:
        logger.info("检测到 .env 变化，重新加载配置...")
        from dotenv import load_dotenv
        load_dotenv(_env_file, override=True)
        from core.api import EmbeddingAPI, RerankAPI
        _emb_api = EmbeddingAPI()
        _rerank_api = RerankAPI()
        _rerank_api.set_k(RETRIEVAL_K)
        _env_mtime = current_mtime
        logger.info("配置重新加载完成")


async def _get_collection():
    """获取当前活跃集合"""
    global _chroma_client, _chroma_collection, _active_collection_name

    current = get_active_collection(COLLECTION_NAME)
    if _chroma_collection is None or current != _active_collection_name:
        if _chroma_client is None:
            _chroma_client = await chromadb.AsyncHttpClient(
                host=os.getenv("CHROMA_SERVER_HOST") or "127.0.0.1",
                port=int(os.getenv("CHROMA_SERVER_PORT") or "9898"),
            )
        try:
            _chroma_collection = await _chroma_client.get_collection(name=current)
        except Exception:
            logger.warning(f"集合 {current} 不存在，回退到 {COLLECTION_NAME}")
            _chroma_collection = await _chroma_client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
            )
            current = COLLECTION_NAME
        _active_collection_name = current
        logger.info(f"活跃集合: {current}")
    return _chroma_collection


async def search_async(query: str) -> str:
    """搜索知识库"""
    t0 = time.time()
    _check_config_reload()
    # 健康检查
    ok, err = _emb_api.health_check()
    if not ok:
        return f"[错误] Embedding 服务不可用: {err}\n请启动服务后重试。"

    try:
        # 向量化查询
        vectors = await _scheduler.embed_async([query], priority=0)
        query_vec = vectors[0]

        # 查询 ChromaDB
        collection = await _get_collection()
        do_rerank = _rerank_api.get_info()["enabled"]
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

        # Rerank
        rerank_executed = False
        rerank_scores = []

        if do_rerank and len(docs) > 1:
            try:
                scores, indices = await _rerank_api.rerank_async(query, docs)
                rerank_executed = True
                rerank_scores = scores
                ids = [ids[i] for i in indices]
                docs = [docs[i] for i in indices]
                metas = [metas[i] for i in indices]
                dists = [dists[i] for i in indices]
            except Exception as e:
                logger.warning(f"Rerank 失败: {e}")
                docs = docs[:RETRIEVAL_K]
                metas = metas[:RETRIEVAL_K]
                dists = dists[:RETRIEVAL_K]
                ids = ids[:RETRIEVAL_K]
        else:
            docs = docs[:RETRIEVAL_K]
            metas = metas[:RETRIEVAL_K]
            dists = dists[:RETRIEVAL_K]
            ids = ids[:RETRIEVAL_K]

        # 格式化结果
        if rerank_executed:
            score_str = ", ".join([f"{s:.2f}" for s in rerank_scores])
            parts = [f"找到 {len(docs)} 条相关文档（已重排）| 分数: {score_str}\n"]
        else:
            parts = [f"找到 {len(docs)} 条相关文档\n"]

        for i, (doc_id, doc_text, meta, dist) in enumerate(zip(ids, docs, metas, dists), 1):
            source = meta.get("source", "未知来源")
            fname = os.path.basename(source)
            similarity = max(0, 1 - dist)
            part = f"[{i}] 来源: {fname} | 相似度: {similarity:.2%}\n{doc_text.strip()}"
            parts.append(part)
        elapsed = time.time() - t0
        logger.info(f"search: '{query[:50]}' => {len(docs)} results, rerank={rerank_executed}, {elapsed:.2f}s")
        return "\n\n".join(parts)

    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return f"[错误] 搜索过程出错: {e}"


# ============================================================
#  MCP 协议端点
# ============================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    _check_config_reload()
    emb_ok, emb_err = _emb_api.health_check() if _emb_api else (False, "未初始化")
    rerank_ok, rerank_err = _rerank_api.health_check() if _rerank_api else (False, "未初始化")

    try:
        coll = await _get_collection()
        db_count = await coll.count()
    except Exception:
        db_count = 0

    return {
        "status": "ok",
        "version": "1.0.0",
        "embedding": {"online": emb_ok, "error": emb_err, "info": _emb_api.get_info() if _emb_api else {}},
        "rerank": {"online": rerank_ok, "error": rerank_err, "info": _rerank_api.get_info() if _rerank_api else {}},
        "chromadb": {
            "server": f"{os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}",
            "collection": get_active_collection(COLLECTION_NAME),
            "documents": db_count,
        },
    }


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP JSON-RPC 端点"""
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
                "serverInfo": {"name": "Ezy-RAG", "version": "1.0.0"},
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
    """启动 MCP 服务器"""
    _init_services()

    emb_info = _emb_api.get_info()
    rerank_info = _rerank_api.get_info()

    logger.info("=" * 50)
    logger.info("Ezy-RAG MCP Server V1.0.0 启动中...")
    logger.info(f"Embedding: {emb_info['mode']} ({emb_info['model']}, {emb_info['dim']}维)")
    logger.info(f"Rerank: {'启用' if rerank_info['enabled'] else '未启用'} ({rerank_info['mode']})")
    logger.info(f"ChromaDB: {os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}")
    logger.info(f"监听: http://{os.getenv('MCP_SERVER_HOST', '127.0.0.1')}:{os.getenv('MCP_SERVER_PORT', '9766')}")
    logger.info("=" * 50)

    uvicorn.run(
        app,
        host=os.getenv("MCP_SERVER_HOST") or "127.0.0.1",
        port=int(os.getenv("MCP_SERVER_PORT") or "9766"),
        log_level="info",
    )


if __name__ == "__main__":
    main()
