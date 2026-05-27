# -*- coding: utf-8 -*-
"""
Ezy-RAG — 初始化脚本
交互式配置，自动生成 .env 文件

用法:
  python init.py          # 交互式配置
  python init.py --default # 使用默认值，跳过交互
"""
import argparse
from pathlib import Path

# 配置项定义（默认值 + 描述 + 验证）
CONFIG_ITEMS = [
    # Embedding 模型配置
    {
        "key": "EMBEDDING_API_URL",
        "default": "http://127.0.0.1:5000/v1/embeddings",
        "description": "Embedding 服务地址",
        "type": "str",
    },
    {
        "key": "EMBEDDING_API_KEY",
        "default": "",
        "description": "Embedding 服务密钥（可选）",
        "type": "str",
        "secret": True,
    },
    {
        "key": "EMBEDDING_MODEL",
        "default": "text-embedding-qwen3-embedding-4b",
        "description": "嵌入模型名称",
        "type": "str",
    },
    {
        "key": "EMBEDDING_DIM",
        "default": "2560",
        "description": "嵌入维度",
        "type": "int",
    },
    # Rerank 模型配置
    {
        "key": "RERANK_ENABLED",
        "default": "true",
        "description": "是否启用重排",
        "type": "bool",
    },
    {
        "key": "RERANK_API_URL",
        "default": "http://127.0.0.1:5001",
        "description": "Rerank 服务地址",
        "type": "str",
    },
    {
        "key": "RERANK_API_KEY",
        "default": "",
        "description": "Rerank 服务密钥（可选）",
        "type": "str",
        "secret": True,
    },
    # ChromaDB 服务配置
    {
        "key": "CHROMA_SERVER_HOST",
        "default": "127.0.0.1",
        "description": "ChromaDB 服务器地址",
        "type": "str",
    },
    {
        "key": "CHROMA_SERVER_PORT",
        "default": "9898",
        "description": "ChromaDB 服务器端口",
        "type": "int",
    },
    # MCP 服务配置
    {
        "key": "MCP_SERVER_HOST",
        "default": "127.0.0.1",
        "description": "MCP 服务器地址",
        "type": "str",
    },
    {
        "key": "MCP_SERVER_PORT",
        "default": "9766",
        "description": "MCP 服务器端口",
        "type": "int",
    },
    # 切块策略
    {
        "key": "CHUNK_TEMPLATE",
        "default": "academic",
        "description": "切块模板 (academic/chinese/code)",
        "type": "str",
        "choices": ["academic", "chinese", "code"],
    },
]


def generate_env(config_values: dict, output_file: Path):
    """生成 .env 文件"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# Ezy-RAG 配置文件（由 init.py 自动生成）\n")
        f.write("# ============================================================\n\n")

        # Embedding 模型配置
        f.write("# ----- Embedding 模型配置 -----\n")
        for key in ["EMBEDDING_API_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "EMBEDDING_DIM"]:
            item = next(i for i in CONFIG_ITEMS if i["key"] == key)
            value = config_values.get(key, item["default"])
            f.write(f"{key}={value}\n")
        f.write("\n")

        # Rerank 模型配置
        f.write("# ----- Rerank 模型配置 -----\n")
        for key in ["RERANK_ENABLED", "RERANK_API_URL", "RERANK_API_KEY"]:
            item = next(i for i in CONFIG_ITEMS if i["key"] == key)
            value = config_values.get(key, item["default"])
            f.write(f"{key}={value}\n")
        f.write("\n")

        # ChromaDB 服务配置
        f.write("# ----- ChromaDB 服务配置 -----\n")
        for key in ["CHROMA_SERVER_HOST", "CHROMA_SERVER_PORT"]:
            item = next(i for i in CONFIG_ITEMS if i["key"] == key)
            value = config_values.get(key, item["default"])
            f.write(f"{key}={value}\n")
        f.write("\n")

        # MCP 服务配置
        f.write("# ----- MCP 服务配置 -----\n")
        for key in ["MCP_SERVER_HOST", "MCP_SERVER_PORT"]:
            item = next(i for i in CONFIG_ITEMS if i["key"] == key)
            value = config_values.get(key, item["default"])
            f.write(f"{key}={value}\n")
        f.write("\n")

        # 切块策略
        f.write("# ----- 切块策略 -----\n")
        for key in ["CHUNK_TEMPLATE"]:
            item = next(i for i in CONFIG_ITEMS if i["key"] == key)
            value = config_values.get(key, item["default"])
            f.write(f"{key}={value}\n")

    print(f"\n✓ 已生成配置文件: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Ezy-RAG 初始化脚本")
    parser.add_argument("--default", action="store_true", help="使用默认值，跳过交互")
    args = parser.parse_args()

    print("=" * 60)
    print("  Ezy-RAG V0.0.14 — 初始化配置")
    print("=" * 60)

    config_values = {}

    if args.default:
        print("\n使用默认配置...")
        for item in CONFIG_ITEMS:
            config_values[item["key"]] = item["default"]
    else:
        print("\n请按提示输入配置（直接回车使用默认值）：\n")

        for item in CONFIG_ITEMS:
            key = item["key"]
            default = item["default"]
            description = item["description"]
            item_type = item["type"]
            choices = item.get("choices")
            secret = item.get("secret", False)

            # 构建提示信息
            if choices:
                prompt = f"{description} [{'/'.join(choices)}] (默认: {default}): "
            elif secret:
                prompt = f"{description} (默认: ****): "
            else:
                prompt = f"{description} (默认: {default}): "

            # 获取用户输入
            while True:
                value = input(prompt).strip()

                # 使用默认值
                if not value:
                    value = default
                    break

                # 验证输入
                if item_type == "int":
                    try:
                        int(value)
                        break
                    except ValueError:
                        print("  ✗ 请输入有效的整数")
                        continue

                if choices and value not in choices:
                    print(f"  ✗ 请选择: {', '.join(choices)}")
                    continue

                break

            config_values[key] = value

    # 生成 .env 文件
    env_file = Path(__file__).parent / ".env"
    generate_env(config_values, env_file)

    print("\n" + "=" * 60)
    print("  初始化完成！")
    print("=" * 60)
    print("\n下一步：")
    print("  1. 检查 .env 文件，确保配置正确")
    print("  2. 启动服务: python -m servers.chroma")
    print("  3. 构建知识库: python -m core.builder --full")
    print("  4. 启动 MCP: python -m servers.mcp")


if __name__ == "__main__":
    main()
