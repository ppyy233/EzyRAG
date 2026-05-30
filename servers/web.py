# -*- coding: utf-8 -*-
"""
Ezy-RAG — Web API 服务器
提供 REST API 接口 + 托管前端静态文件
用法: python -m servers.web
"""
import os
import sys
import json
import asyncio
import logging
import socket
import subprocess
from pathlib import Path
from typing import List, Optional, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.settings import (
    load_config, save_config, get_collection_name, get_docs_dir,
    get_chunk_config, get_chunk_templates, get_retrieval_config,
    get_embedding_mode, get_embedding_config, get_rerank_mode,
    get_rerank_enabled, get_rerank_config, get_hnsw_config
)
from config.pointer import get_active_collection, set_active_collection

LOG_DIR = ROOT / "runtime" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "web_api.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Ezy-RAG-Web")

app = FastAPI(title="Ezy-RAG Web API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
#  WebSocket 管理器
# ============================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# 线程池，用于执行同步/重建等耗时操作
executor = ThreadPoolExecutor(max_workers=2)

# ============================================================
#  数据模型
# ============================================================

class ApiResponse(BaseModel):
    status: str
    data: Any = None
    message: str = ""

class SearchRequest(BaseModel):
    query: str

class ConfigUpdate(BaseModel):
    embedding_mode: Optional[str] = None
    embedding_cloud_url: Optional[str] = None
    embedding_cloud_api_key: Optional[str] = None
    embedding_cloud_model: Optional[str] = None
    embedding_cloud_dim: Optional[str] = None
    embedding_local_url: Optional[str] = None
    embedding_local_model_path: Optional[str] = None
    embedding_local_dim: Optional[str] = None
    rerank_enabled: Optional[str] = None
    rerank_mode: Optional[str] = None
    rerank_cloud_url: Optional[str] = None
    rerank_cloud_api_key: Optional[str] = None
    rerank_cloud_model: Optional[str] = None
    rerank_local_url: Optional[str] = None
    rerank_local_model_path: Optional[str] = None
    chroma_host: Optional[str] = None
    chroma_port: Optional[str] = None
    mcp_host: Optional[str] = None
    mcp_port: Optional[str] = None
    chunk_template: Optional[str] = None

class ServiceAction(BaseModel):
    service: str

# ============================================================
#  工具函数
# ============================================================

def check_port(host: str, port: int) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def get_service_status() -> dict:
    chroma_host = os.getenv("CHROMA_SERVER_HOST", "127.0.0.1")
    chroma_port = int(os.getenv("CHROMA_SERVER_PORT", "9898"))
    mcp_host = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    mcp_port = int(os.getenv("MCP_SERVER_PORT", "9766"))
    
    embedding_mode = os.getenv("EMBEDDING_MODE", "cloud")
    rerank_enabled = os.getenv("RERANK_ENABLED", "true").lower() == "true"
    rerank_mode = os.getenv("RERANK_MODE", "cloud")
    
    services = {
        "chromadb": {
            "name": "ChromaDB",
            "online": check_port(chroma_host, chroma_port),
            "host": chroma_host,
            "port": chroma_port,
            "mode": "server"
        },
        "mcp": {
            "name": "MCP",
            "online": check_port(mcp_host, mcp_port),
            "host": mcp_host,
            "port": mcp_port,
            "mode": "server"
        },
        "embedding": {
            "name": "Embedding",
            "online": False,
            "mode": embedding_mode,
            "config": get_embedding_config()
        },
        "rerank": {
            "name": "Rerank",
            "online": False,
            "enabled": rerank_enabled,
            "mode": rerank_mode,
            "config": get_rerank_config()
        }
    }
    
    if embedding_mode == "local":
        emb_url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
        try:
            emb_port = int(emb_url.split(":")[-1].split("/")[0])
        except:
            emb_port = 1234
        services["embedding"]["online"] = check_port("127.0.0.1", emb_port)
        services["embedding"]["port"] = emb_port
    else:
        services["embedding"]["online"] = True
    
    if rerank_enabled:
        if rerank_mode == "local":
            rerank_url = os.getenv("RERANK_LOCAL_URL", "http://127.0.0.1:5001")
            try:
                rerank_port = int(rerank_url.split(":")[-1].split("/")[0])
            except:
                rerank_port = 5001
            services["rerank"]["online"] = check_port("127.0.0.1", rerank_port)
            services["rerank"]["port"] = rerank_port
        else:
            services["rerank"]["online"] = True
    
    return services

def connect_chroma():
    import chromadb
    from core.api import EmbeddingAPI
    from core.database import DocumentDatabase
    from core.maintenance import cleanup_orphan_hnsw_dirs, cleanup_orphan_shadows
    
    host = os.getenv("CHROMA_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("CHROMA_SERVER_PORT", "9898"))
    
    client = chromadb.HttpClient(host=host, port=port)
    client.heartbeat()
    
    emb_api = EmbeddingAPI()
    
    # 启动清理
    cleanup_orphan_hnsw_dirs()
    cleanup_orphan_shadows(client, get_collection_name())
    
    collection_name = get_active_collection(get_collection_name())
    
    try:
        collection = client.get_collection(name=collection_name)
        # 验证 HNSW 完整性
        try:
            collection.count()
        except Exception as e:
            if "hnsw" in str(e).lower():
                _repair_hnsw_index(collection_name)
                collection = client.get_collection(name=collection_name)
    except:
        # 从配置获取 HNSW 参数
        hnsw_config = get_hnsw_config()
        metadata = {
            "hnsw:space": hnsw_config["space"],
            "hnsw:sync_threshold": hnsw_config["sync_threshold"],
            "hnsw:ef_construction": hnsw_config["ef_construction"],
            "hnsw:M": hnsw_config["M"],
        }
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata=metadata
        )
        set_active_collection(get_collection_name(), collection_name)
    
    db = DocumentDatabase(collection, emb_api, client, collection_name)
    return client, db


def _repair_hnsw_index(collection_name: str):
    """修复 HNSW 索引：删除损坏的索引目录，让 ChromaDB 重建"""
    from core.maintenance import _get_hnsw_segment_id
    import shutil
    
    chroma_dir = ROOT / "data" / "chroma_db"
    hnsw_seg_id = _get_hnsw_segment_id(collection_name)
    if hnsw_seg_id:
        seg_dir = chroma_dir / hnsw_seg_id
        if seg_dir.exists():
            shutil.rmtree(str(seg_dir))
            logger.info(f"修复: 删除损坏的 HNSW 索引 {hnsw_seg_id[:8]}...")

def get_local_documents(source: str = "all") -> list:
    """获取本地文档列表（支持数据源过滤）"""
    from core.document import SUPPORTED_EXT
    
    docs_dir = ROOT / "data" / "docs"
    web_dir = ROOT / "data" / "web"
    
    documents = []
    seen = set()
    
    # 获取 docs 目录的文件
    if source in ("all", "docs") and docs_dir.exists():
        for ext in SUPPORTED_EXT:
            for f in docs_dir.glob(f"**/*{ext}"):
                if f.is_file():
                    key = str(f.resolve())
                    if key not in seen:
                        seen.add(key)
                        documents.append(str(f))
    
    # 获取 web 目录的文件
    if source in ("all", "web") and web_dir.exists():
        for ext in SUPPORTED_EXT:
            for f in web_dir.glob(f"**/*{ext}"):
                if f.is_file():
                    key = str(f.resolve())
                    if key not in seen:
                        seen.add(key)
                        documents.append(str(f))
    
    return sorted(documents)

# ============================================================
#  API 端点：系统
# ============================================================

@app.get("/api/system/health")
async def health_check():
    services = get_service_status()
    
    db_info = {"documents": 0, "chunks": 0, "collection": ""}
    try:
        _, db = connect_chroma()
        db_info["documents"] = len(db.list_documents())
        db_info["chunks"] = db.count()
        db_info["collection"] = db.collection_name
    except:
        pass
    
    return ApiResponse(
        status="success",
        data={
            "version": "1.0.0",
            "services": services,
            "database": db_info
        }
    )

@app.get("/api/system/status")
async def system_status():
    return ApiResponse(
        status="success",
        data=get_service_status()
    )

# ============================================================
#  API 端点：配置
# ============================================================

@app.get("/api/config")
async def get_config():
    try:
        env_path = ROOT / "config" / ".env"
        env_config = {}
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_config[key.strip()] = value.strip()
        
        config = load_config()
        
        return ApiResponse(
            status="success",
            data={
                "env": env_config,
                "config": config,
                "templates": get_chunk_templates()
            }
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.put("/api/config")
async def update_config(update: ConfigUpdate):
    try:
        env_path = ROOT / "config" / ".env"
        env_config = {}
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_config[key.strip()] = value.strip()
        
        if update.embedding_mode is not None:
            env_config['EMBEDDING_MODE'] = update.embedding_mode
        if update.embedding_cloud_url is not None:
            env_config['EMBEDDING_CLOUD_URL'] = update.embedding_cloud_url
        if update.embedding_cloud_api_key is not None:
            env_config['EMBEDDING_CLOUD_API_KEY'] = update.embedding_cloud_api_key
        if update.embedding_cloud_model is not None:
            env_config['EMBEDDING_CLOUD_MODEL'] = update.embedding_cloud_model
        if update.embedding_cloud_dim is not None:
            env_config['EMBEDDING_CLOUD_DIM'] = update.embedding_cloud_dim
        if update.embedding_local_url is not None:
            env_config['EMBEDDING_LOCAL_URL'] = update.embedding_local_url
        if update.embedding_local_model_path is not None:
            env_config['EMBEDDING_LOCAL_MODEL_PATH'] = update.embedding_local_model_path
        if update.embedding_local_dim is not None:
            env_config['EMBEDDING_LOCAL_DIM'] = update.embedding_local_dim
        if update.rerank_enabled is not None:
            env_config['RERANK_ENABLED'] = update.rerank_enabled
        if update.rerank_mode is not None:
            env_config['RERANK_MODE'] = update.rerank_mode
        if update.rerank_cloud_url is not None:
            env_config['RERANK_CLOUD_URL'] = update.rerank_cloud_url
        if update.rerank_cloud_api_key is not None:
            env_config['RERANK_CLOUD_API_KEY'] = update.rerank_cloud_api_key
        if update.rerank_cloud_model is not None:
            env_config['RERANK_CLOUD_MODEL'] = update.rerank_cloud_model
        if update.rerank_local_url is not None:
            env_config['RERANK_LOCAL_URL'] = update.rerank_local_url
        if update.rerank_local_model_path is not None:
            env_config['RERANK_LOCAL_MODEL_PATH'] = update.rerank_local_model_path
        if update.chroma_host is not None:
            env_config['CHROMA_SERVER_HOST'] = update.chroma_host
        if update.chroma_port is not None:
            env_config['CHROMA_SERVER_PORT'] = update.chroma_port
        if update.mcp_host is not None:
            env_config['MCP_SERVER_HOST'] = update.mcp_host
        if update.mcp_port is not None:
            env_config['MCP_SERVER_PORT'] = update.mcp_port
        if update.chunk_template is not None:
            env_config['CHUNK_TEMPLATE'] = update.chunk_template
        
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("# ============================================================\n")
            f.write("# Ezy-RAG V1.0.0 — 环境配置\n")
            f.write("# ============================================================\n\n")
            
            f.write("# ----- Embedding 配置 -----\n")
            f.write(f"EMBEDDING_MODE={env_config.get('EMBEDDING_MODE', 'cloud')}\n\n")
            f.write("# 云端配置\n")
            for key in ['EMBEDDING_CLOUD_URL', 'EMBEDDING_CLOUD_API_KEY', 'EMBEDDING_CLOUD_MODEL', 'EMBEDDING_CLOUD_DIM']:
                f.write(f"{key}={env_config.get(key, '')}\n")
            f.write("\n# 本地配置\n")
            for key in ['EMBEDDING_LOCAL_URL', 'EMBEDDING_LOCAL_MODEL_PATH', 'EMBEDDING_LOCAL_DIM']:
                f.write(f"{key}={env_config.get(key, '')}\n")
            f.write("\n")
            
            f.write("# ----- Rerank 配置 -----\n")
            f.write(f"RERANK_ENABLED={env_config.get('RERANK_ENABLED', 'true')}\n")
            f.write(f"RERANK_MODE={env_config.get('RERANK_MODE', 'cloud')}\n\n")
            f.write("# 云端配置\n")
            for key in ['RERANK_CLOUD_URL', 'RERANK_CLOUD_API_KEY', 'RERANK_CLOUD_MODEL']:
                f.write(f"{key}={env_config.get(key, '')}\n")
            f.write("\n# 本地配置\n")
            for key in ['RERANK_LOCAL_URL', 'RERANK_LOCAL_MODEL_PATH']:
                f.write(f"{key}={env_config.get(key, '')}\n")
            f.write("\n")
            
            f.write("# ----- 服务配置 -----\n")
            for key in ['CHROMA_SERVER_HOST', 'CHROMA_SERVER_PORT', 'MCP_SERVER_HOST', 'MCP_SERVER_PORT']:
                f.write(f"{key}={env_config.get(key, '')}\n")
            f.write("\n")
            
            f.write("# ----- 切块策略 -----\n")
            f.write(f"CHUNK_TEMPLATE={env_config.get('CHUNK_TEMPLATE', 'academic')}\n")
        
        load_dotenv(env_path, override=True)
        
        return ApiResponse(status="success", message="配置已保存，部分配置需要重启服务生效")
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.get("/api/config/templates")
async def get_templates():
    return ApiResponse(
        status="success",
        data=get_chunk_templates()
    )

@app.get("/api/config/chunk")
async def get_chunk_config_api():
    """获取当前切片配置"""
    try:
        config = get_chunk_config()
        templates = get_chunk_templates()
        
        return ApiResponse(
            status="success",
            data={
                "current": config,
                "templates": templates
            }
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.put("/api/config/chunk")
async def update_chunk_config(request: dict):
    """更新切片配置"""
    try:
        import json
        
        chunk_size = request.get("chunk_size")
        overlap = request.get("overlap")
        strategy = request.get("strategy")
        template = request.get("template")
        
        # 更新 config.json
        config_path = ROOT / "config" / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if template:
            # 切换模板
            if template in config["chunk"]["templates"]:
                config["chunk"]["default_template"] = template
            else:
                return ApiResponse(status="error", message=f"模板 {template} 不存在")
        elif chunk_size is not None and overlap is not None and strategy is not None:
            # 更新自定义模板
            config["chunk"]["templates"]["custom"] = {
                "name": "自定义模板",
                "chunk_size": int(chunk_size),
                "overlap": int(overlap),
                "strategy": strategy,
                "separators": ["\n\n", "\n", " ", ""]
            }
            config["chunk"]["default_template"] = "custom"
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"切片配置已更新: chunk_size={chunk_size}, overlap={overlap}, strategy={strategy}, template={template}")
        
        return ApiResponse(status="success", message="切片配置已保存")
    except Exception as e:
        logger.error(f"更新切片配置失败: {e}")
        return ApiResponse(status="error", message=str(e))

# ============================================================
#  API 端点：文档管理
# ============================================================

@app.get("/api/documents")
async def list_documents(source: str = "all"):
    try:
        local_docs = get_local_documents(source)
        
        vector_docs = []
        try:
            _, db = connect_chroma()
            vector_docs = db.list_documents()
        except:
            pass
        
        local_set = {d for d in local_docs}
        vector_map = {d["source"]: d for d in vector_docs}
        
        result = []
        for doc_path in local_docs:
            doc_name = Path(doc_path).name
            # 判断来源
            source_type = "local"
            if "/data/web/" in doc_path.replace("\\", "/") or "\\data\\web\\" in doc_path:
                source_type = "web"
            
            if doc_path in vector_map:
                v = vector_map[doc_path]
                result.append({
                    "path": doc_path,
                    "name": doc_name,
                    "source_type": source_type,
                    "status": "imported",
                    "chunks": v["chunks"],
                    "content_hash": v.get("content_hash", ""),
                    "created_at": v.get("created_at", "")
                })
            else:
                result.append({
                    "path": doc_path,
                    "name": doc_name,
                    "source_type": source_type,
                    "status": "local",
                    "chunks": 0,
                    "content_hash": "",
                    "created_at": ""
                })
        
        # 添加孤立记录（根据数据源过滤）
        for doc in vector_docs:
            if doc["source"] not in local_set and doc.get("source_type") == "local_file":
                source_type = "local"
                if "/data/web/" in doc["source"].replace("\\", "/") or "\\data\\web\\" in doc["source"]:
                    source_type = "web"
                
                # 根据数据源过滤
                if source == "docs" and source_type != "local":
                    continue
                if source == "web" and source_type != "web":
                    continue
                
                result.append({
                    "path": doc["source"],
                    "name": doc["source_name"],
                    "source_type": source_type,
                    "status": "orphan",
                    "chunks": doc["chunks"],
                    "content_hash": doc.get("content_hash", ""),
                    "created_at": doc.get("created_at", "")
                })
        
        return ApiResponse(status="success", data=result)
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/import")
async def import_documents(request: dict):
    try:
        from core.document import read_file, SUPPORTED_EXT
        
        file_paths = request.get("files", [])
        if not file_paths:
            return ApiResponse(status="error", message="未指定文件")
        
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        results = []
        total_chunks = 0
        
        for file_path in file_paths:
            full_path = Path(file_path)
            if not full_path.exists():
                results.append({"file": file_path, "status": "error", "message": "文件不存在"})
                continue
            
            ext = full_path.suffix.lower()
            if ext not in SUPPORTED_EXT:
                results.append({"file": file_path, "status": "error", "message": f"不支持的格式: {ext}"})
                continue
            
            try:
                text = read_file(str(full_path))
                if not text or not text.strip():
                    results.append({"file": file_path, "status": "error", "message": "文件内容为空"})
                    continue
                
                doc_name = full_path.stem
                text = f"[文件名: {doc_name}]\n{text}"
                doc = {"path": str(full_path), "text": text}
                
                count = db.add(doc, chunk_cfg, source_type="local_file")
                total_chunks += count
                results.append({"file": file_path, "status": "success", "chunks": count})
                
                await manager.broadcast({
                    "type": "import_progress",
                    "data": {"file": full_path.name, "chunks": count, "status": "success"}
                })
            except Exception as e:
                results.append({"file": file_path, "status": "error", "message": str(e)})
        
        return ApiResponse(
            status="success",
            data={"results": results, "total_chunks": total_chunks}
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/import-all")
async def import_all_documents():
    try:
        local_docs = get_local_documents()
        if not local_docs:
            return ApiResponse(status="error", message="没有找到本地文档")
        
        from core.document import read_file, SUPPORTED_EXT
        
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        results = []
        total_chunks = 0
        
        for file_path in local_docs:
            full_path = Path(file_path)
            try:
                text = read_file(str(full_path))
                if not text or not text.strip():
                    continue
                
                doc_name = full_path.stem
                text = f"[文件名: {doc_name}]\n{text}"
                doc = {"path": str(full_path), "text": text}
                
                count = db.add(doc, chunk_cfg, source_type="local_file")
                total_chunks += count
                results.append({"file": file_path, "status": "success", "chunks": count})
                
                await manager.broadcast({
                    "type": "import_progress",
                    "data": {"file": full_path.name, "chunks": count, "status": "success"}
                })
            except Exception as e:
                results.append({"file": file_path, "status": "error", "message": str(e)})
        
        return ApiResponse(
            status="success",
            data={"results": results, "total_chunks": total_chunks, "total_files": len(local_docs)}
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """上传文件到 data/docs 目录"""
    try:
        docs_dir = ROOT / "data" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        
        uploaded = []
        for file in files:
            file_path = docs_dir / file.filename
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            uploaded.append(file.filename)
            logger.info(f"上传文件: {file.filename}")
        
        return ApiResponse(status="success", data={"uploaded": uploaded, "count": len(uploaded)})
    except Exception as e:
        logger.error(f"上传失败: {e}")
        return ApiResponse(status="error", message=str(e))

@app.delete("/api/documents/{file_path:path}")
async def delete_document(file_path: str):
    try:
        _, db = connect_chroma()
        logger.info(f"删除文档: {file_path}")
        db.delete(file_path)
        logger.info(f"删除成功: {file_path}")
        return ApiResponse(status="success", message=f"已删除: {file_path}")
    except Exception as e:
        logger.error(f"删除失败: {file_path}, 错误: {e}")
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/delete-all")
async def delete_all_documents(request: dict):
    """删除所有文档的向量记录"""
    try:
        source = request.get("source", "all")
        _, db = connect_chroma()
        
        # 根据数据源获取文档列表
        docs = db.list_documents()
        if source == "docs":
            docs = [d for d in docs if d.get("source_type") == "local_file" and "/data/web/" not in d["source"].replace("\\", "/")]
        elif source == "web":
            docs = [d for d in docs if "/data/web/" in d["source"].replace("\\", "/") or "\\data\\web\\" in d["source"]]
        
        deleted = 0
        for doc in docs:
            try:
                db.delete(doc["source"])
                deleted += 1
                logger.info(f"删除: {doc['source_name']}")
            except Exception as e:
                logger.warning(f"删除失败: {doc['source_name']}, 错误: {e}")
        
        logger.info(f"完全删除完成: {deleted} 个文档")
        return ApiResponse(status="success", data={"deleted": deleted})
    except Exception as e:
        logger.error(f"完全删除失败: {e}")
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/update")
async def update_document(request: dict):
    """更新单个文档"""
    try:
        file_path = request.get("file_path", "")
        if not file_path:
            return ApiResponse(status="error", message="未指定文件路径")
        
        from core.document import read_file, SUPPORTED_EXT
        
        full_path = Path(file_path)
        if not full_path.exists():
            return ApiResponse(status="error", message="文件不存在")
        
        ext = full_path.suffix.lower()
        if ext not in SUPPORTED_EXT:
            return ApiResponse(status="error", message=f"不支持的格式: {ext}")
        
        text = read_file(str(full_path))
        if not text or not text.strip():
            return ApiResponse(status="error", message="文件内容为空")
        
        doc_name = full_path.stem
        text = f"[文件名: {doc_name}]\n{text}"
        doc = {"path": str(full_path), "text": text}
        
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        count = db.update(doc, chunk_cfg, source_type="local_file")
        
        logger.info(f"更新成功: {file_path}, {count} chunks")
        return ApiResponse(status="success", data={"chunks": count})
    except Exception as e:
        logger.error(f"更新失败: {e}")
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/sync")
async def sync_documents(request: dict):
    try:
        from core.document import load_all_documents
        
        source = request.get("source", "all")
        
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        # 根据数据源加载文档
        dirs = []
        if source in ("all", "docs"):
            docs_dir = ROOT / "data" / "docs"
            if docs_dir.exists():
                dirs.append(docs_dir)
        if source in ("all", "web"):
            web_dir = ROOT / "data" / "web"
            if web_dir.exists():
                dirs.append(web_dir)
        
        if not dirs:
            return ApiResponse(status="error", message="没有找到数据目录")
        
        logger.info(f"开始同步文档 (source={source})...")
        documents = load_all_documents(*dirs)
        if not documents:
            return ApiResponse(status="error", message="没有本地文档")
        
        logger.info(f"共加载 {len(documents)} 份文档")
        
        # 创建进度队列
        progress_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        
        # 进度回调（在工作线程中调用）
        def on_progress(op, idx, total, name, count):
            try:
                loop.call_soon_threadsafe(
                    progress_queue.put_nowait,
                    {"op": op, "idx": idx, "total": total, "name": name, "count": count}
                )
            except Exception:
                pass
        
        # 异步进度推送协程
        async def push_progress():
            while True:
                try:
                    msg = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    if msg.get("done"):
                        break
                    await manager.broadcast({
                        "type": "sync_progress",
                        "data": msg
                    })
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break
        
        push_task = asyncio.create_task(push_progress())
        
        # 在线程池中执行同步（避免阻塞事件循环）
        stats = await loop.run_in_executor(
            executor,
            lambda: db.sync(documents, chunk_cfg, on_progress=on_progress)
        )
        
        # 通知进度推送结束
        progress_queue.put_nowait({"done": True})
        await push_task
        
        logger.info(f"同步完成: 新增={stats['added']}, 更新={stats['updated']}, 未变={stats['unchanged']}, 删除={stats['deleted']}")
        
        await manager.broadcast({
            "type": "sync_complete",
            "data": stats
        })
        
        return ApiResponse(status="success", data=stats)
    except Exception as e:
        logger.error(f"同步失败: {e}")
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/rebuild")
async def rebuild_documents(request: dict):
    try:
        from core.document import load_all_documents
        
        source = request.get("source", "all")
        
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        # 根据数据源加载文档
        dirs = []
        if source in ("all", "docs"):
            docs_dir = ROOT / "data" / "docs"
            if docs_dir.exists():
                dirs.append(docs_dir)
        if source in ("all", "web"):
            web_dir = ROOT / "data" / "web"
            if web_dir.exists():
                dirs.append(web_dir)
        
        if not dirs:
            return ApiResponse(status="error", message="没有找到数据目录")
        
        logger.info(f"开始全量重建 (source={source})...")
        documents = load_all_documents(*dirs)
        if not documents:
            return ApiResponse(status="error", message="没有本地文档")
        
        logger.info(f"共加载 {len(documents)} 份文档")
        
        # 创建进度队列
        progress_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        
        # 进度回调（在工作线程中调用）
        def on_progress(op, idx, total, name, count):
            try:
                loop.call_soon_threadsafe(
                    progress_queue.put_nowait,
                    {"op": op, "idx": idx, "total": total, "name": name, "count": count}
                )
            except Exception:
                pass
        
        # 异步进度推送协程
        async def push_progress():
            while True:
                try:
                    msg = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    if msg.get("done"):
                        break
                    await manager.broadcast({
                        "type": "rebuild_progress",
                        "data": msg
                    })
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break
        
        push_task = asyncio.create_task(push_progress())
        
        # 在线程池中执行重建（避免阻塞事件循环）
        count = await loop.run_in_executor(
            executor,
            lambda: db.rebuild(documents, chunk_cfg, on_progress=on_progress)
        )
        
        # 通知进度推送结束
        progress_queue.put_nowait({"done": True})
        await push_task
        
        logger.info(f"重建完成: {count} chunks")
        
        await manager.broadcast({
            "type": "rebuild_complete",
            "data": {"chunks": count, "documents": len(documents)}
        })
        
        return ApiResponse(
            status="success",
            data={"chunks": count, "documents": len(documents)}
        )
    except Exception as e:
        logger.error(f"重建失败: {e}")
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/clean-orphans")
async def clean_orphan_records(request: dict):
    try:
        source = request.get("source", "all")
        
        _, db = connect_chroma()
        
        # 根据数据源获取目录
        dirs = []
        if source in ("all", "docs"):
            docs_dir = str(ROOT / "data" / "docs")
            dirs.append(docs_dir)
        if source in ("all", "web"):
            web_dir = str(ROOT / "data" / "web")
            dirs.append(web_dir)
        
        orphans = db.check_orphan_records(*dirs)
        if not orphans:
            return ApiResponse(status="success", data={"cleaned": 0, "message": "没有孤立记录"})
        
        count = db.clean_orphan_records(*dirs)
        return ApiResponse(status="success", data={"cleaned": count})
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/batch-import")
async def batch_import_documents(request: dict):
    """批量导入文档（带进度推送）"""
    try:
        files = request.get("files", [])
        if not files:
            return ApiResponse(status="error", message="未指定文件")
        
        from core.document import read_file, SUPPORTED_EXT
        
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        results = []
        total_chunks = 0
        n = len(files)
        
        for i, file_path in enumerate(files, 1):
            full_path = Path(file_path)
            if not full_path.exists():
                results.append({"file": file_path, "status": "error", "message": "文件不存在"})
                await manager.broadcast({
                    "type": "batch_progress",
                    "data": {"op": "import", "idx": i, "total": n, "name": full_path.name, "status": "error", "message": "文件不存在"}
                })
                continue
            
            ext = full_path.suffix.lower()
            if ext not in SUPPORTED_EXT:
                results.append({"file": file_path, "status": "error", "message": f"不支持的格式: {ext}"})
                await manager.broadcast({
                    "type": "batch_progress",
                    "data": {"op": "import", "idx": i, "total": n, "name": full_path.name, "status": "error", "message": f"不支持的格式: {ext}"}
                })
                continue
            
            try:
                text = read_file(str(full_path))
                if not text or not text.strip():
                    results.append({"file": file_path, "status": "error", "message": "文件内容为空"})
                    await manager.broadcast({
                        "type": "batch_progress",
                        "data": {"op": "import", "idx": i, "total": n, "name": full_path.name, "status": "error", "message": "文件内容为空"}
                    })
                    continue
                
                doc_name = full_path.stem
                text = f"[文件名: {doc_name}]\n{text}"
                doc = {"path": str(full_path), "text": text}
                
                count = db.add(doc, chunk_cfg, source_type="local_file")
                total_chunks += count
                results.append({"file": file_path, "status": "success", "chunks": count})
                
                await manager.broadcast({
                    "type": "batch_progress",
                    "data": {"op": "import", "idx": i, "total": n, "name": full_path.name, "status": "success", "chunks": count}
                })
            except Exception as e:
                results.append({"file": file_path, "status": "error", "message": str(e)})
                await manager.broadcast({
                    "type": "batch_progress",
                    "data": {"op": "import", "idx": i, "total": n, "name": full_path.name, "status": "error", "message": str(e)}
                })
        
        imported = sum(1 for r in results if r["status"] == "success")
        
        await manager.broadcast({
            "type": "batch_complete",
            "data": {"op": "import", "imported": imported, "total_chunks": total_chunks}
        })
        
        return ApiResponse(
            status="success",
            data={"imported": imported, "total_chunks": total_chunks, "results": results}
        )
    except Exception as e:
        logger.error(f"批量导入失败: {e}")
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/batch-delete")
async def batch_delete_documents(request: dict):
    """批量删除文档的向量记录（带进度推送）"""
    try:
        files = request.get("files", [])
        if not files:
            return ApiResponse(status="error", message="未指定文件")
        
        _, db = connect_chroma()
        
        results = []
        n = len(files)
        
        for i, file_path in enumerate(files, 1):
            try:
                db.delete(file_path)
                results.append({"file": file_path, "status": "success"})
                logger.info(f"批量删除: {file_path}")
                
                await manager.broadcast({
                    "type": "batch_progress",
                    "data": {"op": "delete", "idx": i, "total": n, "name": Path(file_path).name, "status": "success"}
                })
            except Exception as e:
                results.append({"file": file_path, "status": "error", "message": str(e)})
                await manager.broadcast({
                    "type": "batch_progress",
                    "data": {"op": "delete", "idx": i, "total": n, "name": Path(file_path).name, "status": "error", "message": str(e)}
                })
        
        deleted = sum(1 for r in results if r["status"] == "success")
        
        await manager.broadcast({
            "type": "batch_complete",
            "data": {"op": "delete", "deleted": deleted}
        })
        
        return ApiResponse(status="success", data={"deleted": deleted, "results": results})
    except Exception as e:
        logger.error(f"批量删除失败: {e}")
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/crawl")
async def crawl_webpage(request: dict):
    try:
        from core.document import read_file
        from core.utils import md5_short
        
        url = request.get("url", "")
        if not url:
            return ApiResponse(status="error", message="URL 不能为空")
        
        logger.info(f"开始爬取: {url}")
        
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return ApiResponse(status="error", message="缺少依赖，请运行: uv pip install requests beautifulsoup4")
        
        # 1. 爬取网页
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string if soup.title else url
        
        # 2. 提取纯文本
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)
        
        if not text:
            return ApiResponse(status="error", message="网页内容为空")
        
        # 3. 保存到 data/web 目录
        web_dir = ROOT / "data" / "web"
        web_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{md5_short(url)}.txt"
        filepath = web_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"[网页标题: {title}]\n")
            f.write(f"[来源: {url}]\n")
            f.write(f"[爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n\n")
            f.write(text)
        
        # 4. 添加到向量库（和本地文档走相同流程）
        text_content = read_file(str(filepath))
        doc_name = filepath.stem
        doc = {"path": str(filepath), "text": f"[文件名: {doc_name}]\n{text_content}"}
        
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        count = db.add(doc, chunk_cfg, source_type="local_file")
        
        logger.info(f"爬取成功: {url}, 保存到 {filename}, {count} chunks")
        
        return ApiResponse(
            status="success",
            data={"url": url, "title": title, "file": filename, "chunks": count}
        )
    except Exception as e:
        logger.error(f"爬取失败: {e}")
        return ApiResponse(status="error", message=str(e))

# ============================================================
#  API 端点：搜索
# ============================================================

@app.post("/api/search")
async def search_knowledge_base(request: SearchRequest):
    try:
        from core.api import EmbeddingAPI, RerankAPI
        from core.scheduler import get_scheduler
        
        query = request.query
        if not query:
            return ApiResponse(status="error", message="查询不能为空")
        
        emb_api = EmbeddingAPI()
        ok, err = emb_api.health_check()
        if not ok:
            return ApiResponse(status="error", message=f"Embedding 服务不可用: {err}")
        
        scheduler = get_scheduler()
        
        vectors = await scheduler.embed_async([query], priority=0)
        query_vec = vectors[0]
        
        _, db = connect_chroma()
        
        retrieval_config = get_retrieval_config()
        k = retrieval_config["k"]
        fetch_k = retrieval_config["fetch_k"]
        
        rerank_api = RerankAPI()
        do_rerank = rerank_api.get_info()["enabled"]
        actual_fetch_k = fetch_k if do_rerank else k
        
        results = db.search(query_vec, n_results=actual_fetch_k)
        
        if not results or not results["ids"] or not results["ids"][0]:
            return ApiResponse(
                status="success",
                data={"results": [], "query": query, "total": 0}
            )
        
        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]
        
        rerank_executed = False
        rerank_scores = []
        
        if do_rerank and len(docs) > 1:
            try:
                scores, indices = await rerank_api.rerank_async(query, docs)
                rerank_executed = True
                rerank_scores = scores
                ids = [ids[i] for i in indices]
                docs = [docs[i] for i in indices]
                metas = [metas[i] for i in indices]
                dists = [dists[i] for i in indices]
            except Exception as e:
                logger.warning(f"Rerank 失败: {e}")
                docs = docs[:k]
                metas = metas[:k]
                dists = dists[:k]
                ids = ids[:k]
        else:
            docs = docs[:k]
            metas = metas[:k]
            dists = dists[:k]
            ids = ids[:k]
        
        search_results = []
        for i, (doc_id, doc_text, meta, dist) in enumerate(zip(ids, docs, metas, dists)):
            source = meta.get("source", "未知来源")
            fname = Path(source).name if source != "未知来源" else "未知来源"
            similarity = max(0, 1 - dist)
            
            result_item = {
                "id": doc_id,
                "text": doc_text.strip(),
                "source": source,
                "filename": fname,
                "similarity": round(similarity * 100, 2),
                "chunk_index": meta.get("chunk_index", 0)
            }
            
            if rerank_executed and i < len(rerank_scores):
                result_item["rerank_score"] = round(rerank_scores[i] * 100, 2)
            
            search_results.append(result_item)
        
        return ApiResponse(
            status="success",
            data={
                "results": search_results,
                "query": query,
                "total": len(search_results),
                "rerank": rerank_executed
            }
        )
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return ApiResponse(status="error", message=str(e))

# ============================================================
#  API 端点：服务管理
# ============================================================

@app.post("/api/services/start")
async def start_service(request: ServiceAction):
    try:
        service = request.service
        host = "127.0.0.1"
        
        if service == "chromadb":
            port = int(os.getenv("CHROMA_SERVER_PORT", "9898"))
            if check_port(host, port):
                return ApiResponse(status="success", message="ChromaDB 已在运行")
            subprocess.Popen([sys.executable, "-m", "servers.chroma"], cwd=ROOT)
            
        elif service == "embedding":
            if os.getenv("EMBEDDING_MODE", "cloud") != "local":
                return ApiResponse(status="error", message="当前为云端模式，无需启动本地 Embedding")
            emb_url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
            try:
                port = int(emb_url.split(":")[-1].split("/")[0])
            except:
                port = 1234
            if check_port(host, port):
                return ApiResponse(status="success", message="Embedding 已在运行")
            subprocess.Popen([sys.executable, "-m", "servers.embedding"], cwd=ROOT)
            
        elif service == "rerank":
            if not get_rerank_enabled() or get_rerank_mode() != "local":
                return ApiResponse(status="error", message="当前未启用本地 Rerank")
            rerank_url = os.getenv("RERANK_LOCAL_URL", "http://127.0.0.1:5001")
            try:
                port = int(rerank_url.split(":")[-1].split("/")[0])
            except:
                port = 5001
            if check_port(host, port):
                return ApiResponse(status="success", message="Rerank 已在运行")
            subprocess.Popen([sys.executable, "-m", "servers.rerank"], cwd=ROOT)
            
        elif service == "mcp":
            port = int(os.getenv("MCP_SERVER_PORT", "9766"))
            if check_port(host, port):
                return ApiResponse(status="success", message="MCP 已在运行")
            subprocess.Popen([sys.executable, "-m", "servers.mcp"], cwd=ROOT)
            
        elif service == "all":
            results = []
            chroma_port = int(os.getenv("CHROMA_SERVER_PORT", "9898"))
            if not check_port(host, chroma_port):
                subprocess.Popen([sys.executable, "-m", "servers.chroma"], cwd=ROOT)
                results.append("ChromaDB 启动中")
            
            if os.getenv("EMBEDDING_MODE", "cloud") == "local":
                emb_url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
                try:
                    emb_port = int(emb_url.split(":")[-1].split("/")[0])
                except:
                    emb_port = 1234
                if not check_port(host, emb_port):
                    subprocess.Popen([sys.executable, "-m", "servers.embedding"], cwd=ROOT)
                    results.append("Embedding 启动中")
            
            if get_rerank_enabled() and get_rerank_mode() == "local":
                rerank_url = os.getenv("RERANK_LOCAL_URL", "http://127.0.0.1:5001")
                try:
                    rerank_port = int(rerank_url.split(":")[-1].split("/")[0])
                except:
                    rerank_port = 5001
                if not check_port(host, rerank_port):
                    subprocess.Popen([sys.executable, "-m", "servers.rerank"], cwd=ROOT)
                    results.append("Rerank 启动中")
            
            mcp_port = int(os.getenv("MCP_SERVER_PORT", "9766"))
            if not check_port(host, mcp_port):
                subprocess.Popen([sys.executable, "-m", "servers.mcp"], cwd=ROOT)
                results.append("MCP 启动中")
            
            return ApiResponse(status="success", data={"started": results})
        else:
            return ApiResponse(status="error", message=f"未知服务: {service}")
        
        return ApiResponse(status="success", message=f"{service} 启动中")
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.post("/api/services/stop")
async def stop_service(request: ServiceAction):
    try:
        service = request.service
        host = "127.0.0.1"
        
        port_map = {
            "chromadb": int(os.getenv("CHROMA_SERVER_PORT", "9898")),
            "mcp": int(os.getenv("MCP_SERVER_PORT", "9766")),
        }
        
        if os.getenv("EMBEDDING_MODE", "cloud") == "local":
            emb_url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
            try:
                port_map["embedding"] = int(emb_url.split(":")[-1].split("/")[0])
            except:
                port_map["embedding"] = 1234
        
        if get_rerank_enabled() and get_rerank_mode() == "local":
            rerank_url = os.getenv("RERANK_LOCAL_URL", "http://127.0.0.1:5001")
            try:
                port_map["rerank"] = int(rerank_url.split(":")[-1].split("/")[0])
            except:
                port_map["rerank"] = 5001
        
        if service == "all":
            stopped = []
            for svc, port in port_map.items():
                if check_port(host, port):
                    try:
                        result = subprocess.run(
                            ["netstat", "-ano"],
                            capture_output=True, text=True
                        )
                        for line in result.stdout.split('\n'):
                            if f":{port}" in line and "LISTENING" in line:
                                pid = line.split()[-1]
                                subprocess.run(
                                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                                    capture_output=True
                                )
                                stopped.append(svc)
                                break
                    except:
                        pass
            return ApiResponse(status="success", data={"stopped": stopped})
        
        if service not in port_map:
            return ApiResponse(status="error", message=f"未知服务: {service}")
        
        port = port_map[service]
        if not check_port(host, port):
            return ApiResponse(status="success", message=f"{service} 未在运行")
        
        try:
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.split()[-1]
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True
                    )
                    return ApiResponse(status="success", message=f"{service} 已停止")
        except:
            pass
        
        return ApiResponse(status="error", message=f"停止 {service} 失败")
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

# ============================================================
#  WebSocket
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ============================================================
#  前端静态文件托管
# ============================================================

frontend_dist = ROOT / "frontend" / "dist"

if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            response = FileResponse(str(file_path))
            # 对 index.html 和根路径设置不缓存
            if full_path == "index.html" or full_path == "":
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
            return response
        # SPA fallback - 返回 index.html
        response = FileResponse(str(frontend_dist / "index.html"))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

# ============================================================
#  启动入口
# ============================================================

def main():
    host = os.getenv("WEB_API_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_API_PORT", "9767"))
    
    logger.info("=" * 50)
    logger.info("Ezy-RAG Web API Server V1.0.0")
    logger.info(f"监听: http://{host}:{port}")
    logger.info("=" * 50)
    
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
