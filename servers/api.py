# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.14 — REST API + WebSocket 服务器
提供文档管理、搜索、状态查询等 API

用法: python -m servers.api
"""
import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import chromadb
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import settings
from config.settings import get_chunk_config, get_collection_name
from core.embedder import get_lm_proxy
from core.repository import DocumentRepository
from core.builder import build_incremental, build_full, load_all_documents

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Ezy-RAG-API")

# 创建 FastAPI 应用
app = FastAPI(title="Ezy-RAG API", version="0.0.14")

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 已连接，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket 已断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# 请求模型
class AddDocumentRequest(BaseModel):
    file_path: str

class DeleteDocumentRequest(BaseModel):
    file_path: str

class UpdateDocumentRequest(BaseModel):
    file_path: str

class SearchRequest(BaseModel):
    query: str

# 响应模型
class ApiResponse(BaseModel):
    status: str
    data: Any = None
    message: str = ""

# 获取 ChromaDB 客户端
async def get_chroma_client():
    return chromadb.HttpClient(
        host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
    )

# 获取 Repository
async def get_repository():
    client = await get_chroma_client()
    collection_name = get_active_collection_name()
    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
        )
    emb_proxy = get_lm_proxy()
    return DocumentRepository(collection, emb_proxy)

# 获取当前活跃集合名
def get_active_collection_name() -> str:
    pointer_file = ROOT / "runtime" / "state" / "collection_pointer.json"
    if pointer_file.exists():
        with open(pointer_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("default_collection", "default_collection")
    return "default_collection"

# 获取本地文档列表
def get_local_documents() -> List[str]:
    docs_dir = ROOT / "data" / "docs"
    if not docs_dir.exists():
        return []
    
    documents = []
    for f in docs_dir.glob("**/*"):
        if f.is_file() and f.suffix in {".txt", ".md", ".pdf", ".docx", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs"}:
            documents.append(str(f))
    
    return sorted(documents)

# WebSocket 端点
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 处理搜索请求
            if message.get("type") == "search":
                query = message.get("data", {}).get("query", "")
                if query:
                    # 广播搜索开始
                    await manager.broadcast({
                        "type": "search",
                        "data": {"status": "started", "query": query},
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # 执行搜索（这里需要调用 MCP 的搜索逻辑）
                    # 暂时返回模拟结果
                    await manager.broadcast({
                        "type": "search",
                        "data": {
                            "status": "completed",
                            "query": query,
                            "results": []
                        },
                        "timestamp": datetime.now().isoformat()
                    })
            
            # 处理其他消息
            else:
                await websocket.send_text(f"Message received: {data}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# REST API 端点

@app.get("/api/status")
async def get_status():
    """获取数据库状态"""
    try:
        client = await get_chroma_client()
        client.heartbeat()
        
        repo = await get_repository()
        docs = repo.list_documents()
        
        return ApiResponse(
            status="success",
            data={
                "collection": get_active_collection_name(),
                "total_records": repo.count(),
                "total_documents": len(docs),
                "chromadb": {"online": True, "url": f"{os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}"},
                "embedding": {"online": True, "url": os.getenv("EMBEDDING_API_URL", "http://127.0.0.1:5000")},
            }
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.get("/api/documents")
async def list_documents():
    """获取文档映射表"""
    try:
        repo = await get_repository()
        vector_docs = repo.list_documents()
        local_docs = get_local_documents()
        
        # 构建映射表
        documents = []
        for doc_path in local_docs:
            doc_name = Path(doc_path).name
            # 检查是否在向量库中
            in_vector = False
            chunks = 0
            for v_doc in vector_docs:
                if v_doc["source"] == doc_path:
                    in_vector = True
                    chunks = v_doc["chunks"]
                    break
            
            documents.append({
                "path": doc_path,
                "name": doc_name,
                "in_vector": in_vector,
                "chunks": chunks
            })
        
        return ApiResponse(
            status="success",
            data={
                "documents": documents,
                "local_count": len(local_docs),
                "vector_count": len(vector_docs),
                "total_chunks": sum(d["chunks"] for d in vector_docs)
            }
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents")
async def add_document(request: AddDocumentRequest):
    """添加文档到向量库"""
    try:
        file_path = request.file_path
        full_path = ROOT / file_path
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
        
        # 读取文件内容
        text = full_path.read_text(encoding="utf-8")
        doc_name = full_path.stem
        text = f"[文件名: {doc_name}]\n{text}"
        
        # 添加到向量库
        repo = await get_repository()
        chunk_cfg = get_chunk_config()
        doc = {"path": file_path, "text": text}
        count = repo.add(doc, chunk_cfg)
        
        # 广播文档更新
        await manager.broadcast({
            "type": "document",
            "data": {
                "action": "add",
                "file_path": file_path,
                "chunks": count
            },
            "timestamp": datetime.now().isoformat()
        })
        
        return ApiResponse(
            status="success",
            message=f"添加成功: {file_path} ({count} chunks)"
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文件到本地文档库"""
    try:
        docs_dir = ROOT / "data" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = docs_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 广播文件上传
        await manager.broadcast({
            "type": "document",
            "data": {
                "action": "upload",
                "file_path": str(file_path),
                "file_name": file.filename
            },
            "timestamp": datetime.now().isoformat()
        })
        
        return ApiResponse(
            status="success",
            data={"file_path": str(file_path)},
            message=f"上传成功: {file.filename}"
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.delete("/api/documents")
async def delete_document(request: DeleteDocumentRequest):
    """从向量库删除文档"""
    try:
        repo = await get_repository()
        repo.delete(request.file_path)
        
        # 广播文档删除
        await manager.broadcast({
            "type": "document",
            "data": {
                "action": "delete",
                "file_path": request.file_path
            },
            "timestamp": datetime.now().isoformat()
        })
        
        return ApiResponse(
            status="success",
            message=f"删除成功: {request.file_path}"
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.put("/api/documents")
async def update_document(request: UpdateDocumentRequest):
    """更新向量库中的文档"""
    try:
        file_path = request.file_path
        full_path = ROOT / file_path
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
        
        # 读取文件内容
        text = full_path.read_text(encoding="utf-8")
        doc_name = full_path.stem
        text = f"[文件名: {doc_name}]\n{text}"
        
        # 更新向量库
        repo = await get_repository()
        chunk_cfg = get_chunk_config()
        doc = {"path": file_path, "text": text}
        count = repo.update(doc, chunk_cfg)
        
        # 广播文档更新
        await manager.broadcast({
            "type": "document",
            "data": {
                "action": "update",
                "file_path": file_path,
                "chunks": count
            },
            "timestamp": datetime.now().isoformat()
        })
        
        return ApiResponse(
            status="success",
            message=f"更新成功: {file_path} ({count} chunks)"
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.post("/api/sync")
async def sync_documents():
    """同步本地文件和向量库"""
    try:
        # 获取本地文档
        local_docs = get_local_documents()
        
        # 获取向量库文档
        repo = await get_repository()
        vector_docs = repo.list_documents()
        vector_paths = {d["source"] for d in vector_docs}
        
        # 计算差异
        new_docs = [d for d in local_docs if d not in vector_paths]
        deleted_docs = [d for d in vector_paths if d not in local_docs]
        
        # 执行同步
        added = 0
        deleted = 0
        
        # 添加新文档
        for doc_path in new_docs:
            try:
                full_path = ROOT / doc_path
                text = full_path.read_text(encoding="utf-8")
                doc_name = full_path.stem
                text = f"[文件名: {doc_name}]\n{text}"
                
                chunk_cfg = get_chunk_config()
                doc = {"path": doc_path, "text": text}
                count = repo.add(doc, chunk_cfg)
                added += 1
            except Exception as e:
                logger.error(f"添加文档失败: {doc_path} ({e})")
        
        # 删除已删文档
        for doc_path in deleted_docs:
            try:
                repo.delete(doc_path)
                deleted += 1
            except Exception as e:
                logger.error(f"删除文档失败: {doc_path} ({e})")
        
        # 广播同步完成
        await manager.broadcast({
            "type": "document",
            "data": {
                "action": "sync",
                "added": added,
                "deleted": deleted
            },
            "timestamp": datetime.now().isoformat()
        })
        
        return ApiResponse(
            status="success",
            data={"added": added, "deleted": deleted},
            message=f"同步完成: 添加 {added} 个，删除 {deleted} 个"
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.post("/api/rebuild")
async def rebuild_database():
    """全量重建向量库"""
    try:
        # 广播重建开始
        await manager.broadcast({
            "type": "progress",
            "data": {
                "operation": "rebuild",
                "status": "started"
            },
            "timestamp": datetime.now().isoformat()
        })
        
        # 执行全量重建
        collection_name = get_active_collection_name()
        chunk_cfg = get_chunk_config()
        
        # 连接 ChromaDB
        client = await get_chroma_client()
        
        # 删除旧集合
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
        
        # 加载文档
        docs_dir = ROOT / "data" / "docs"
        documents = load_all_documents(docs_dir)
        
        # 获取 Embedding 代理
        emb_proxy = get_lm_proxy()
        
        # 全量重建
        count = build_full(collection_name, client, documents, emb_proxy, chunk_cfg)
        
        # 广播重建完成
        await manager.broadcast({
            "type": "progress",
            "data": {
                "operation": "rebuild",
                "status": "completed",
                "total": count
            },
            "timestamp": datetime.now().isoformat()
        })
        
        return ApiResponse(
            status="success",
            data={"total": count},
            message=f"全量重建完成: {count} 个 chunks"
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.post("/api/search")
async def search_knowledge_base(request: SearchRequest):
    """搜索知识库"""
    try:
        # 这里需要调用 MCP 的搜索逻辑
        # 暂时返回模拟结果
        return ApiResponse(
            status="success",
            data={
                "query": request.query,
                "results": []
            }
        )
    except Exception as e:
        return ApiResponse(status="error", message=str(e))

@app.get("/api/health")
async def health_check():
    """健康检查"""
    try:
        # 检查 ChromaDB
        client = await get_chroma_client()
        client.heartbeat()
        chromadb_status = "online"
    except Exception:
        chromadb_status = "offline"
    
    # 检查 Embedding 服务
    try:
        import httpx
        embedding_url = os.getenv("EMBEDDING_API_URL", "http://127.0.0.1:5000")
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{embedding_url}/models")
            embedding_status = "online" if r.status_code == 200 else "offline"
    except Exception:
        embedding_status = "offline"
    
    return ApiResponse(
        status="success",
        data={
            "chromadb": {"status": chromadb_status},
            "embedding": {"status": embedding_status}
        }
    )

# 挂载前端静态文件
frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dist)), name="static")
    
    @app.get("/")
    async def index():
        return FileResponse(str(frontend_dist / "index.html"))

def main():
    """主函数"""
    logger.info("Ezy-RAG API Server V0.0.14 启动中...")
    logger.info(f"ChromaDB Server: {os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}")
    logger.info(f"Embedding 服务: {os.getenv('EMBEDDING_API_URL', 'http://127.0.0.1:5000')}")
    logger.info(f"监听: http://{os.getenv('MCP_SERVER_HOST', '127.0.0.1')}:9767")
    logger.info(f"API 文档: http://{os.getenv('MCP_SERVER_HOST', '127.0.0.1')}:9767/docs")
    
    uvicorn.run(
        app,
        host=os.getenv("MCP_SERVER_HOST", "127.0.0.1"),
        port=9767,
        log_level="info",
    )

if __name__ == "__main__":
    main()
