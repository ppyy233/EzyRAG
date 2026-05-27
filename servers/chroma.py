# -*- coding: utf-8 -*-
"""
QwenKB — ChromaDB Server 启动脚本
用法: python -m servers.chroma
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import config
import uvicorn
from chromadb.server.fastapi import FastAPI
from chromadb.config import Settings

s = Settings(
    chroma_server_host=config.CHROMA_SERVER_HOST,
    chroma_server_http_port=config.CHROMA_SERVER_PORT,
    persist_directory=str(ROOT / config.CHROMA_DIR),
    is_persistent=True,
    anonymized_telemetry=False,
)
server = FastAPI(s)
app = server.app()

if __name__ == "__main__":
    uvicorn.run(app, host=config.CHROMA_SERVER_HOST, port=config.CHROMA_SERVER_PORT)
