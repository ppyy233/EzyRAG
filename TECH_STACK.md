# Ezy-RAG V0.0.17 技术栈报告

## 1. 项目概述

Ezy-RAG 是一个本地化部署的检索增强生成（RAG）知识库系统，支持多种文档格式的向量化存储、语义检索和智能问答。

### 1.1 核心特性
- **双模式部署**：支持本地模型和云端API自由切换
- **原子性操作**：基于影子集合策略的ACID事务保证
- **优先级调度**：查询请求优先于建库请求处理
- **多格式支持**：30+文档格式（PDF/Word/TXT/代码等）
- **增量更新**：智能检测文档变化，零开销跳过未变文件

---

## 2. 项目目录结构

```
Ezy-RAG/
├── config/                     # 配置中心
│   ├── .env                    # 环境变量（API Key等敏感信息）
│   ├── .env.example            # 环境变量模板
│   ├── config.json             # 业务配置（切片模板、检索参数）
│   └── settings.py             # 配置加载模块
│
├── core/                       # 核心业务层
│   ├── __init__.py
│   ├── builder.py              # 知识库构建（文档加载/切片/向量化）
│   ├── repository.py           # 文档仓库（CRUD/影子集合/ACID事务）
│   └── scheduler.py            # 任务调度器（优先级队列/OpenAI兼容）
│
├── local/                      # 本地模型服务层
│   ├── __init__.py
│   ├── embedding.py            # Embedding服务（sentence-transformers）
│   └── rerank.py               # Rerank服务（CrossEncoder）
│
├── servers/                    # 服务层
│   ├── __init__.py
│   ├── chroma.py               # ChromaDB服务（向量数据库）
│   └── mcp.py                  # MCP服务（查询接口/Rerank聚合）
│
├── data/                       # 数据目录
│   ├── docs/                   # 本地文档
│   ├── web/                    # 网页爬取数据
│   ├── chroma_db/              # ChromaDB持久化
│   └── models/                 # 本地模型文件
│       ├── embedding/          # Embedding模型
│       └── rerank/             # Rerank模型
│
├── runtime/                    # 运行时目录
│   ├── logs/                   # 日志文件
│   └── state/                  # 状态文件（集合指针等）
│
├── tests/                      # 测试目录
│   ├── test_all.py             # 基础功能测试
│   ├── test_core.py            # 核心模块测试
│   └── generate_report.py      # 测试报告生成
│
├── init.py                     # 配置管理脚本
├── start_all.py                # 服务管理脚本
├── db_manage.py                # 数据库管理工具
├── ezyrag.py                   # CLI入口
├── pyproject.toml              # 项目配置
└── uv.lock                     # 依赖锁文件
```

---

## 3. 技术栈详解

### 3.1 运行环境

| 组件 | 版本/规格 | 说明 |
|------|-----------|------|
| Python | 3.11 | 主运行环境 |
| 操作系统 | Windows 10/11 x64 | 主要部署平台 |
| 包管理器 | uv | 高性能Python包管理器 |
| CUDA | 12.4 | GPU加速支持 |

### 3.2 核心依赖

| 依赖库 | 版本 | 用途 |
|--------|------|------|
| **chromadb** | >=1.5.9 | 向量数据库 |
| **sentence-transformers** | >=5.5.0 | Embedding/Rerank模型 |
| **torch** | >=2.5.0,<2.7.0 | 深度学习框架 |
| **openai** | >=2.36.0 | OpenAI API兼容 |
| **fastapi** | >=0.136.1 | Web框架 |
| **uvicorn** | >=0.46.0 | ASGI服务器 |
| **mcp** | >=1.27.1 | MCP协议支持 |

### 3.3 文档处理依赖

| 依赖库 | 版本 | 用途 |
|--------|------|------|
| **pypdf** | >=6.11.0 | PDF解析 |
| **python-docx** | >=1.2.0 | Word文档解析 |
| **beautifulsoup4** | >=4.12.0 | 网页内容提取 |
| **requests** | >=2.28.0 | HTTP客户端 |

---

## 4. 架构设计

### 4.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI入口层                               │
│                    ezyrag.py / init.py                       │
├─────────────────────────────────────────────────────────────┤
│                      服务管理层                              │
│                  start_all.py / db_manage.py                 │
├─────────────────────────────────────────────────────────────┤
│                      服务层                                  │
│            servers/chroma.py / servers/mcp.py                │
├─────────────────────────────────────────────────────────────┤
│                      本地模型层                              │
│          local/embedding.py / local/rerank.py                │
├─────────────────────────────────────────────────────────────┤
│                      核心业务层                              │
│    core/builder.py / core/repository.py / core/scheduler.py  │
├─────────────────────────────────────────────────────────────┤
│                      配置层                                  │
│               config/settings.py / config.json               │
├─────────────────────────────────────────────────────────────┤
│                      存储层                                  │
│              ChromaDB / 文件系统 / 指针文件                   │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 数据流

```
用户查询 → MCP服务 → Scheduler → Embedding向量化 → ChromaDB检索
                ↓
           [可选] Rerank重排 → 返回结果

建库流程 → Builder → 文档加载 → 切片 → Scheduler → Embedding向量化 → ChromaDB存储
```

### 4.3 服务依赖关系

```
MCP服务 (9766)
  ├── 依赖: ChromaDB服务 (9898)
  ├── 依赖: Embedding服务 (本地1234 / 云端API)
  └── 可选: Rerank服务 (本地5001 / 云端API)

ChromaDB服务 (9898)
  └── 独立运行

Embedding服务 (1234)
  └── 独立运行（本地模式）

Rerank服务 (5001)
  └── 独立运行（本地模式）
```

---

## 5. 核心模块详解

### 5.1 core/scheduler.py - 任务调度器

**职责**：统一管理Embedding请求，实现优先级队列调度

**核心设计**：
```python
class TaskScheduler:
    _queue = PriorityQueue()  # 优先级队列
    
    # 优先级定义
    # priority=0   → VIP查询（高优先级）
    # priority=100 → 建库（低优先级）
```

**关键方法**：
- `embed_sync(texts, priority)` - 同步Embedding（建库使用）
- `embed_async(texts, priority)` - 异步Embedding（查询使用）

**设计优势**：
- 查询请求优先于建库请求处理
- 支持多提供商自动适配（OpenAI/Cohere/Jina）
- 动态维度支持

### 5.2 core/repository.py - 文档仓库

**职责**：封装所有向量数据库操作，实现文档级CRUD和ACID事务

**核心设计**：
```python
class DocumentRepository:
    def __init__(self, collection, emb_proxy, chroma_client=None, collection_name=None):
        self.collection = collection
        self.emb_proxy = emb_proxy
        self.chroma_client = chroma_client  # 用于影子集合策略
        self.collection_name = collection_name
```

**关键方法**：
- `add(doc, chunk_cfg)` - 添加文档
- `update(doc, chunk_cfg)` - 更新文档（影子集合策略）
- `delete(source)` - 删除文档
- `sync(documents, chunk_cfg)` - 同步文档（影子集合策略）
- `cleanup_duplicates()` - 清理重复数据

**ACID保证 - 影子集合策略**：
```
1. 创建影子集合（{name}_v{timestamp}）
2. 复制所有数据到影子集合
3. 在影子集合中执行变更
4. 验证数据完整性
5. 切换指针到影子集合
6. 删除旧集合
```

### 5.3 core/builder.py - 知识库构建器

**职责**：文档加载、切片、向量化、存储

**核心设计**：
- **全量重建**：删除旧集合，重新创建并添加所有文档
- **增量更新**：通过Repository实现文档级CRUD

**切片策略**：
```python
# recursive策略（推荐）
段落 → 句子 → 字符，保留学术文献的段落完整性

# flat策略（兼容旧逻辑）
扁平切片，不保留段落结构
```

**支持格式**：
```python
SUPPORTED_EXT = {
    ".pdf", ".docx", ".txt", ".md",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs",
    ".json", ".yaml", ".yml", ".csv", ".xml", ".toml",
    # ... 30+格式
}
```

### 5.4 config/settings.py - 配置中心

**职责**：统一管理所有配置，支持.env和config.json

**关键函数**：
```python
# Embedding配置
get_embedding_mode()      # local / cloud
get_embedding_config()    # 完整配置

# Rerank配置
get_rerank_mode()         # local / cloud
get_rerank_enabled()      # true / false
get_rerank_config()       # 完整配置

# 业务配置
get_collection_name()     # 集合名称
get_chunk_config()        # 切片模板
get_retrieval_config()    # 检索参数
```

---

## 6. 双模式设计

### 6.1 Embedding双模式

**本地模式**：
```
EMBEDDING_MODE=local
EMBEDDING_LOCAL_URL=http://127.0.0.1:1234/v1/embeddings
EMBEDDING_LOCAL_MODEL_PATH=data/models/embedding
EMBEDDING_LOCAL_DIM=1024
```

**云端模式**：
```
EMBEDDING_MODE=cloud
EMBEDDING_CLOUD_URL=https://api.siliconflow.cn/v1/embeddings
EMBEDDING_CLOUD_API_KEY=sk-xxx
EMBEDDING_CLOUD_MODEL=BAAI/bge-m3
EMBEDDING_CLOUD_DIM=1024
```

### 6.2 Rerank双模式

**本地模式**：
```
RERANK_MODE=local
RERANK_LOCAL_URL=http://127.0.0.1:5001
RERANK_LOCAL_MODEL_PATH=data/models/rerank
```

**云端模式**：
```
RERANK_MODE=cloud
RERANK_CLOUD_URL=https://api.cohere.com/v1/rerank
RERANK_CLOUD_API_KEY=xxx
RERANK_CLOUD_MODEL=rerank-multilingual-v3.0
```

---

## 7. 服务管理

### 7.1 服务启动

```bash
# 启动所有服务
python start_all.py

# 单独启动服务
python -m servers.chroma      # ChromaDB服务
python -m servers.mcp         # MCP服务
python -m local.embedding     # Embedding服务（本地模式）
python -m local.rerank        # Rerank服务（本地模式）
```

### 7.2 数据库管理

```bash
# 查看状态
python db_manage.py status

# 添加文档
python db_manage.py add --all

# 同步文档
python db_manage.py sync

# 全量重建
python db_manage.py rebuild
```

---

## 8. 测试覆盖

### 8.1 测试套件

| 测试套件 | 测试数 | 通过率 | 覆盖内容 |
|----------|--------|--------|----------|
| test_all.py | 30 | 100% | 基础功能、配置、模块导入 |
| test_core.py | 25 | 100% | 异步并发、ACID事务、影子集合 |

### 8.2 关键测试用例

- **异步并发测试**：验证查询和建库能同时进行
- **ACID事务测试**：验证影子集合策略的原子性
- **异常恢复测试**：验证异常情况下数据不丢失

---

## 9. 部署建议

### 9.1 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 4核 | 8核+ |
| 内存 | 8GB | 16GB+ |
| GPU | 无（CPU模式） | NVIDIA GPU（CUDA 12.4） |
| 存储 | 10GB | 50GB+（含模型） |

### 9.2 软件要求

- Windows 10/11 x64
- Python 3.11
- CUDA 12.4（GPU模式）

### 9.3 快速部署

```bash
# 1. 安装依赖
uv sync

# 2. 初始化配置
python init.py

# 3. 下载模型（本地模式）
# 将模型文件放入 data/models/embedding/ 和 data/models/rerank/

# 4. 启动服务
python start_all.py

# 5. 添加文档
python db_manage.py add --all

# 6. 查询测试
python ezyrag.py
```

---

## 10. 技术亮点

1. **影子集合策略**：保证update和sync操作的原子性，异常情况下数据不丢失
2. **优先级队列**：查询请求优先于建库请求处理，提升用户体验
3. **双模式切换**：本地模型和云端API自由切换，灵活部署
4. **增量更新**：智能检测文档变化，零开销跳过未变文件
5. **30+格式支持**：覆盖常见文档和代码格式
6. **完善的测试**：55个测试用例，100%通过率

---

## 11. 版本信息

- **版本号**：V0.0.17
- **Python版本**：3.11
- **主要依赖**：ChromaDB >=1.5.9, sentence-transformers >=5.5.0
- **许可证**：待定
- **仓库**：CLI-Ezy-RAG分支
