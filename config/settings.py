# -*- coding: utf-8 -*-
"""
Ezy-RAG 鈥?閰嶇疆鍔犺浇妯″潡
浣嶄簬 config/ 鐩綍涓嬶紝璐熻矗鍔犺浇 .env 鍜?config.json
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 閰嶇疆鏂囦欢璺緞
CONFIG_DIR = Path(__file__).parent
ENV_FILE = CONFIG_DIR / ".env"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 鍔犺浇 .env
if not ENV_FILE.exists():
    raise FileNotFoundError(f"閰嶇疆鏂囦欢 {ENV_FILE} 涓嶅瓨鍦紝璇疯繍琛? python init.py")
load_dotenv(ENV_FILE)

# 鍔犺浇 config.json
if not CONFIG_FILE.exists():
    raise FileNotFoundError(f"閰嶇疆鏂囦欢 {CONFIG_FILE} 涓嶅瓨鍦紝璇疯繍琛? python init.py")


def load_config() -> dict:
    """鍔犺浇 config.json"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(config: dict):
    """淇濆瓨 config.json"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_collection_name() -> str:
    """鑾峰彇闆嗗悎鍚嶇О"""
    config = load_config()
    return config["collection"]["name"]


def get_docs_dir() -> str:
    """鑾峰彇鏂囨。鐩綍"""
    config = load_config()
    return config["docs"]["dir"]


def get_web_dir() -> str:
    """鑾峰彇缃戦〉鏁版嵁鐩綍"""
    config = load_config()
    return config.get("web", {}).get("dir", "data/web")


def get_chroma_dir() -> str:
    """鑾峰彇 ChromaDB 鏁版嵁鐩綍"""
    config = load_config()
    return config["chroma"]["dir"]


def get_chunk_config(template_name: str = None) -> dict:
    """鑾峰彇鍒囩墖妯℃澘閰嶇疆"""
    config = load_config()
    default_template = config["chunk"]["default_template"]
    name = template_name or os.getenv("CHUNK_TEMPLATE", default_template)

    if name not in config["chunk"]["templates"]:
        name = default_template

    return config["chunk"]["templates"][name]


def get_chunk_templates() -> dict:
    """鑾峰彇鎵€鏈夊垏鐗囨ā鏉?""
    config = load_config()
    return config["chunk"]["templates"]


def get_hnsw_config() -> dict:
    """鑾峰彇 HNSW 绱㈠紩閰嶇疆"""
    config = load_config()
    defaults = {
        "space": "cosine",
        "ef_construction": 100,
        "ef_search": 100,
        "max_neighbors": 16,
        "sync_threshold": 1000,
        "batch_size": 100,
    }
    hnsw = config.get("hnsw", {})
    # 鍚堝苟榛樿鍊?
    for key, value in defaults.items():
        if key not in hnsw:
            hnsw[key] = value
    return hnsw


def get_retrieval_config() -> dict:
    """鑾峰彇妫€绱㈤厤缃?""
    config = load_config()
    return config["retrieval"]


def get_embedding_mode() -> str:
    """鑾峰彇 Embedding 妯″紡锛歭ocal / cloud"""
    return os.getenv("EMBEDDING_MODE", "cloud").lower()


def get_embedding_config() -> dict:
    """鑾峰彇 Embedding 閰嶇疆"""
    mode = get_embedding_mode()

    if mode == "local":
        dim_str = os.getenv("EMBEDDING_LOCAL_DIM", "")
        dim = int(dim_str) if dim_str and dim_str.strip() else None
        return {
            "mode": "local",
            "url": os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings"),
            "model": os.getenv("EMBEDDING_LOCAL_MODEL", "text-embedding-qwen3-embedding-4b"),
            "dim": dim,
        }
    else:
        dim_str = os.getenv("EMBEDDING_CLOUD_DIM", "")
        dim = int(dim_str) if dim_str and dim_str.strip() else None
        return {
            "mode": "cloud",
            "provider": os.getenv("EMBEDDING_CLOUD_PROVIDER", "siliconflow"),
            "api_key": os.getenv("EMBEDDING_CLOUD_API_KEY", ""),
            "model": os.getenv("EMBEDDING_CLOUD_MODEL", "BAAI/bge-m3"),
            "dim": dim,
            "url": os.getenv("EMBEDDING_CLOUD_URL", ""),
        }


def get_rerank_mode() -> str:
    """鑾峰彇 Rerank 妯″紡锛歭ocal / cloud"""
    return os.getenv("RERANK_MODE", "cloud").lower()


def get_rerank_enabled() -> bool:
    """鑾峰彇 Rerank 鏄惁鍚敤"""
    return os.getenv("RERANK_ENABLED", "true").lower() == "true"


def get_rerank_config() -> dict:
    """鑾峰彇 Rerank 閰嶇疆"""
    mode = get_rerank_mode()

    if mode == "local":
        return {
            "mode": "local",
            "url": os.getenv("RERANK_LOCAL_URL", "http://127.0.0.1:5001"),
        }
    else:
        return {
            "mode": "cloud",
            "provider": os.getenv("RERANK_CLOUD_PROVIDER", "cohere"),
            "api_key": os.getenv("RERANK_CLOUD_API_KEY", ""),
            "model": os.getenv("RERANK_CLOUD_MODEL", "rerank-multilingual-v3.0"),
            "url": os.getenv("RERANK_CLOUD_URL", ""),
        }
