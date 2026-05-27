# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.14 — 配置管理脚本
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
        f.write("# Ezy-RAG V0.0.14 — 环境配置\n")
        f.write("# 由 init.py 生成\n")
        f.write("# ============================================================\n\n")

        # Embedding 模型配置
        f.write("# ----- Embedding 模型配置 -----\n")
        for key in ["EMBEDDING_API_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "EMBEDDING_DIM"]:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")

        # Rerank 模型配置
        f.write("# ----- Rerank 模型配置 -----\n")
        for key in ["RERANK_ENABLED", "RERANK_API_URL", "RERANK_API_KEY"]:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")

        # ChromaDB 服务配置
        f.write("# ----- ChromaDB 服务配置 -----\n")
        for key in ["CHROMA_SERVER_HOST", "CHROMA_SERVER_PORT"]:
            f.write(f"{key}={env.get(key, '')}\n")
        f.write("\n")

        # MCP 服务配置
        f.write("# ----- MCP 服务配置 -----\n")
        for key in ["MCP_SERVER_HOST", "MCP_SERVER_PORT"]:
            f.write(f"{key}={env.get(key, '')}\n")
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
    print("-" * 40)
    for key, value in env.items():
        if "KEY" in key and value:
            print(f"{key}=****")
        else:
            print(f"{key}={value}")


def show_config():
    """显示 config.json 配置"""
    config = load_config()
    print("\n当前 config.json 配置：")
    print("-" * 40)
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
        # 更新 Embedding 服务配置
        print("\n当前 Embedding 服务配置：")
        print(f"  EMBEDDING_API_URL={env.get('EMBEDDING_API_URL', '')}")
        print(f"  EMBEDDING_API_KEY=****")
        print(f"  EMBEDDING_MODEL={env.get('EMBEDDING_MODEL', '')}")
        print(f"  EMBEDDING_DIM={env.get('EMBEDDING_DIM', '')}")

        print("\n输入新值（直接回车跳过）：")
        env['EMBEDDING_API_URL'] = input(f"EMBEDDING_API_URL [{env.get('EMBEDDING_API_URL', '')}]: ").strip() or env.get('EMBEDDING_API_URL', '')
        env['EMBEDDING_API_KEY'] = input(f"EMBEDDING_API_KEY [****]: ").strip() or env.get('EMBEDDING_API_KEY', '')
        env['EMBEDDING_MODEL'] = input(f"EMBEDDING_MODEL [{env.get('EMBEDDING_MODEL', '')}]: ").strip() or env.get('EMBEDDING_MODEL', '')
        env['EMBEDDING_DIM'] = input(f"EMBEDDING_DIM [{env.get('EMBEDDING_DIM', '')}]: ").strip() or env.get('EMBEDDING_DIM', '')

        save_env(env)
        print("\n✓ Embedding 服务配置已更新")

    elif choice == "2":
        # 更新 Rerank 服务配置
        print("\n当前 Rerank 服务配置：")
        print(f"  RERANK_ENABLED={env.get('RERANK_ENABLED', 'true')}")
        print(f"  RERANK_API_URL={env.get('RERANK_API_URL', '')}")
        print(f"  RERANK_API_KEY=****")

        print("\n输入新值（直接回车跳过）：")
        env['RERANK_ENABLED'] = input(f"RERANK_ENABLED [{env.get('RERANK_ENABLED', 'true')}]: ").strip() or env.get('RERANK_ENABLED', 'true')
        env['RERANK_API_URL'] = input(f"RERANK_API_URL [{env.get('RERANK_API_URL', '')}]: ").strip() or env.get('RERANK_API_URL', '')
        env['RERANK_API_KEY'] = input(f"RERANK_API_KEY [****]: ").strip() or env.get('RERANK_API_KEY', '')

        save_env(env)
        print("\n✓ Rerank 服务配置已更新")

    elif choice == "3":
        # 更新 ChromaDB 服务配置
        print("\n当前 ChromaDB 服务配置：")
        print(f"  CHROMA_SERVER_HOST={env.get('CHROMA_SERVER_HOST', '127.0.0.1')}")
        print(f"  CHROMA_SERVER_PORT={env.get('CHROMA_SERVER_PORT', '9898')}")

        print("\n输入新值（直接回车跳过）：")
        env['CHROMA_SERVER_HOST'] = input(f"CHROMA_SERVER_HOST [{env.get('CHROMA_SERVER_HOST', '127.0.0.1')}]: ").strip() or env.get('CHROMA_SERVER_HOST', '127.0.0.1')
        env['CHROMA_SERVER_PORT'] = input(f"CHROMA_SERVER_PORT [{env.get('CHROMA_SERVER_PORT', '9898')}]: ").strip() or env.get('CHROMA_SERVER_PORT', '9898')

        save_env(env)
        print("\n✓ ChromaDB 服务配置已更新")

    elif choice == "4":
        # 更新 MCP 服务配置
        print("\n当前 MCP 服务配置：")
        print(f"  MCP_SERVER_HOST={env.get('MCP_SERVER_HOST', '127.0.0.1')}")
        print(f"  MCP_SERVER_PORT={env.get('MCP_SERVER_PORT', '9766')}")

        print("\n输入新值（直接回车跳过）：")
        env['MCP_SERVER_HOST'] = input(f"MCP_SERVER_HOST [{env.get('MCP_SERVER_HOST', '127.0.0.1')}]: ").strip() or env.get('MCP_SERVER_HOST', '127.0.0.1')
        env['MCP_SERVER_PORT'] = input(f"MCP_SERVER_PORT [{env.get('MCP_SERVER_PORT', '9766')}]: ").strip() or env.get('MCP_SERVER_PORT', '9766')

        save_env(env)
        print("\n✓ MCP 服务配置已更新")

    elif choice == "5":
        # 更新切块策略
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

    elif choice == "6":
        return

    else:
        print("无效的选择")


def update_config():
    """更新 config.json 配置"""
    config = load_config()

    print("\n可修改的 config.json 配置项：")
    print("1. 切片模板配置")
    print("2. 检索参数配置")
    print("3. 返回")

    choice = input("\n请选择 (1-3): ").strip()

    if choice == "1":
        # 更新切片模板配置
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
            # 修改现有模板
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
            # 添加自定义模板
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
            # 删除模板
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

    elif choice == "2":
        # 更新检索参数配置
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

    elif choice == "3":
        return

    else:
        print("无效的选择")


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
            "EMBEDDING_API_URL": "http://127.0.0.1:5000/v1/embeddings",
            "EMBEDDING_API_KEY": "",
            "EMBEDDING_MODEL": "text-embedding-qwen3-embedding-4b",
            "EMBEDDING_DIM": "2560",
            "RERANK_ENABLED": "true",
            "RERANK_API_URL": "http://127.0.0.1:5001",
            "RERANK_API_KEY": "",
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
        print("  Ezy-RAG V0.0.14 — 配置管理")
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
