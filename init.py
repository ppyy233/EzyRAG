# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 — 配置管理脚本
用法: python init.py
"""
import os
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG_DIR = ROOT / "config"
ENV_FILE = CONFIG_DIR / ".env"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_env() -> dict:
    """加载 .env 文件"""
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
    """保存 .env 文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write("# ============================================================\n")
        f.write("# Ezy-RAG V0.0.17 — 环境配置\n")
        f.write("# 由 init.py 生成\n")
        f.write("# ============================================================\n\n")

        # Embedding 模型配置
        f.write("# ----- Embedding 模型配置 -----\n")
        f.write("# 模式：local（本地 LM Studio/Ollama）/ cloud（云端 API）\n")
        f.write(f"EMBEDDING_MODE={env.get('EMBEDDING_MODE', 'cloud')}\n\n")

        f.write("# 云端模式配置（openai/siliconflow/deepseek/zhipu/moonshot/custom）\n")
        cloud_embedding = {
            "EMBEDDING_CLOUD_PROVIDER": "siliconflow",
            "EMBEDDING_CLOUD_API_KEY": "",
            "EMBEDDING_CLOUD_MODEL": "BAAI/bge-m3",
            "EMBEDDING_CLOUD_DIM": "1024",
            "EMBEDDING_CLOUD_URL": ""
        }
        for key, default in cloud_embedding.items():
            f.write(f"{key}={env.get(key, default)}\n")

        f.write("\n# 本地模式配置（LM Studio/Ollama 等）\n")
        local_embedding = {
            "EMBEDDING_LOCAL_URL": "http://127.0.0.1:1234/v1/embeddings",
            "EMBEDDING_LOCAL_MODEL": "text-embedding-qwen3-embedding-4b",
            "EMBEDDING_LOCAL_DIM": "2560"
        }
        for key, default in local_embedding.items():
            f.write(f"{key}={env.get(key, default)}\n")
        f.write("\n")

        # Rerank 模型配置
        f.write("# ----- Rerank 模型配置 -----\n")
        f.write("# 是否启用 Rerank\n")
        f.write(f"RERANK_ENABLED={env.get('RERANK_ENABLED', 'true')}\n\n")

        f.write("# 模式：local（本地 CrossEncoder）/ cloud（云端 API）\n")
        f.write(f"RERANK_MODE={env.get('RERANK_MODE', 'cloud')}\n\n")

        f.write("# 云端模式配置（cohere/jina/custom）\n")
        cloud_rerank = {
            "RERANK_CLOUD_PROVIDER": "cohere",
            "RERANK_CLOUD_API_KEY": "",
            "RERANK_CLOUD_MODEL": "rerank-multilingual-v3.0",
            "RERANK_CLOUD_URL": ""
        }
        for key, default in cloud_rerank.items():
            f.write(f"{key}={env.get(key, default)}\n")

        f.write("\n# 本地模式配置\n")
        local_rerank = {
            "RERANK_LOCAL_URL": "http://127.0.0.1:5001"
        }
        for key, default in local_rerank.items():
            f.write(f"{key}={env.get(key, default)}\n")
        f.write("\n")

        # ChromaDB 服务配置
        f.write("# ----- ChromaDB 服务配置 -----\n")
        chroma_defaults = {
            "CHROMA_SERVER_HOST": "127.0.0.1",
            "CHROMA_SERVER_PORT": "9898"
        }
        for key, default in chroma_defaults.items():
            f.write(f"{key}={env.get(key, default)}\n")
        f.write("\n")

        # MCP 服务配置
        f.write("# ----- MCP 服务配置 -----\n")
        mcp_defaults = {
            "MCP_SERVER_HOST": "127.0.0.1",
            "MCP_SERVER_PORT": "9766"
        }
        for key, default in mcp_defaults.items():
            f.write(f"{key}={env.get(key, default)}\n")
        f.write("\n")

        # 切块策略
        f.write("# ----- 切块策略 -----\n")
        f.write(f"CHUNK_TEMPLATE={env.get('CHUNK_TEMPLATE', 'academic')}\n")


def load_config() -> dict:
    """加载 config.json 文件"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    """保存 config.json 文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def show_env():
    """显示 .env 配置"""
    env = load_env()
    print("\n当前 .env 配置：")
    print("-" * 60)
    for key, value in env.items():
        if "KEY" in key and value:
            print(f"{key}=****")
        else:
            print(f"{key}={value}")


def show_config():
    """显示 config.json 配置"""
    config = load_config()
    print("\n当前 config.json 配置：")
    print("-" * 60)
    print(json.dumps(config, ensure_ascii=False, indent=2))


def update_env():
    """更新 .env 配置"""
    env = load_env()

    print("\n可修改的 .env 配置项：")
    print("1. Embedding 服务配置")
    print("2. Rerank 服务配置")
    print("3. ChromaDB 服务配置")
    print("4. MCP 服务配置")
    print("5. 切块策略")
    print("6. 返回")

    choice = input("\n请选择 (1-6): ").strip()

    if choice == "1":
        update_embedding_config(env)
    elif choice == "2":
        update_rerank_config(env)
    elif choice == "3":
        update_chroma_config(env)
    elif choice == "4":
        update_mcp_config(env)
    elif choice == "5":
        update_chunk_config(env)
    elif choice == "6":
        return
    else:
        print("无效的选择")


def update_embedding_config(env: dict):
    """更新 Embedding 配置"""
    print("\n当前 Embedding 配置：")
    print(f"  模式: {env.get('EMBEDDING_MODE', 'cloud')}")

    # 选择模式
    print("\n选择 Embedding 模式：")
    print("1. 云端模式（OpenAI/SiliconFlow/DeepSeek 等）")
    print("2. 本地模式（LM Studio/Ollama 等）")
    mode_choice = input("\n请选择 (1-2): ").strip()

    if mode_choice == "1":
        env['EMBEDDING_MODE'] = 'cloud'

        # 选择云端提供商
        print("\n选择云端提供商：")
        print("1. SiliconFlow（默认）")
        print("2. OpenAI")
        print("3. DeepSeek")
        print("4. 智谱 AI")
        print("5. Moonshot")
        print("6. 自定义")

        provider_map = {
            "1": "siliconflow",
            "2": "openai",
            "3": "deepseek",
            "4": "zhipu",
            "5": "moonshot",
            "6": "custom"
        }
        provider_choice = input("\n请选择 (1-6) [1]: ").strip() or "1"
        provider = provider_map.get(provider_choice, "siliconflow")
        env['EMBEDDING_CLOUD_PROVIDER'] = provider

        if provider == "custom":
            env['EMBEDDING_CLOUD_URL'] = input(f"API URL [{env.get('EMBEDDING_CLOUD_URL', '')}]: ").strip() or env.get('EMBEDDING_CLOUD_URL', '')

        env['EMBEDDING_CLOUD_API_KEY'] = input(f"API Key [****]: ").strip() or env.get('EMBEDDING_CLOUD_API_KEY', '')
        env['EMBEDDING_CLOUD_MODEL'] = input(f"模型名称 [{env.get('EMBEDDING_CLOUD_MODEL', 'BAAI/bge-m3')}]: ").strip() or env.get('EMBEDDING_CLOUD_MODEL', 'BAAI/bge-m3')
        env['EMBEDDING_CLOUD_DIM'] = input(f"向量维度 [{env.get('EMBEDDING_CLOUD_DIM', '1024')}]: ").strip() or env.get('EMBEDDING_CLOUD_DIM', '1024')

    elif mode_choice == "2":
        env['EMBEDDING_MODE'] = 'local'
        env['EMBEDDING_LOCAL_URL'] = input(f"本地服务 URL [{env.get('EMBEDDING_LOCAL_URL', 'http://127.0.0.1:1234/v1/embeddings')}]: ").strip() or env.get('EMBEDDING_LOCAL_URL', 'http://127.0.0.1:1234/v1/embeddings')
        env['EMBEDDING_LOCAL_MODEL'] = input(f"模型名称 [{env.get('EMBEDDING_LOCAL_MODEL', 'text-embedding-qwen3-embedding-4b')}]: ").strip() or env.get('EMBEDDING_LOCAL_MODEL', 'text-embedding-qwen3-embedding-4b')
        env['EMBEDDING_LOCAL_DIM'] = input(f"向量维度 [{env.get('EMBEDDING_LOCAL_DIM', '2560')}]: ").strip() or env.get('EMBEDDING_LOCAL_DIM', '2560')

    save_env(env)
    print("\n✓ Embedding 配置已更新")


def update_rerank_config(env: dict):
    """更新 Rerank 配置"""
    print("\n当前 Rerank 配置：")
    print(f"  启用: {env.get('RERANK_ENABLED', 'true')}")
    print(f"  模式: {env.get('RERANK_MODE', 'cloud')}")

    # 是否启用
    enabled = input(f"\n是否启用 Rerank？(y/N) [{'y' if env.get('RERANK_ENABLED', 'true') == 'true' else 'N'}]: ").strip().lower()
    env['RERANK_ENABLED'] = 'true' if enabled == 'y' else 'false'

    if env['RERANK_ENABLED'] == 'true':
        # 选择模式
        print("\n选择 Rerank 模式：")
        print("1. 云端模式（Cohere/Jina 等）")
        print("2. 本地模式（CrossEncoder）")
        mode_choice = input("\n请选择 (1-2): ").strip()

        if mode_choice == "1":
            env['RERANK_MODE'] = 'cloud'

            # 选择云端提供商
            print("\n选择云端提供商：")
            print("1. Cohere（默认）")
            print("2. Jina")
            print("3. 自定义")

            provider_map = {"1": "cohere", "2": "jina", "3": "custom"}
            provider_choice = input("\n请选择 (1-3) [1]: ").strip() or "1"
            provider = provider_map.get(provider_choice, "cohere")
            env['RERANK_CLOUD_PROVIDER'] = provider

            if provider == "custom":
                env['RERANK_CLOUD_URL'] = input(f"API URL [{env.get('RERANK_CLOUD_URL', '')}]: ").strip() or env.get('RERANK_CLOUD_URL', '')

            env['RERANK_CLOUD_API_KEY'] = input(f"API Key [****]: ").strip() or env.get('RERANK_CLOUD_API_KEY', '')
            env['RERANK_CLOUD_MODEL'] = input(f"模型名称 [{env.get('RERANK_CLOUD_MODEL', 'rerank-multilingual-v3.0')}]: ").strip() or env.get('RERANK_CLOUD_MODEL', 'rerank-multilingual-v3.0')

        elif mode_choice == "2":
            env['RERANK_MODE'] = 'local'
            env['RERANK_LOCAL_URL'] = input(f"本地服务 URL [{env.get('RERANK_LOCAL_URL', 'http://127.0.0.1:5001')}]: ").strip() or env.get('RERANK_LOCAL_URL', 'http://127.0.0.1:5001')

    save_env(env)
    print("\n✓ Rerank 配置已更新")


def update_chroma_config(env: dict):
    """更新 ChromaDB 配置"""
    print("\n当前 ChromaDB 配置：")
    print(f"  HOST: {env.get('CHROMA_SERVER_HOST', '127.0.0.1')}")
    print(f"  PORT: {env.get('CHROMA_SERVER_PORT', '9898')}")

    print("\n输入新值（直接回车跳过）：")
    env['CHROMA_SERVER_HOST'] = input(f"HOST [{env.get('CHROMA_SERVER_HOST', '127.0.0.1')}]: ").strip() or env.get('CHROMA_SERVER_HOST', '127.0.0.1')
    env['CHROMA_SERVER_PORT'] = input(f"PORT [{env.get('CHROMA_SERVER_PORT', '9898')}]: ").strip() or env.get('CHROMA_SERVER_PORT', '9898')

    save_env(env)
    print("\n✓ ChromaDB 配置已更新")


def update_mcp_config(env: dict):
    """更新 MCP 配置"""
    print("\n当前 MCP 配置：")
    print(f"  HOST: {env.get('MCP_SERVER_HOST', '127.0.0.1')}")
    print(f"  PORT: {env.get('MCP_SERVER_PORT', '9766')}")

    print("\n输入新值（直接回车跳过）：")
    env['MCP_SERVER_HOST'] = input(f"HOST [{env.get('MCP_SERVER_HOST', '127.0.0.1')}]: ").strip() or env.get('MCP_SERVER_HOST', '127.0.0.1')
    env['MCP_SERVER_PORT'] = input(f"PORT [{env.get('MCP_SERVER_PORT', '9766')}]: ").strip() or env.get('MCP_SERVER_PORT', '9766')

    save_env(env)
    print("\n✓ MCP 配置已更新")


def update_chunk_config(env: dict):
    """更新切块策略"""
    print("\n当前切块策略：")
    print(f"  CHUNK_TEMPLATE={env.get('CHUNK_TEMPLATE', 'academic')}")

    print("\n可选模板：")
    print("1. academic（英文文献专用）")
    print("2. chinese（中文专用）")
    print("3. code（数据分析/代码专用）")
    print("4. custom（自定义模板）")

    template_choice = input("\n请选择 (1-4): ").strip()
    template_map = {"1": "academic", "2": "chinese", "3": "code", "4": "custom"}
    template_name = template_map.get(template_choice, env.get('CHUNK_TEMPLATE', 'academic'))

    env['CHUNK_TEMPLATE'] = template_name
    save_env(env)
    print(f"\n✓ 切块策略已更新为: {template_name}")


def update_config():
    """更新 config.json 配置"""
    config = load_config()

    print("\n可修改的 config.json 配置项：")
    print("1. 切片模板配置")
    print("2. 检索参数配置")
    print("3. 返回")

    choice = input("\n请选择 (1-3): ").strip()

    if choice == "1":
        update_chunk_templates(config)
    elif choice == "2":
        update_retrieval_config(config)
    elif choice == "3":
        return
    else:
        print("无效的选择")


def update_chunk_templates(config: dict):
    """更新切片模板配置"""
    print("\n当前切片模板：")
    for name, template in config["chunk"]["templates"].items():
        print(f"  {name}: {template['name']}")

    print("\n操作：")
    print("1. 修改现有模板")
    print("2. 添加自定义模板")
    print("3. 删除模板")
    print("4. 返回")

    sub_choice = input("\n请选择 (1-4): ").strip()

    if sub_choice == "1":
        template_name = input("\n输入模板名称: ").strip()
        if template_name in config["chunk"]["templates"]:
            template = config["chunk"]["templates"][template_name]
            print(f"\n当前 {template_name} 模板配置：")
            print(f"  chunk_size={template['chunk_size']}")
            print(f"  overlap={template['overlap']}")
            print(f"  strategy={template['strategy']}")

            print("\n输入新值（直接回车跳过）：")
            chunk_size = input(f"chunk_size [{template['chunk_size']}]: ").strip()
            if chunk_size:
                template['chunk_size'] = int(chunk_size)

            overlap = input(f"overlap [{template['overlap']}]: ").strip()
            if overlap:
                template['overlap'] = int(overlap)

            print("\n切片策略：")
            print("1. recursive（推荐，保留段落结构）")
            print("2. flat（兼容旧逻辑）")
            strategy_choice = input(f"请选择 (1-2) [{'1' if template['strategy'] == 'recursive' else '2'}]: ").strip()
            if strategy_choice == "2":
                template['strategy'] = "flat"
            elif strategy_choice == "1":
                template['strategy'] = "recursive"

            save_config(config)
            print(f"\n✓ {template_name} 模板配置已更新")
        else:
            print(f"\n✗ 模板 {template_name} 不存在")

    elif sub_choice == "2":
        template_name = input("\n输入模板名称: ").strip()
        if template_name not in config["chunk"]["templates"]:
            print(f"\n输入 {template_name} 模板配置：")
            chunk_size = input("chunk_size [1000]: ").strip() or "1000"
            overlap = input("overlap [100]: ").strip() or "100"

            print("\n切片策略：")
            print("1. recursive（推荐，保留段落结构）")
            print("2. flat（兼容旧逻辑）")
            strategy_choice = input("请选择 (1-2) [1]: ").strip()
            strategy = "flat" if strategy_choice == "2" else "recursive"

            separators = input("separators (逗号分隔，直接回车使用默认值) [\\n\\n,\\n, ,]: ").strip()
            if separators:
                separators = [s.strip() for s in separators.split(',')]
            else:
                separators = ["\n\n", "\n", " ", ""]

            config["chunk"]["templates"][template_name] = {
                "name": f"自定义模板 - {template_name}",
                "chunk_size": int(chunk_size),
                "overlap": int(overlap),
                "strategy": strategy,
                "separators": separators
            }

            save_config(config)
            print(f"\n✓ {template_name} 模板已添加")
        else:
            print(f"\n✗ 模板 {template_name} 已存在")

    elif sub_choice == "3":
        template_name = input("\n输入模板名称: ").strip()
        if template_name in config["chunk"]["templates"]:
            del config["chunk"]["templates"][template_name]
            save_config(config)
            print(f"\n✓ {template_name} 模板已删除")
        else:
            print(f"\n✗ 模板 {template_name} 不存在")

    elif sub_choice == "4":
        return

    else:
        print("无效的选择")


def update_retrieval_config(config: dict):
    """更新检索参数配置"""
    retrieval = config["retrieval"]
    print("\n当前检索参数配置：")
    print(f"  k={retrieval['k']}")
    print(f"  fetch_k={retrieval['fetch_k']}")
    print(f"  lambda={retrieval['lambda']}")
    print(f"  threshold={retrieval['threshold']}")

    print("\n输入新值（直接回车跳过）：")
    k = input(f"k [{retrieval['k']}]: ").strip()
    if k:
        retrieval['k'] = int(k)

    fetch_k = input(f"fetch_k [{retrieval['fetch_k']}]: ").strip()
    if fetch_k:
        retrieval['fetch_k'] = int(fetch_k)

    lambda_val = input(f"lambda [{retrieval['lambda']}]: ").strip()
    if lambda_val:
        retrieval['lambda'] = float(lambda_val)

    threshold = input(f"threshold [{retrieval['threshold']}]: ").strip()
    if threshold:
        retrieval['threshold'] = float(threshold)

    save_config(config)
    print("\n✓ 检索参数配置已更新")


def reset_config():
    """重置配置为默认值"""
    print("\n⚠ 警告：重置配置将覆盖当前配置！")
    choice = input("确认重置？(y/N): ").strip().lower()

    if choice == 'y':
        # 备份当前配置
        if ENV_FILE.exists():
            backup_file = ENV_FILE.with_suffix('.env.backup')
            shutil.copy(ENV_FILE, backup_file)
            print(f"已备份 .env 到: {backup_file}")

        if CONFIG_FILE.exists():
            backup_file = CONFIG_FILE.with_suffix('.json.backup')
            shutil.copy(CONFIG_FILE, backup_file)
            print(f"已备份 config.json 到: {backup_file}")

        # 重置为默认配置
        default_env = {
            "EMBEDDING_MODE": "cloud",
            "EMBEDDING_CLOUD_PROVIDER": "siliconflow",
            "EMBEDDING_CLOUD_API_KEY": "",
            "EMBEDDING_CLOUD_MODEL": "BAAI/bge-m3",
            "EMBEDDING_CLOUD_DIM": "1024",
            "EMBEDDING_CLOUD_URL": "",
            "EMBEDDING_LOCAL_URL": "http://127.0.0.1:1234/v1/embeddings",
            "EMBEDDING_LOCAL_MODEL": "text-embedding-qwen3-embedding-4b",
            "EMBEDDING_LOCAL_DIM": "2560",
            "RERANK_ENABLED": "true",
            "RERANK_MODE": "cloud",
            "RERANK_CLOUD_PROVIDER": "cohere",
            "RERANK_CLOUD_API_KEY": "",
            "RERANK_CLOUD_MODEL": "rerank-multilingual-v3.0",
            "RERANK_CLOUD_URL": "",
            "RERANK_LOCAL_URL": "http://127.0.0.1:5001",
            "CHROMA_SERVER_HOST": "127.0.0.1",
            "CHROMA_SERVER_PORT": "9898",
            "MCP_SERVER_HOST": "127.0.0.1",
            "MCP_SERVER_PORT": "9766",
            "CHUNK_TEMPLATE": "academic"
        }
        save_env(default_env)

        default_config = {
            "collection": {
                "name": "default_collection"
            },
            "docs": {
                "dir": "data/docs"
            },
            "chroma": {
                "dir": "data/chroma_db"
            },
            "chunk": {
                "templates": {
                    "academic": {
                        "name": "英文文献专用",
                        "chunk_size": 2000,
                        "overlap": 200,
                        "strategy": "recursive",
                        "separators": ["\n\n", "\n", "\r\n", "。", ". ", "！", "?", "？", "!", "；", ";", "，", ",", "、", " ", ""]
                    },
                    "chinese": {
                        "name": "中文专用",
                        "chunk_size": 1500,
                        "overlap": 150,
                        "strategy": "recursive",
                        "separators": ["\n\n", "\n", "。", "！", "？", "；", "，", "、", " ", ""]
                    },
                    "code": {
                        "name": "数据分析/代码专用",
                        "chunk_size": 3000,
                        "overlap": 300,
                        "strategy": "flat",
                        "separators": ["\n\n\n", "\n\n", "\n", ". ", " ", ""]
                    },
                    "custom": {
                        "name": "自定义模板",
                        "chunk_size": 1000,
                        "overlap": 100,
                        "strategy": "recursive",
                        "separators": ["\n\n", "\n", " ", ""]
                    }
                },
                "default_template": "academic"
            },
            "retrieval": {
                "k": 5,
                "fetch_k": 15,
                "lambda": 0.7,
                "threshold": 0.3
            }
        }
        save_config(default_config)

        print("\n✓ 配置已重置为默认值")
    else:
        print("\n已取消重置")


def delete_config():
    """删除配置文件"""
    print("\n⚠ 警告：删除配置将无法恢复！")
    choice = input("确认删除？(y/N): ").strip().lower()

    if choice == 'y':
        # 备份当前配置
        if ENV_FILE.exists():
            backup_file = ENV_FILE.with_suffix('.env.backup')
            shutil.copy(ENV_FILE, backup_file)
            print(f"已备份 .env 到: {backup_file}")

        if CONFIG_FILE.exists():
            backup_file = CONFIG_FILE.with_suffix('.json.backup')
            shutil.copy(CONFIG_FILE, backup_file)
            print(f"已备份 config.json 到: {backup_file}")

        # 删除配置文件
        if ENV_FILE.exists():
            ENV_FILE.unlink()
            print("已删除 .env")

        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            print("已删除 config.json")

        print("\n✓ 配置文件已删除")
    else:
        print("\n已取消删除")


def main():
    """主函数"""
    # 确保配置目录存在
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        print("\n" + "=" * 60)
        print("  Ezy-RAG V0.0.17 — 配置管理")
        print("=" * 60)
        print("1. 查看配置")
        print("2. 更新配置")
        print("3. 重置配置")
        print("4. 删除配置")
        print("5. 退出")

        choice = input("\n请选择 (1-5): ").strip()

        if choice == "1":
            print("\n查看配置：")
            print("1. 查看 .env")
            print("2. 查看 config.json")
            print("3. 返回")

            sub_choice = input("\n请选择 (1-3): ").strip()

            if sub_choice == "1":
                show_env()
            elif sub_choice == "2":
                show_config()
            elif sub_choice == "3":
                continue
            else:
                print("无效的选择")

        elif choice == "2":
            print("\n更新配置：")
            print("1. 更新 .env")
            print("2. 更新 config.json")
            print("3. 返回")

            sub_choice = input("\n请选择 (1-3): ").strip()

            if sub_choice == "1":
                update_env()
            elif sub_choice == "2":
                update_config()
            elif sub_choice == "3":
                continue
            else:
                print("无效的选择")

        elif choice == "3":
            reset_config()

        elif choice == "4":
            delete_config()

        elif choice == "5":
            break

        else:
            print("无效的选择")


if __name__ == "__main__":
    main()
