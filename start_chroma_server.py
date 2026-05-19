import os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import config
import uvicorn
from chromadb.server.fastapi import FastAPI
from chromadb.config import Settings

s = Settings(
    chroma_server_host=config.CHROMA_SERVER_HOST,
    chroma_server_http_port=config.CHROMA_SERVER_PORT,
    persist_directory=os.path.join(ROOT, config.CHROMA_DIR),
    is_persistent=True,
    anonymized_telemetry=False,
)
server = FastAPI(s)
app = server.app()
uvicorn.run(app, host=config.CHROMA_SERVER_HOST, port=config.CHROMA_SERVER_PORT)
