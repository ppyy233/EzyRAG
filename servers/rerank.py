# -*- coding: utf-8 -*-
"""
Ezy-RAG 鈥?鏈湴 Rerank HTTP 鏈嶅姟
鍔犺浇 cross-encoder 妯″瀷锛屾毚闇?POST /rerank 鎺ュ彛

鐢ㄦ硶:
  python -m servers.rerank                # 榛樿 127.0.0.1:5001
  python -m servers.rerank --port 5002    # 鑷畾涔夌鍙?
  python -m servers.rerank --model BAAI/bge-reranker-v2-m3  # 鎸囧畾妯″瀷

鎺ュ彛:
  POST /rerank  {"query": "...", "documents": ["...", ...]}
  杩斿洖:          {"scores": [0.87, 0.32, ...]}
"""
import os
import sys
import time
import argparse
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 鍔犺浇鐜鍙橀噺锛堝鍏onfig.settings浼氳嚜鍔ㄥ姞杞?env锛?
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

app = FastAPI(title="Ezy-RAG Rerank Server", version="1.0.0")

_model = None


def detect_device():
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            logger.info(f"妫€娴嬪埌 GPU: {name}")
            return "cuda"
    except ImportError:
        pass
    logger.info("浣跨敤 CPU")
    return "cpu"


def load_model(model_path: str = None):
    global _model
    
    # 浼樺厛浣跨敤浼犲叆鐨勬ā鍨嬭矾寰勶紝鍚﹀垯浠庣幆澧冨彉閲忚鍙?
    load_path = model_path or os.getenv("RERANK_LOCAL_MODEL_PATH", "")
    
    if not load_path:
        logger.error("鏈寚瀹氭ā鍨嬭矾寰勶紝璇疯缃?RERANK_LOCAL_MODEL_PATH 鎴栦娇鐢?--model-path 鍙傛暟")
        sys.exit(1)
    
    # 灏嗙浉瀵硅矾寰勮浆鎹负缁濆璺緞
    model_dir = Path(load_path)
    if not model_dir.is_absolute():
        model_dir = ROOT / model_dir
    load_path = str(model_dir)
    
    # 妫€鏌ユā鍨嬫枃浠舵槸鍚﹀瓨鍦?
    if not model_dir.exists():
        logger.error(f"妯″瀷鐩綍涓嶅瓨鍦? {model_dir}")
        logger.info(f"璇蜂笅杞芥ā鍨嬫枃浠跺埌: {model_dir}")
        sys.exit(1)
    
    config_file = model_dir / "config.json"
    if not config_file.exists():
        logger.error(f"妯″瀷閰嶇疆鏂囦欢涓嶅瓨鍦? {config_file}")
        logger.info(f"璇风‘淇濇ā鍨嬫枃浠跺畬鏁?)
        sys.exit(1)
    
    logger.info(f"鍔犺浇閲嶆帓妯″瀷: {load_path}")
    from sentence_transformers import CrossEncoder
    device = detect_device()
    _model = CrossEncoder(load_path, device=device, trust_remote_code=True)
    logger.info("閲嶆帓妯″瀷灏辩华")


class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    model: str = None
    top_n: int = None


@app.get("/health")
async def health():
    """鍋ュ悍妫€鏌ョ鐐?""
    return {"status": "ok", "model": "loaded" if _model else "not_loaded"}


@app.post("/rerank")
async def rerank(req: RerankRequest):
    """鏈湴 rerank锛堝吋瀹规棫璺緞锛?""
    return await _do_rerank(req)


@app.post("/v1/rerank")
async def rerank_v1(req: RerankRequest):
    """OpenAI 鍏煎鐨?rerank 绔偣锛堝绉?embedding 鐨?/v1/embeddings锛?""
    return await _do_rerank(req)


async def _do_rerank(req: RerankRequest):
    """缁熶竴鐨?rerank 閫昏緫锛岃繑鍥炴牸寮忓榻愪簯绔?API"""
    if _model is None:
        return JSONResponse({"error": "妯″瀷鏈姞杞?}, status_code=503)
    t0 = time.time()
    try:
        pairs = [(req.query, doc) for doc in req.documents]
        raw_scores = _model.predict(pairs, show_progress_bar=False)

        # 鎸夊垎鏁版帓搴忥紝鍙?top_n
        indexed_scores = sorted(enumerate(raw_scores), key=lambda x: x[1], reverse=True)
        if req.top_n is not None:
            indexed_scores = indexed_scores[:req.top_n]

        # 杩斿洖鏍煎紡瀵归綈浜戠 API锛圫iliconFlow/Cohere 鏍煎紡锛?
        results = [
            {"index": idx, "relevance_score": float(score)}
            for idx, score in indexed_scores
        ]
        elapsed = time.time() - t0
        logger.info(f"rerank: {len(req.documents)} docs, {elapsed:.2f}s")
        return {"results": results}
    except Exception as e:
        elapsed = time.time() - t0
        logger.error(f"rerank failed: {e}, {elapsed:.2f}s")
        return JSONResponse({"error": str(e)}, status_code=500)


def main():
    parser = argparse.ArgumentParser(description="Ezy-RAG 鏈湴 Rerank 鏈嶅姟")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--model-path", type=str, default=None, help="妯″瀷璺緞")
    args = parser.parse_args()

    load_model(args.model_path)
    logger.info(f"Rerank Server 鍚姩: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
