# -*- coding: utf-8 -*-
"""
Ezy-RAG — CLI 公共逻辑
提供服务状态检测、数据库连接、文档管理等共享功能
"""
import os
import sys
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")


def check_port(host: str, port: int) -> bool:
    """检查端口是否可连接"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_service_status() -> dict:
    """获取所有服务状态（调用 core 模块）"""
    from core.api import EmbeddingAPI, RerankAPI
    
    chroma_host = os.getenv("CHROMA_SERVER_HOST", "127.0.0.1")
    chroma_port = int(os.getenv("CHROMA_SERVER_PORT", "9898"))
    mcp_host = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    mcp_port = int(os.getenv("MCP_SERVER_PORT", "9766"))
    
    # ChromaDB 状态
    chroma_online = check_port(chroma_host, chroma_port)
    
    # MCP 状态
    mcp_online = check_port(mcp_host, mcp_port)
    
    # Embedding 状态
    try:
        emb_api = EmbeddingAPI()
        emb_info = emb_api.get_info()
        emb_ok, emb_err = emb_api.health_check()
        embedding = {
            "online": emb_ok,
            "mode": emb_info["mode"],
            "model": emb_info["model"],
            "info": f"{emb_info['mode']} ({emb_info['model']})"
        }
    except Exception as e:
        embedding = {"online": False, "mode": "unknown", "model": "", "info": f"错误: {e}"}
    
    # Rerank 状态
    try:
        rerank_api = RerankAPI()
        rerank_info = rerank_api.get_info()
        rerank_enabled = rerank_info["enabled"]
        if rerank_enabled:
            rerank_ok, rerank_err = rerank_api.health_check()
            rerank = {
                "online": rerank_ok,
                "enabled": True,
                "mode": rerank_info["mode"],
                "model": rerank_info["model"],
                "info": f"{rerank_info['mode']} ({rerank_info['model']})"
            }
        else:
            rerank = {"online": False, "enabled": False, "mode": "disabled", "model": "", "info": "未启用", "skip": True}
    except Exception as e:
        rerank = {"online": False, "enabled": False, "mode": "unknown", "model": "", "info": f"错误: {e}"}
    
    return {
        "chromadb": {"online": chroma_online, "host": chroma_host, "port": chroma_port, "info": f":{chroma_port}"},
        "embedding": embedding,
        "rerank": rerank,
        "mcp": {"online": mcp_online, "host": mcp_host, "port": mcp_port, "info": f":{mcp_port}"},
    }


def connect_chroma():
    """连接 ChromaDB，返回 (client, db)"""
    import chromadb
    from core.api import EmbeddingAPI
    from core.database import DocumentDatabase
    from config.settings import get_collection_name
    from config.pointer import get_active_collection, set_active_collection
    
    host = os.getenv("CHROMA_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("CHROMA_SERVER_PORT", "9898"))
    
    client = chromadb.HttpClient(host=host, port=port)
    client.heartbeat()
    
    emb_api = EmbeddingAPI()
    collection_name = get_active_collection(get_collection_name())
    
    try:
        collection = client.get_collection(name=collection_name)
        collection.count()  # 验证完整性
    except Exception:
        from config.settings import get_chroma_hnsw_metadata
        metadata = get_chroma_hnsw_metadata()
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata=metadata
        )
        set_active_collection(get_collection_name(), collection_name)
    
    db = DocumentDatabase(collection, emb_api, client, collection_name)
    return client, db


def get_local_documents(source: str = "all") -> list:
    """获取本地文档列表
    
    Args:
        source: "all" | "docs" | "web"
        
    Returns:
        文档路径列表
    """
    from core.document import SUPPORTED_EXT
    
    dirs = []
    if source in ("docs", "all"):
        dirs.append(ROOT / "data" / "docs")
    if source in ("web", "all"):
        dirs.append(ROOT / "data" / "web")
    
    documents = []
    seen = set()
    for docs_dir in dirs:
        if not docs_dir.exists():
            continue
        for ext in SUPPORTED_EXT:
            for f in docs_dir.glob(f"**/*{ext}"):
                if f.is_file():
                    key = str(f.resolve())
                    if key not in seen:
                        seen.add(key)
                        documents.append(str(f))
    return sorted(documents)


def get_database_stats() -> dict:
    """获取数据库统计信息"""
    from core.document import SUPPORTED_EXT
    
    stats = {
        "docs_count": 0,
        "web_count": 0,
        "vector_docs": 0,
        "chunks": 0,
        "collection": ""
    }
    
    # 统计本地文档
    docs_dir = ROOT / "data" / "docs"
    if docs_dir.exists():
        stats["docs_count"] = sum(1 for ext in SUPPORTED_EXT 
                                  for f in docs_dir.glob(f"**/*{ext}") 
                                  if f.is_file())
    
    # 统计网页文档
    web_dir = ROOT / "data" / "web"
    if web_dir.exists():
        stats["web_count"] = sum(1 for f in web_dir.glob("*.txt") if f.is_file())
    
    # 向量库信息
    try:
        _, db = connect_chroma()
        vector_docs = db.list_documents()
        stats["vector_docs"] = len(vector_docs)
        stats["chunks"] = db.count()
        stats["collection"] = db.collection_name
    except Exception:
        pass
    
    return stats


def get_document_list(source: str = "all") -> list:
    """获取文档列表（合并本地和向量库信息）
    
    Args:
        source: "all" | "docs" | "web"
        
    Returns:
        文档信息列表
    """
    local_docs = get_local_documents(source)
    
    vector_docs = []
    try:
        _, db = connect_chroma()
        vector_docs = db.list_documents()
    except Exception:
        pass
    
    local_paths = {d for d in local_docs}
    vector_map = {d["source"]: d for d in vector_docs}
    
    result = []
    for doc_path in local_docs:
        doc_name = Path(doc_path).name
        # 判断来源目录
        source_dir = "web" if "\\data\\web\\" in doc_path or "/data/web/" in doc_path else "docs"
        
        if doc_path in vector_map:
            v = vector_map[doc_path]
            result.append({
                "path": doc_path,
                "name": doc_name,
                "source": source_dir,
                "status": "imported",
                "chunks": v["chunks"],
                "content_hash": v.get("content_hash", ""),
            })
        else:
            result.append({
                "path": doc_path,
                "name": doc_name,
                "source": source_dir,
                "status": "local",
                "chunks": 0,
                "content_hash": "",
            })
    
    # 孤立记录（向量库有但本地没有）
    for doc in vector_docs:
        if doc["source"] not in local_paths and doc.get("source_type") == "local_file":
            source_dir = "web" if "\\data\\web\\" in doc["source"] or "/data/web/" in doc["source"] else "docs"
            result.append({
                "path": doc["source"],
                "name": doc["source_name"],
                "source": source_dir,
                "status": "orphan",
                "chunks": doc["chunks"],
                "content_hash": doc.get("content_hash", ""),
            })
    
    return result


def reload_env():
    """重新加载环境变量"""
    load_dotenv(ROOT / "config" / ".env", override=True)
