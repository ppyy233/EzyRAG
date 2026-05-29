# -*- coding: utf-8 -*-
"""
Ezy-RAG — 本地 Embedding HTTP 服务
加载 sentence-transformers 模型，暴露 OpenAI 兼容的 API 端点

用法:
  python -m servers.embedding                # 默认 127.0.0.1:1234
  python -m servers.embedding --port 1235    # 自定义端口
  python -m servers.embedding --model BAAI/bge-large-zh-v1.5  # 指定模型

接口:
  POST /v1/embeddings  {"input": "...", "model": "...", "dimensions": 1024}
  返回:                {"data": [{"embedding": [...]}]}

支持的模型:
  - BAAI/bge-large-zh-v1.5 (1024维)
  - BAAI/bge-large-en-v1.5 (1024维)
  - BAAI/bge-m3 (1024维)
  - text-embedding-qwen3-embedding-4b (2560维)
  - 其他 sentence-transformers 模型
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Union

import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 加载环境变量（导入config.settings会自动加载.env）
import config.settings  # noqa: F401

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

LOG_DIR = ROOT / "runtime" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "embedding.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("EmbeddingServer")

app = FastAPI(title="Ezy-RAG Embedding Server", version="0.0.18")

_model = None
_model_name = None


def detect_device():
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            logger.info(f"检测到 GPU: {name}")
            return "cuda"
    except ImportError:
        pass
    logger.info("使用 CPU")
    return "cpu"


def load_model(model_path: str = None):
    global _model, _model_name
    
    # 优先使用传入的模型路径，否则从环境变量读取
    load_path = model_path or os.getenv("EMBEDDING_LOCAL_MODEL_PATH", "")
    
    if not load_path:
        logger.error("未指定模型路径，请设置 EMBEDDING_LOCAL_MODEL_PATH 或使用 --model-path 参数")
        sys.exit(1)
    
    # 将相对路径转换为绝对路径
    model_dir = Path(load_path)
    if not model_dir.is_absolute():
        model_dir = ROOT / model_dir
    load_path = str(model_dir)
    
    logger.info(f"加载 Embedding 模型: {load_path}")
    from sentence_transformers import SentenceTransformer
    device = detect_device()
    _model = SentenceTransformer(load_path, device=device, trust_remote_code=True)
    _model_name = load_path
    
    # 获取模型维度
    test_embedding = _model.encode(["test"], show_progress_bar=False)
    dim = len(test_embedding[0])
    logger.info(f"Embedding 模型就绪 (维度: {dim})")


class EmbeddingRequest(BaseModel):
    input: Union[str, list[str]]
    model: str = None
    encoding_format: str = "float"
    dimensions: int = None


@app.post("/v1/embeddings")
async def create_embeddings(req: EmbeddingRequest):
    if _model is None:
        return JSONResponse({"error": "模型未加载"}, status_code=503)
    
    try:
        texts = req.input if isinstance(req.input, list) else [req.input]
        
        # 生成 embedding（使用no_grad避免保存梯度，减少显存占用）
        with torch.no_grad():
            embeddings = _model.encode(texts, show_progress_bar=False)
        
        # 如果指定了维度，调整维度
        if req.dimensions is not None:
            target_dim = req.dimensions
            adjusted_embeddings = []
            for emb in embeddings:
                if len(emb) > target_dim:
                    adjusted_embeddings.append(emb[:target_dim].tolist())
                elif len(emb) < target_dim:
                    adjusted_embeddings.append(emb.tolist() + [0.0] * (target_dim - len(emb)))
                else:
                    adjusted_embeddings.append(emb.tolist())
            embeddings = adjusted_embeddings
        else:
            embeddings = [emb.tolist() for emb in embeddings]
        
        # 清理GPU缓存，防止显存泄漏
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return {
            "object": "list",
            "model": _model_name,
            "data": [
                {
                    "object": "embedding",
                    "embedding": emb,
                    "index": i
                }
                for i, emb in enumerate(embeddings)
            ],
            "usage": {
                "prompt_tokens": sum(len(t.split()) for t in texts),
                "completion_tokens": 0,
                "total_tokens": sum(len(t.split()) for t in texts)
            }
        }
    except Exception as e:
        logger.error(f"Embedding 失败: {e}")
        # 异常时也清理GPU缓存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return JSONResponse({"error": str(e)}, status_code=500)


def main():
    parser = argparse.ArgumentParser(description="Ezy-RAG 本地 Embedding 服务")
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--model-path", type=str, default=None, help="模型路径")
    args = parser.parse_args()
    
    load_model(args.model_path)
    logger.info(f"Embedding Server 启动: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
