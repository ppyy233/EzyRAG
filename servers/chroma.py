# -*- coding: utf-8 -*-
"""
Ezy-RAG V1.0.0 — ChromaDB Server 启动脚本
用法: python -m servers.chroma
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from config.settings import get_chroma_dir
import uvicorn
from chromadb.server.fastapi import FastAPI
from chromadb.config import Settings

# 从配置文件读取
CHROMA_DIR = get_chroma_dir()

s = Settings(
    chroma_server_host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
    chroma_server_http_port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
    persist_directory=str(ROOT / CHROMA_DIR),
    is_persistent=True,
    anonymized_telemetry=False,
)
server = FastAPI(s)
app = server.app()

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"), port=int(os.getenv("CHROMA_SERVER_PORT", "9898")))
