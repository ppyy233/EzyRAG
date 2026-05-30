# Ezy-RAG

知识库系统，提供文档管理、向量检索、智能问答等功能。

## 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（包管理器）
- Node.js（前端构建）

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 配置环境变量
cp config/.env.example config/.env
# 编辑 config/.env，填写 API Key 等配置

# 3. 启动服务
python -m servers.web
```

访问 http://127.0.0.1:9767 即可使用。

## 云端模式 vs 本地模式

默认使用**云端模式**，无需安装额外依赖。如需使用本地模型：

```bash
# 安装本地模型依赖（约 2GB）
uv sync --extra local
```

| 功能 | 云端模式 | 本地模式 |
|------|----------|----------|
| Embedding | 需要 API Key | 需要下载模型 |
| Rerank | 需要 API Key | 需要下载模型 + torch |

在 `config/.env` 中切换模式：

```bash
EMBEDDING_MODE=cloud   # 或 local
RERANK_MODE=cloud      # 或 local
```

## CLI 命令

```bash
python ezyrag.py                # 交互式菜单
python ezyrag.py quickstart     # 快速开始向导
python ezyrag.py service        # 服务管理
python ezyrag.py db             # 文档管理
python ezyrag.py config         # 配置管理
python ezyrag.py health         # 健康检查
```

## MCP Server 接入 opencode

Ezy-RAG 提供 MCP（Model Context Protocol）服务，可接入 opencode 等 AI Agent。

### 1. 启动服务

确保 Ezy-RAG 服务已启动（MCP 服务默认端口 9766）：

```bash
python -m servers.mcp
```

### 2. 配置 opencode

在项目根目录创建 `opencode.json`，添加 MCP 配置：

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

### 3. 重启 opencode

配置生效后，opencode 会自动发现 `search_knowledge_base` 工具。

**工具说明：** 当用户询问的信息可能属于个人私有数据、特定工作环境，或涉及训练数据中不存在的特定内容时，opencode 会优先调用此工具检索本地知识库。

## 项目结构

```
Ezy-RAG/
├── config/          # 配置层
├── core/            # 核心层
├── servers/         # 服务层
├── cli/             # CLI 交互层
├── frontend/        # Web 前端
├── data/            # 数据目录
└── quickstart.py    # 一键启动脚本
```

## 更多信息

详见 [architecture.md](architecture.md) 了解系统架构、数据流、API 接口等详细内容。
