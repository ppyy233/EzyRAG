# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 — 配置加载模块
位于 config/ 目录下，负责加载 .env 和 config.json
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 配置文件路径
CONFIG_DIR = Path(__file__).parent
ENV_FILE = CONFIG_DIR / ".env"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 加载 .env
if not ENV_FILE.exists():
    raise FileNotFoundError(f"配置文件 {ENV_FILE} 不存在，请运行: python init.py")
load_dotenv(ENV_FILE)

# 加载 config.json
if not CONFIG_FILE.exists():
    raise FileNotFoundError(f"配置文件 {CONFIG_FILE} 不存在，请运行: python init.py")


def load_config() -> dict:
    """加载 config.json"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(config: dict):
    """保存 config.json"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_collection_name() -> str:
    """获取集合名称"""
    config = load_config()
    return config["collection"]["name"]


def get_docs_dir() -> str:
    """获取文档目录"""
    config = load_config()
    return config["docs"]["dir"]


def get_web_dir() -> str:
    """获取网页数据目录"""
    config = load_config()
    return config.get("web", {}).get("dir", "data/web")


def get_chroma_dir() -> str:
    """获取 ChromaDB 数据目录"""
    config = load_config()
    return config["chroma"]["dir"]


def get_chunk_config(template_name: str = None) -> dict:
    """获取切片模板配置"""
    config = load_config()
    default_template = config["chunk"]["default_template"]
    name = template_name or os.getenv("CHUNK_TEMPLATE", default_template)

    if name not in config["chunk"]["templates"]:
        name = default_template

    return config["chunk"]["templates"][name]


def get_chunk_templates() -> dict:
    """获取所有切片模板"""
    config = load_config()
    return config["chunk"]["templates"]


def get_retrieval_config() -> dict:
    """获取检索配置"""
    config = load_config()
    return config["retrieval"]


def get_embedding_mode() -> str:
    """获取 Embedding 模式：local / cloud"""
    return os.getenv("EMBEDDING_MODE", "cloud").lower()


def get_embedding_config() -> dict:
    """获取 Embedding 配置"""
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
    """获取 Rerank 模式：local / cloud"""
    return os.getenv("RERANK_MODE", "cloud").lower()


def get_rerank_enabled() -> bool:
    """获取 Rerank 是否启用"""
    return os.getenv("RERANK_ENABLED", "true").lower() == "true"


def get_rerank_config() -> dict:
    """获取 Rerank 配置"""
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
