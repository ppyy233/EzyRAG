# -*- coding: utf-8 -*-
"""
Ezy-RAG — 本地 Rerank HTTP 服务
加载 cross-encoder 模型，暴露 POST /rerank 接口

用法:
  python -m servers.rerank                # 默认 127.0.0.1:5001
  python -m servers.rerank --port 5002    # 自定义端口
  python -m servers.rerank --model BAAI/bge-reranker-v2-m3  # 指定模型

接口:
  POST /rerank  {"query": "...", "documents": ["...", ...]}
  返回:          {"scores": [0.87, 0.32, ...]}
"""
import os
import sys
import argparse
import logging
from pathlib import Path

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
        logging.FileHandler(LOG_DIR / "rerank.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("RerankServer")

app = FastAPI(title="Ezy-RAG Rerank Server", version="0.0.18")

_model = None


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
    global _model
    
    # 优先使用传入的模型路径，否则从环境变量读取
    load_path = model_path or os.getenv("RERANK_LOCAL_MODEL_PATH", "")
    
    if not load_path:
        logger.error("未指定模型路径，请设置 RERANK_LOCAL_MODEL_PATH 或使用 --model-path 参数")
        sys.exit(1)
    
    # 将相对路径转换为绝对路径
    model_dir = Path(load_path)
    if not model_dir.is_absolute():
        model_dir = ROOT / model_dir
    load_path = str(model_dir)
    
    # 检查模型文件是否存在
    if not model_dir.exists():
        logger.error(f"模型目录不存在: {model_dir}")
        logger.info(f"请下载模型文件到: {model_dir}")
        sys.exit(1)
    
    config_file = model_dir / "config.json"
    if not config_file.exists():
        logger.error(f"模型配置文件不存在: {config_file}")
        logger.info(f"请确保模型文件完整")
        sys.exit(1)
    
    logger.info(f"加载重排模型: {load_path}")
    from sentence_transformers import CrossEncoder
    device = detect_device()
    _model = CrossEncoder(load_path, device=device, trust_remote_code=True)
    logger.info("重排模型就绪")


class RerankRequest(BaseModel):
    query: str
    documents: list[str]


@app.post("/rerank")
async def rerank(req: RerankRequest):
    if _model is None:
        return JSONResponse({"error": "模型未加载"}, status_code=503)
    try:
        pairs = [(req.query, doc) for doc in req.documents]
        raw_scores = _model.predict(pairs, show_progress_bar=False)
        scores = [float(s) for s in raw_scores]
        return {"scores": scores}
    except Exception as e:
        logger.error(f"重排失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


def main():
    parser = argparse.ArgumentParser(description="Ezy-RAG 本地 Rerank 服务")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--model-path", type=str, default=None, help="模型路径")
    args = parser.parse_args()

    load_model(args.model_path)
    logger.info(f"Rerank Server 启动: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
