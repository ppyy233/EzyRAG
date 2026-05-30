# -*- coding: utf-8 -*-
"""
Ezy-RAG 鈥?鏈湴 Embedding HTTP 鏈嶅姟
鍔犺浇 sentence-transformers 妯″瀷锛屾毚闇?OpenAI 鍏煎鐨?API 绔偣

鐢ㄦ硶:
  python -m servers.embedding                # 榛樿 127.0.0.1:1234
  python -m servers.embedding --port 1235    # 鑷畾涔夌鍙?
  python -m servers.embedding --model BAAI/bge-large-zh-v1.5  # 鎸囧畾妯″瀷

鎺ュ彛:
  POST /v1/embeddings  {"input": "...", "model": "...", "dimensions": 1024}
  杩斿洖:                {"data": [{"embedding": [...]}]}

鏀寔鐨勬ā鍨?
  - BAAI/bge-large-zh-v1.5 (1024缁?
  - BAAI/bge-large-en-v1.5 (1024缁?
  - BAAI/bge-m3 (1024缁?
  - text-embedding-qwen3-embedding-4b (2560缁?
  - 鍏朵粬 sentence-transformers 妯″瀷
"""
import os
import sys
import gc
import time
import argparse
import logging
from pathlib import Path
from typing import Union

import torch

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
        logging.FileHandler(LOG_DIR / "embedding.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("EmbeddingServer")

app = FastAPI(title="Ezy-RAG Embedding Server", version="1.0.0")

_model = None
_model_name = None


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
    global _model, _model_name
    
    # 浼樺厛浣跨敤浼犲叆鐨勬ā鍨嬭矾寰勶紝鍚﹀垯浠庣幆澧冨彉閲忚鍙?
    load_path = model_path or os.getenv("EMBEDDING_LOCAL_MODEL_PATH", "")
    
    if not load_path:
        logger.error("鏈寚瀹氭ā鍨嬭矾寰勶紝璇疯缃?EMBEDDING_LOCAL_MODEL_PATH 鎴栦娇鐢?--model-path 鍙傛暟")
        sys.exit(1)
    
    # 灏嗙浉瀵硅矾寰勮浆鎹负缁濆璺緞
    model_dir = Path(load_path)
    if not model_dir.is_absolute():
        model_dir = ROOT / model_dir
    load_path = str(model_dir)
    
    logger.info(f"鍔犺浇 Embedding 妯″瀷: {load_path}")
    from sentence_transformers import SentenceTransformer
    device = detect_device()
    _model = SentenceTransformer(load_path, device=device, trust_remote_code=True)
    _model_name = load_path
    
    # 鑾峰彇妯″瀷缁村害
    test_embedding = _model.encode(["test"], show_progress_bar=False)
    dim = len(test_embedding[0])
    logger.info(f"Embedding 妯″瀷灏辩华 (缁村害: {dim})")


class EmbeddingRequest(BaseModel):
    input: Union[str, list[str]]
    model: str = None
    encoding_format: str = "float"
    dimensions: int = None


@app.get("/v1/models")
async def list_models():
    """OpenAI 鍏煎鐨勬ā鍨嬪垪琛ㄧ鐐?""
    return {
        "object": "list",
        "data": [{
            "id": _model_name or "unknown",
            "object": "model",
            "owned_by": "local",
        }],
    }


@app.get("/health")
async def health():
    """鍋ュ悍妫€鏌ョ鐐?""
    return {"status": "ok", "model": "loaded" if _model else "not_loaded"}


@app.post("/v1/embeddings")
async def create_embeddings(req: EmbeddingRequest):
    if _model is None:
        return JSONResponse({"error": "妯″瀷鏈姞杞?}, status_code=503)
    
    t0 = time.time()
    try:
        texts = req.input if isinstance(req.input, list) else [req.input]
        
        # 閫愭潯澶勭悊锛岄伩鍏嶅ぇ鎵归噺瀵艰嚧鏄惧瓨鐖嗙偢
        all_embeddings = []
        for text in texts:
            with torch.no_grad():
                emb = _model.encode([text], show_progress_bar=False)
            all_embeddings.append(emb[0])
        
        # 杞负 Python list锛岄噴鏀?GPU 寮犻噺
        if req.dimensions is not None:
            target_dim = req.dimensions
            result = []
            for emb in all_embeddings:
                if len(emb) > target_dim:
                    result.append(emb[:target_dim].tolist())
                elif len(emb) < target_dim:
                    result.append(emb.tolist() + [0.0] * (target_dim - len(emb)))
                else:
                    result.append(emb.tolist())
        else:
            result = [emb.tolist() for emb in all_embeddings]
        
        del all_embeddings
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        
        elapsed = time.time() - t0
        total_chars = sum(len(t) for t in texts)
        vram = "N/A"
        if torch.cuda.is_available():
            vram_mb = torch.cuda.memory_allocated() // 1024 // 1024
            vram = f"{vram_mb} MiB"
        logger.info(f"embed: {len(texts)} texts, {total_chars} chars, {elapsed:.2f}s, VRAM={vram}")
        
        return {
            "object": "list",
            "model": _model_name,
            "data": [
                {
                    "object": "embedding",
                    "embedding": emb,
                    "index": i
                }
                for i, emb in enumerate(result)
            ],
            "usage": {
                "prompt_tokens": sum(len(t.split()) for t in texts),
                "completion_tokens": 0,
                "total_tokens": sum(len(t.split()) for t in texts)
            }
        }
    except Exception as e:
        logger.error(f"Embedding 澶辫触: {e}")
        # 寮傚父鏃朵篃娓呯悊GPU缂撳瓨
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        return JSONResponse({"error": str(e)}, status_code=500)


def main():
    parser = argparse.ArgumentParser(description="Ezy-RAG 鏈湴 Embedding 鏈嶅姟")
    parser.add_argument("--port", type=int, default=1234)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--model-path", type=str, default=None, help="妯″瀷璺緞")
    args = parser.parse_args()
    
    load_model(args.model_path)
    logger.info(f"Embedding Server 鍚姩: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
