# -*- coding: utf-8 -*-
"""
Ezy-RAG — 配置加载模块
只负责加载 .env 文件，不定义任何配置变量
各模块通过 os.getenv() 直接读取环境变量
"""
from pathlib import Path
from dotenv import load_dotenv

# 自动初始化 .env
env_file = Path(__file__).parent / ".env"
if not env_file.exists():
    raise FileNotFoundError(
        f"配置文件 {env_file} 不存在，请运行: python init.py"
    )

load_dotenv(env_file)
