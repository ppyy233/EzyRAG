# -*- coding: utf-8 -*-
"""
Ezy-RAG V1.0.0 — 配置加载模块
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


def load_env() -> dict:
    """加载 .env 文件为字典"""
    env = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env[key.strip()] = value.strip()
    return env


def save_env(env: dict):
    """保存字典到 .env 文件"""
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write("# Ezy-RAG 环境配置\n\n")
        for key in ["EMBEDDING_API_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "EMBEDDING_DIM"]:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")
        for key in ["RERANK_ENABLED", "RERANK_API_URL", "RERANK_API_KEY", "RERANK_MODEL"]:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")
        for key in ["CHROMA_SERVER_HOST", "CHROMA_SERVER_PORT"]:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")
        for key in ["MCP_SERVER_HOST", "MCP_SERVER_PORT"]:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")
        f.write(f"CHUNK_TEMPLATE={env.get('CHUNK_TEMPLATE', 'academic')}\n")
