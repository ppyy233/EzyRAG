# -*- coding: utf-8 -*-
"""
QwenKB — 本地 BGE Rerank HTTP 服务
加载 BGE cross-encoder 模型，暴露 POST /rerank 接口

用法:
  python rerank_server.py              # 默认 127.0.0.1:5001
  python rerank_server.py --port 5002  # 自定义端口

接口:
  POST /rerank  {"query": "...", "documents": ["...", ...]}
  返回:          {"scores": [0.87, 0.32, ...]}
"""
import os
import sys
import argparse
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RerankServer")

app = FastAPI(title="QwenKB Rerank Server", version="1.0.0")

_model = None


def load_model(model_name: str = None):
    global _model
    import os as _os
    if model_name is None:
        model_name = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "models", "bge-reranker")
    logger.info(f"加载重排模型: {model_name}")
    from sentence_transformers import CrossEncoder
    _model = CrossEncoder(model_name, trust_remote_code=True)
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
    parser = argparse.ArgumentParser(description="QwenKB 本地 Rerank 服务")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--model", type=str, default=None)
    args = parser.parse_args()

    load_model(args.model)
    logger.info(f"Rerank Server 启动: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
