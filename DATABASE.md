# Ezy-RAG V1.0.0 技术文档

## 1. 系统概述

Ezy-RAG 是一个本地部署的知识库 RAG（Retrieval-Augmented Generation）系统，支持文档的切片、向量化、存储和语义检索。

### 核心理念

**本地库和向量库分离管理**：
- 本地库（`data/docs/`）：用户管理的原始文档
- 向量库（ChromaDB）：系统管理的向量数据
- 两者通过 `source` 字段和 `content_hash` 建立映射与一致性校验

---

## 2. 技术栈

### 2.1 后端

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **语言** | Python | 3.11+ | 主开发语言 |
| **包管理** | uv | - | 依赖管理与虚拟环境 |
| **Web 框架** | FastAPI | ≥0.136.1 | REST API + WebSocket 服务 |
| **ASGI 服务器** | Uvicorn | ≥0.46.0 | 运行 FastAPI |
| **向量数据库** | ChromaDB | ≥1.5.9 | 向量存储与检索（HNSW 索引） |
| **Embedding** | OpenAI SDK | ≥2.36.0 | 调用 Embedding 服务（兼容 LM Studio） |
| **Embedding 模型** | Qwen3-Embedding-4B | - | 文本向量化（维度 2560） |
| **Rerank 模型** | BGE Cross-Encoder | - | 检索结果重排优化 |
| **深度学习** | PyTorch | ≥2.5.0, <2.7.0 | Rerank 模型推理（CUDA 12.4） |
| **Embedding 框架** | Sentence-Transformers | ≥5.5.0 | 加载 Rerank 模型 |
| **MCP 协议** | mcp | ≥1.27.1 | AI 客户端工具调用协议 |
| **HTTP 客户端** | httpx | ≥0.28.1 | 异步 HTTP 请求 |
| **PDF 解析** | pypdf | ≥6.11.0 | PDF 文本提取 |
| **Word 解析** | python-docx | ≥1.2.0 | DOCX 文本提取 |
| **遥测** | opentelemetry-instrumentation-fastapi | ≥0.63b1 | 性能监控 |

### 2.2 前端

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **框架** | Vue.js | 3.4+ | 响应式 UI 框架 |
| **构建工具** | Vite | 5.0+ | 开发服务器与生产构建 |
| **路由** | Vue Router | 4.2+ | 前端路由管理 |
| **UI 组件库** | Element Plus | 2.5+ | 表格、表单、按钮等组件 |
| **图标** | @element-plus/icons-vue | 2.3+ | Element Plus 图标集 |
| **HTTP 客户端** | Axios | 1.6+ | 调用后端 API |
| **实时通信** | WebSocket API | - | 接收后端推送消息 |

### 2.3 基础设施

| 类别 | 技术 | 说明 |
|------|------|------|
| **版本控制** | Git | 代码版本管理 |
| **运行平台** | Windows (AMD64) | 主要运行环境 |
| **GPU 加速** | CUDA 12.4 | Embedding 和 Rerank 模型推理 |
| **外部服务** | LM Studio | 本地 Embedding 服务（端口 5000） |

---

## 3. 项目结构

```
E:\桌面\RAG\
├── config/                         # 配置系统
│   ├── .env                        # 环境变量（不入 Git，含 API Key）
│   ├── .env.example                # 配置模板（入 Git）
│   ├── config.json                 # 业务配置（切片模板、检索参数）
│   └── settings.py                 # 配置加载模块
│
├── core/                           # 核心业务逻辑
│   ├── builder.py                  # 知识库构建（全量/增量，文档切片）
│   ├── embedder.py                 # Embedding 代理（优先级队列 + 工作线程）
│   └── repository.py               # 文档仓库（CRUD 封装，ACID 事务）
│
├── servers/                        # 服务层
│   ├── api.py                      # REST API + WebSocket（端口 9767）
│   ├── chroma.py                   # ChromaDB Server（端口 9898）
│   ├── mcp.py                      # MCP Server（端口 9766，供 AI 客户端调用）
│   └── rerank.py                   # Rerank Server（端口 5001）
│
├── frontend/                       # 前端项目
│   ├── src/
│   │   ├── api/index.js            # API 封装（Axios）
│   │   ├── composables/useWebSocket.js  # WebSocket 组合式函数
│   │   ├── components/Navbar.vue   # 导航栏组件
│   │   ├── views/                  # 页面视图
│   │   │   ├── Home.vue            # 首页（状态仪表盘）
│   │   │   ├── Documents.vue       # 文档管理（CRUD + 上传）
│   │   │   ├── Search.vue          # 知识库搜索
│   │   │   ├── Config.vue          # 配置管理
│   │   │   └── Services.vue        # 服务管理
│   │   ├── router/index.js         # 路由配置
│   │   ├── App.vue                 # 根组件
│   │   └── main.js                 # 入口文件
│   ├── dist/                       # 构建产物（生产部署用）
│   ├── package.json                # 前端依赖声明
│   ├── package-lock.json           # 依赖锁定文件
│   └── vite.config.js              # Vite 配置（代理、构建）
│
├── data/                           # 数据目录（不入 Git）
│   ├── docs/                       # 本地文档库
│   ├── chroma_db/                  # ChromaDB 持久化存储
│   └── models/                     # Rerank 模型文件
│
├── runtime/                        # 运行时数据（不入 Git）
│   ├── logs/                       # 服务日志
│   └── state/                      # 状态文件（集合指针）
│
├── tests/                          # 测试脚本
├── launcher.py                     # 统一启动器
├── start_all.py                    # 交互式服务管理
├── db_manage.py                    # 数据库管理 CLI
├── init.py                         # 配置管理 CLI
├── pyproject.toml                  # Python 项目元数据与依赖
├── uv.lock                         # 依赖锁定文件
├── .gitignore                      # Git 忽略规则
├── start.bat                       # 启动快捷方式
└── db.bat                          # 数据库管理快捷方式
```

---

## 4. 系统架构

### 4.1 服务架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户 / AI 客户端                       │
└─────────┬──────────────────┬──────────────────┬─────────┘
          │ HTTP             │ MCP (JSON-RPC)   │ WebSocket
          ▼                  ▼                  ▼
┌─────────────────┐  ┌───────────────┐  ┌──────────────┐
│  API Server     │  │  MCP Server   │  │  WebSocket   │
│  (FastAPI)      │  │  (FastAPI)    │  │  实时推送     │
│  端口: 9767     │  │  端口: 9766   │  │  /ws         │
└────────┬────────┘  └──────┬────────┘  └──────────────┘
         │                  │
         ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│                   核心业务层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ DocumentRepo │  │   Builder    │  │  Embedder    │  │
│  │ (CRUD+ACID)  │  │ (切片+构建)   │  │ (优先级队列)  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼─────────────────┼─────────────────┼───────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
│   ChromaDB      │  │  LM Studio   │  │  Rerank      │
│   端口: 9898    │  │  端口: 5000  │  │  端口: 5001  │
│   (HNSW 索引)   │  │  (外部服务)   │  │  (可选)      │
└─────────────────┘  └──────────────┘  └──────────────┘
```

### 4.2 数据流

```
文档上传/更新
    │
    ▼
文本提取 (PDF/DOCX/TXT)
    │
    ▼
文档切片 (recursive/flat 策略)
    │
    ▼
Embedding 向量化 (LM Studio, Qwen3)
    │
    ▼
写入 ChromaDB (HNSW 索引)

─────────────────────────────

搜索查询
    │
    ▼
查询向量化 (Embedding)
    │
    ▼
ChromaDB 向量检索 (cosine 相似度)
    │
    ▼
可选: Rerank 重排优化
    │
    ▼
返回 Top-K 结果
```

### 4.3 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| API Server | 9767 | REST API + WebSocket，前端通过 Vite 代理访问 |
| MCP Server | 9766 | MCP 协议端点，供 AI 客户端（如 opencode）调用 |
| ChromaDB | 9898 | 向量数据库 HTTP 服务 |
| Rerank Server | 5001 | BGE Cross-Encoder 重排服务 |
| LM Studio | 5000 | 外部 Embedding 服务（需单独启动） |
| Vite Dev | 5173 | 前端开发服务器（仅开发模式） |

---

## 5. 配置系统

### 5.1 配置分层

| 文件 | 类型 | 内容 | 入 Git |
|------|------|------|--------|
| `config/.env` | 环境变量 | IP、端口、API Key、模型名 | 否 |
| `config/.env.example` | 模板 | .env 的示例 | 是 |
| `config/config.json` | 业务配置 | 切片模板、检索参数、集合名 | 是 |
| `config/settings.py` | 加载器 | 统一加载 .env 和 config.json | 是 |

### 5.2 环境变量（.env）

```env
# Embedding 模型配置
EMBEDDING_API_URL=http://127.0.0.1:5000/v1/embeddings
EMBEDDING_API_KEY=
EMBEDDING_MODEL=text-embedding-qwen3-embedding-4b
EMBEDDING_DIM=2560

# Rerank 模型配置
RERANK_ENABLED=true
RERANK_API_URL=http://127.0.0.1:5001
RERANK_API_KEY=

# ChromaDB 服务配置
CHROMA_SERVER_HOST=127.0.0.1
CHROMA_SERVER_PORT=9898

# MCP 服务配置
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=9766

# 切块策略
CHUNK_TEMPLATE=academic
```

### 5.3 业务配置（config.json）

```json
{
  "collection": {"name": "default_collection"},
  "docs": {"dir": "data/docs"},
  "chroma": {"dir": "data/chroma_db"},
  "chunk": {
    "templates": {
      "academic": {
        "name": "英文文献专用",
        "chunk_size": 2000,
        "overlap": 200,
        "strategy": "recursive",
        "separators": ["\n\n", "\n", "。", ". ", "！", "?", "？", "!", "；", ";", "，", ",", "、", " ", ""]
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
  "retrieval": {"k": 5, "fetch_k": 15, "lambda": 0.7, "threshold": 0.3}
}
```

### 5.4 切片策略说明

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `recursive` | 递归分层切片：段落 → 句子 → 字符，保留学术文献段落完整性 | 学术论文、中文文档 |
| `flat` | 扁平切片，不保留段落结构 | 代码、数据分析 |

| 参数 | 说明 |
|------|------|
| `chunk_size` | 单个切片最大字符数 |
| `overlap` | 相邻切片重叠字符数，避免上下文断裂 |
| `separators` | 分隔符优先级列表，从粗到细 |

### 5.5 检索参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `k` | 5 | 最终返回的结果数量 |
| `fetch_k` | 15 | 初始检索数量（Rerank 前） |
| `lambda` | 0.7 | 相似度权重系数 |
| `threshold` | 0.3 | 最低相似度阈值 |

---

## 6. 核心模块详解

### 6.1 Embedding 代理（core/embedder.py）

**设计模式**：生产者-消费者 + 优先级队列

```
优先级定义：
  priority=0   → MCP 查询请求（VIP，插队处理）
  priority=100 → 建库切片请求（普通，排队处理）

工作流程：
  1. 调用方提交 embedding 请求到 PriorityQueue
  2. 工作线程从队列取出请求
  3. 调用 LM Studio API 获取向量
  4. 通过 Event 机制通知调用方结果

接口：
  embed_sync(texts, priority, timeout)   # 同步（core/builder.py 使用）
  embed_async(texts, priority, timeout)  # 异步（servers/mcp.py 使用）
```

### 6.2 文档仓库（core/repository.py）

**设计模式**：Repository 模式 + ACID 事务

```python
class DocumentRepository:
    # Create
    add(doc, chunk_cfg) -> int           # 添加单个文档
    add_many(documents, chunk_cfg) -> int # 批量添加

    # Read
    exists(source) -> bool               # 检查文档是否存在
    get_hash(source) -> str              # 获取 content_hash
    list_documents() -> List[dict]       # 列出所有文档
    count() -> int                       # 记录总数

    # Update
    update(doc, chunk_cfg) -> int        # Add-First 策略

    # Delete
    delete(source)                       # 删除文档

    # Batch
    sync(documents, chunk_cfg) -> dict   # 自动同步
```

**ACID 保证**：

| 特性 | 实现方式 |
|------|----------|
| 原子性 | Add-First 策略：先加新 chunks，再删旧 chunks |
| 一致性 | content_hash 检测数据变化 |
| 隔离性 | 查询和写入分离，查询不中断 |
| 持久性 | sync_threshold=100 控制 HNSW 索引刷盘频率 |

### 6.3 知识库构建（core/builder.py）

**支持格式**：PDF、DOCX、TXT、MD、PY、JS、TS、JAVA、C、CPP、GO、RS 等 30+ 种

**构建模式**：
- **增量更新**（默认）：通过 content_hash 检测变化，只处理新增/修改/删除的文件
- **全量重建**：清空集合，重新处理所有文档

**文件读取器**：

| 格式 | 读取器 | 说明 |
|------|--------|------|
| PDF | pypdf.PdfReader | 逐页提取文本 |
| DOCX | python-docx | 提取段落文本 |
| TXT/MD/代码 | 内置读取器 | 自动检测编码（UTF-8 → GBK → GB2312 → Latin-1） |

---

## 7. API 接口文档

### 7.1 REST API（端口 9767）

#### 状态查询

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/status` | 获取数据库状态（集合名、文档数、服务状态） |
| GET | `/api/health` | 健康检查（ChromaDB、Embedding 服务状态） |

#### 文档管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/documents` | 获取文档列表（本地 vs 向量库映射） |
| POST | `/api/documents` | 添加文档到向量库（body: `{file_path}`） |
| PUT | `/api/documents` | 更新向量库中的文档（body: `{file_path}`） |
| DELETE | `/api/documents` | 从向量库删除文档（body: `{file_path}`） |
| POST | `/api/documents/upload` | 上传文件到本地文档库（multipart/form-data） |

#### 知识库操作

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/search` | 搜索知识库（body: `{query}`） |
| POST | `/api/sync` | 同步本地文件和向量库 |
| POST | `/api/rebuild` | 全量重建向量库 |

#### 配置管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/config` | 读取当前配置（.env + config.json） |
| PUT | `/api/config` | 保存配置（body: `{env, config}`） |

#### 服务管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/services` | 获取所有服务状态 |
| POST | `/api/services/{key}/start` | 启动指定服务 |
| POST | `/api/services/{key}/stop` | 停止指定服务 |

### 7.2 WebSocket（端口 9767）

端点：`ws://127.0.0.1:9767/ws`

**消息类型**：

```json
// 文档操作通知
{"type": "document", "data": {"action": "add|update|delete|sync", ...}, "timestamp": "..."}

// 搜索进度
{"type": "search", "data": {"status": "started|completed", ...}, "timestamp": "..."}

// 重建进度
{"type": "progress", "data": {"operation": "rebuild", "status": "started|completed", ...}, "timestamp": "..."}
```

### 7.3 MCP 协议（端口 9766）

端点：`POST /mcp`

**可用工具**：

```json
{
  "name": "search_knowledge_base",
  "description": "搜索本地知识库中的文档信息",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "搜索关键词"}
    },
    "required": ["query"]
  }
}
```

---

## 8. 前端架构

### 8.1 页面路由

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | Home.vue | 状态仪表盘（文档数、chunks 数、服务状态） |
| `/documents` | Documents.vue | 文档管理（列表、添加、删除、更新、上传、同步） |
| `/search` | Search.vue | 知识库搜索（输入查询、展示结果、相似度排序） |
| `/config` | Config.vue | 配置管理（查看、修改 .env 和 config.json） |
| `/services` | Services.vue | 服务管理（查看状态、启动、停止、重启） |

### 8.2 前端架构图

```
┌───────────────────────────────────────────────┐
│  App.vue                                      │
│  ┌─────────────────────────────────────────┐  │
│  │  Navbar.vue（导航栏 + WebSocket 状态）   │  │
│  └─────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────┐  │
│  │  <router-view />                        │  │
│  │  Home / Documents / Search / Config /   │  │
│  │  Services                               │  │
│  └─────────────────────────────────────────┘  │
└───────────────────────────────────────────────┘
         │ Axios                    │ WebSocket
         ▼                          ▼
┌─────────────────┐        ┌─────────────────┐
│  api/index.js   │        │  useWebSocket   │
│  (REST API)     │        │  (实时推送)      │
└─────────────────┘        └─────────────────┘
         │                          │
         ▼                          ▼
┌───────────────────────────────────────────────┐
│  API Server (FastAPI, 端口 9767)              │
│  Vite 代理: /api → 127.0.0.1:9767            │
│           /ws  → ws://127.0.0.1:9767         │
└───────────────────────────────────────────────┘
```

### 8.3 Vite 配置

```javascript
// vite.config.js
server: {
  port: 5173,
  proxy: {
    '/api': { target: 'http://127.0.0.1:9767', changeOrigin: true },
    '/ws':  { target: 'ws://127.0.0.1:9767', ws: true }
  }
}
```

### 8.4 生产部署

构建产物（`frontend/dist/`）由 API Server 自动挂载为静态文件：

```python
# servers/api.py
frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dist)), name="static")

    @app.get("/")
    async def index():
        return FileResponse(str(frontend_dist / "index.html"))
```

生产模式下访问 `http://127.0.0.1:9767/` 即可使用完整系统。

---

## 9. 数据库架构

### 9.1 ChromaDB 配置

```python
{
    "hnsw:space": "cosine",        # 相似度算法：余弦相似度
    "hnsw:sync_threshold": 100     # HNSW 索引持久化阈值
}
```

### 9.2 元数据结构

每个 chunk 的元数据：

```python
{
    "source": "E:/桌面/RAG/data/docs/彭明旭.txt",    # 来源文档路径
    "chunk_index": 0,                                # 切片索引
    "content_hash": "86e70fca8a5ae452a2b4d97b09b1ac96"  # 文档内容 MD5 哈希
}
```

### 9.3 集合指针机制

文件：`runtime/state/collection_pointer.json`

```json
{
  "default_collection": "default_collection_v2"
}
```

用于全量重建时的原子切换：先创建影子集合写入数据，完成后切换指针。

---

## 10. 快速开始

### 10.1 环境要求

- Python 3.11+
- Node.js 18+
- CUDA 12.4（可选，GPU 加速）
- LM Studio（Embedding 服务）

### 10.2 安装步骤

```bash
# 1. 克隆项目
git clone <repo>
cd RAG

# 2. 安装 Python 依赖
uv sync

# 3. 安装前端依赖
cd frontend
npm install
cd ..

# 4. 初始化配置
python init.py

# 5. 下载 Rerank 模型（可选）
# 将 BGE Cross-Encoder 模型放入 data/models/
```

### 10.3 启动服务

```bash
# 方式一：统一启动器（推荐）
python launcher.py

# 方式二：交互式管理
python start_all.py

# 方式三：单独启动各服务
python -m servers.chroma    # 启动 ChromaDB
python -m servers.rerank    # 启动 Rerank
python -m servers.mcp       # 启动 MCP
python -m servers.api       # 启动 API
```

### 10.4 前端开发

```bash
cd frontend
npm run dev     # 开发模式（热重载，端口 5173）
npm run build   # 构建生产版本
npm run preview # 预览构建结果
```

### 10.5 访问地址

| 服务 | 地址 |
|------|------|
| 前端（开发模式） | http://localhost:5173 |
| 前端（生产模式） | http://localhost:9767 |
| API 文档 | http://localhost:9767/docs |
| MCP 服务 | http://localhost:9766 |

---

## 11. CLI 工具

### 11.1 数据库管理（db_manage.py）

```bash
python db_manage.py list                # 查看文档映射表
python db_manage.py status              # 查看数据库状态
python db_manage.py add <文件路径>       # 添加文档
python db_manage.py add --all           # 添加所有本地文档
python db_manage.py delete <文件路径>    # 删除文档
python db_manage.py delete --all        # 删除所有向量库文档
python db_manage.py update <文件路径>    # 更新文档
python db_manage.py update --all        # 更新所有文档
python db_manage.py sync                # 同步本地和向量库
python db_manage.py rebuild             # 全量重建
```

### 11.2 配置管理（init.py）

```bash
python init.py   # 交互式配置管理（查看/修改/重置/删除）
```

### 11.3 知识库构建（core.builder）

```bash
python -m core.builder                    # 增量更新
python -m core.builder --full             # 全量重建
python -m core.builder --template chinese # 指定切片模板
python -m core.builder -c my_collection   # 指定集合名
```

---

## 12. Git 管理

### 12.1 不入 Git 的内容

| 路径 | 原因 |
|------|------|
| `config/.env` | 包含 API Key 等敏感信息 |
| `data/docs/*` | 用户文档，体积大 |
| `data/chroma_db/*` | 向量库数据，可重建 |
| `data/models/*` | 模型文件，体积大（2GB+） |
| `runtime/logs/*` | 运行日志 |
| `runtime/state/*` | 运行时状态 |
| `frontend/node_modules/` | npm 依赖，由 `npm install` 生成 |
| `.venv/` | Python 虚拟环境 |
| `__pycache__/` | Python 编译缓存 |
| `frontend/dist/` | 前端构建产物 |

### 12.2 入 Git 的关键文件

| 文件 | 说明 |
|------|------|
| `pyproject.toml` | Python 依赖声明 |
| `uv.lock` | Python 依赖锁定 |
| `frontend/package.json` | 前端依赖声明 |
| `frontend/package-lock.json` | 前端依赖锁定 |
| `config/.env.example` | 配置模板 |
| `config/config.json` | 业务配置 |

---

## 13. 测试验证

### 13.1 CRUD 测试

| 操作 | 命令 | 结果 |
|------|------|------|
| 添加单个文件 | `add data/docs/彭明旭.txt` | 1 chunk 添加 |
| 添加多个文件 | `add --all` | 219 chunks 添加 |
| 查看文档列表 | `list` | 34 个文档显示 |
| 删除所有文档 | `delete --all` | 35 个文档删除 |
| 更新单个文件 | `update data/docs/彭明旭.txt` | 1 chunk 更新 |
| 自动同步 | `sync` | 34 个文档同步 |

### 13.2 增量更新测试

| 场景 | 结果 |
|------|------|
| 无变化 | 0 个向量化，34 个未变 |
| 添加 1 个新文件 | 1 个向量化，34 个未变 |
| 修改 1 个文件 | 1 个向量化，33 个未变 |
| 删除 1 个文件 | 0 个向量化，1 个删除 |

### 13.3 sync_threshold 测试

| 场景 | 结果 |
|------|------|
| 写入 50 条 (< 100) + 重启 | 数据完整 |
| 写入 100 条 (= 100) + 重启 | 数据完整 |
| 写入 150 条 (> 100) + 重启 | 数据完整 |
| 写入 200 条 (> 100) + 重启 | 数据完整 |
| CRUD 操作 + 重启 | 数据完整 |

---

## 14. 常见问题

### Q: 如何查看数据库中有哪些文档？
A: 运行 `python db_manage.py list`

### Q: 如何添加新文档到向量库？
A: 将文档放入 `data/docs/`，然后运行 `python db_manage.py add data/docs/新文档.txt`

### Q: 增量更新会重新向量化旧数据吗？
A: 不会。系统通过 content_hash 检测变化，只处理变化的文件。

### Q: sync_threshold 应该设置为多少？
A: 推荐 100。测试证明在所有场景下都能正常工作。

### Q: 前端 node_modules 如何生成？
A: 进入 `frontend/` 目录运行 `npm install`，根据 `package-lock.json` 自动下载所有依赖。

### Q: 如何启用 Rerank？
A: 在 `config/.env` 中设置 `RERANK_ENABLED=true`，并确保 Rerank 服务已启动（`python -m servers.rerank`）。

### Q: 支持哪些文档格式？
A: 支持 PDF、DOCX、TXT、MD、PY、JS、TS、JAVA、C、CPP、GO、RS、R、SH、SQL、JSON、YAML、CSV、XML、TOML、HTML、CSS 等 30+ 种格式。

### Q: 如何切换 Embedding 模型？
A: 修改 `config/.env` 中的 `EMBEDDING_MODEL` 和 `EMBEDDING_DIM`，然后重启服务并重建向量库。

---

## 15. 版本历史

| 版本 | 说明 |
|------|------|
| V1.0.0 | 完整版本：后端 API + 前端 Web UI + MCP 服务 + 配置管理 + 服务管理 |
| V0.0.17 | 底层完善版本 |
| V0.0.16 | 优化版本 |
| V0.0.15 | 所有逻辑系统优化版本 |
| V0.0.14 | 优化项目逻辑 |
| V0.0.13 | 优化框架和修复部分 bug |
| V0.0.10 | 优化切片逻辑，补充切片模板 |
| V0.0.9 | GPU 加速 + 更长响应时间的 embedding + reranker |
| V0.0.8 | 补充 reranker |
| V0.0.7 | 优化版本 |
| V0.0.6 | 进一步优化数据库原子性 |
| V0.0.5 | 实现队列调度 lmstudio 请求 |
| V0.0.4 | ACID 完善 |
| V0.0.2 | 测试 Client-Server ChromaDB |
| V0.0.1 | 本地数据库初版 |
