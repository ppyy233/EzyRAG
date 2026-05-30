# Ezy-RAG

知识库系统，提供文档管理、向量检索、智能问答等功能。

## 快速开始

```bash
python quickstart.py
```

一键完成：环境检查 → 安装依赖 → 配置 API Key → 启动服务 → 打开浏览器。

首次运行会引导你填写配置，之后每次运行直接启动服务。

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（包管理器）
- Node.js（前端构建，可选）

## 云端模式 vs 本地模式

默认使用**云端模式**，无需安装额外依赖。如需使用本地模型：

```bash
uv sync --extra local
```

| 功能 | 云端模式 | 本地模式 |
|------|----------|----------|
| Embedding | 需要 API Key | 需要下载模型 |
| Rerank | 需要 API Key | 需要下载模型 + torch |

## CLI 命令

```bash
python ezyrag.py                # 交互式菜单
python ezyrag.py service        # 服务管理
python ezyrag.py db             # 文档管理
python ezyrag.py config         # 配置管理
python ezyrag.py health         # 健康检查
```

## MCP Server 接入 opencode

Ezy-RAG 提供 MCP（Model Context Protocol）服务，可接入 opencode 等 AI Agent。

### 1. 启动 Ezy-RAG 服务

```bash
python quickstart.py
```

### 2. 启动 MCP 服务

```bash
python -m servers.mcp
```

### 3. 配置 opencode

在项目根目录创建 `opencode.json`：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ezy-rag": {
      "type": "remote",
      "url": "http://127.0.0.1:9766/mcp",
      "enabled": true
    }
  }
}
```

### 4. 重启 opencode

配置生效后，opencode 会自动发现 `search_knowledge_base` 工具。当用户询问的信息可能属于个人私有数据、特定工作环境，或涉及训练数据中不存在的特定内容时，opencode 会优先调用此工具检索本地知识库。

## 项目结构

```
Ezy-RAG/
├── config/          # 配置层
├── core/            # 核心层
├── servers/         # 服务层
├── cli/             # CLI 交互层
├── frontend/        # Web 前端
├── data/            # 数据目录
├── quickstart.py    # 一键启动脚本
└── architecture.md  # 系统架构文档
```

## 更多信息

详见 [architecture.md](architecture.md) 了解系统架构、数据流、API 接口等详细内容。
