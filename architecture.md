# Ezy-RAG 系统架构文档

**版本：** 1.0.0

## 1. 项目概述

Ezy-RAG 是一个知识库系统，提供文档管理、向量检索、智能问答等功能。项目采用四层架构设计，实现了清晰的职责分离和模块化管理。

**技术栈：**
- 后端：Python 3.11+、FastAPI、ChromaDB
- 前端：Vue 3、Element Plus、Vite
- 向量模型：BAAI/bge-m3（云端/本地）

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                      交互层 (Interaction Layer)                  │
│  ┌───────────────────────────────┐  ┌─────────────────────────┐ │
│  │         CLI 命令行界面         │  │       Web 前端界面       │ │
│  │    python ezyrag.py [cmd]     │  │   Vue 3 + Element Plus  │ │
│  └───────────────────────────────┘  └─────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                      服务层 (Service Layer)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ web.py   │  │chroma.py │  │embedding │  │ rerank   │       │
│  │ Web API  │  │ ChromaDB │  │  服务    │  │  服务    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
├─────────────────────────────────────────────────────────────────┤
│                      核心层 (Core Layer)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │database  │  │chunking  │  │document  │  │   api    │       │
│  │数据库操作│  │文本切分  │  │文档处理  │  │API适配器 │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
├─────────────────────────────────────────────────────────────────┤
│                      配置层 (Config Layer)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ .env     │  │config.json│  │settings  │  │ pointer  │       │
│  │环境变量  │  │应用配置  │  │配置加载  │  │指针管理  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 目录结构

```
Ezy-RAG/
├── config/                      # 配置层
│   ├── .env                     # 环境变量配置
│   ├── .env.example             # 环境变量模板
│   ├── config.json              # 应用配置
│   ├── settings.py              # 配置加载模块
│   ├── pointer.py               # 集合指针管理
│   └── version.py               # 版本信息
│
├── core/                        # 核心层
│   ├── api.py                   # Embedding/Rerank API 适配器
│   ├── chunking.py              # 文本切分模块
│   ├── database.py              # 数据库操作模块
│   ├── document.py              # 文档处理模块
│   ├── maintenance.py           # 维护工具模块
│   ├── scheduler.py             # 任务调度器
│   └── utils.py                 # 工具函数
│
├── servers/                     # 服务层
│   ├── chroma.py                # ChromaDB 服务
│   ├── embedding.py             # Embedding 服务
│   ├── rerank.py                # Rerank 服务
│   ├── mcp.py                   # MCP 服务
│   └── web.py                   # Web API 服务器
│
├── cli/                         # CLI 交互层
│   ├── cli_core.py              # CLI 公共逻辑
│   ├── db_manage.py             # 文档管理
│   ├── ezyrag.py                # 主入口
│   ├── init.py                  # 配置管理
│   ├── start_all.py             # 服务管理
│   └── ui.py                    # 终端 UI 工具
│
├── frontend/                    # Web 前端
│   ├── src/
│   │   ├── views/               # 页面组件
│   │   ├── api/                 # API 调用
│   │   ├── components/          # 公共组件
│   │   ├── composables/         # 组合式函数
│   │   ├── router/              # 路由配置
│   │   └── styles/              # 样式文件
│   └── package.json
│
├── data/                        # 数据目录
│   ├── docs/                    # 本地文档
│   ├── web/                     # 爬取的网页
│   ├── chroma_db/               # ChromaDB 数据
│   └── models/                  # 模型文件
│
├── runtime/                     # 运行时数据
│   ├── logs/                    # 日志文件
│   └── state/                   # 状态文件
│
└── pyproject.toml               # 项目配置
```

---

## 4. 配置层 (Config Layer)

配置层负责管理系统的所有配置参数，提供统一的配置加载和访问接口。

### 4.1 文件说明

| 文件 | 说明 |
|------|------|
| `.env` | 环境变量配置（敏感信息、服务地址） |
| `.env.example` | 环境变量模板 |
| `config.json` | 应用配置（切片模板、HNSW参数、检索参数） |
| `settings.py` | 配置加载模块（统一配置访问接口） |
| `pointer.py` | 集合指针管理（原子写入） |

### 4.2 环境变量 (.env)

```bash
# Embedding 配置
EMBEDDING_MODE=cloud          # cloud 或 local
EMBEDDING_CLOUD_URL=https://api.siliconflow.cn/v1/embeddings
EMBEDDING_CLOUD_API_KEY=your-api-key
EMBEDDING_CLOUD_MODEL=BAAI/bge-m3

# Rerank 配置
RERANK_ENABLED=true
RERANK_MODE=local
RERANK_LOCAL_URL=http://127.0.0.1:5001

# 服务配置
CHROMA_SERVER_HOST=127.0.0.1
CHROMA_SERVER_PORT=9898
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=9766

# 切块策略
CHUNK_TEMPLATE=academic
```

### 4.3 应用配置 (config.json)

```json
{
  "collection": {
    "name": "default_collection"
  },
  "docs": {
    "dir": "data/docs"
  },
  "web": {
    "dir": "data/web"
  },
  "chunk": {
    "templates": {
      "academic": {
        "name": "英文文献专用",
        "chunk_size": 2000,
        "overlap": 200,
        "strategy": "recursive",
        "separators": ["\n\n", "\n", ...]
      },
      "chinese": { ... },
      "code": { ... },
      "custom": { ... }
    },
    "default_template": "academic"
  },
  "hnsw": {
    "space": "cosine",
    "M": 16,
    "sync_threshold": 1000,
    "batch_size": 100
  },
  "retrieval": {
    "k": 5,
    "fetch_k": 15
  }
}
```

### 4.4 核心接口

```python
# settings.py
def load_config() -> dict                    # 加载 config.json
def save_config(config: dict)                # 保存 config.json
def get_collection_name() -> str             # 获取集合名称
def get_chunk_config(template=None) -> dict  # 获取切片配置
def get_hnsw_config() -> dict                # 获取 HNSW 配置
def get_chroma_hnsw_metadata() -> dict       # 获取 ChromaDB 兼容的 HNSW 元数据
def get_retrieval_config() -> dict           # 获取检索配置
def get_embedding_config() -> dict           # 获取 Embedding 配置
def get_rerank_config() -> dict              # 获取 Rerank 配置

# pointer.py
def get_active_collection(key: str) -> str   # 获取活跃集合名
def set_active_collection(key: str, name: str) # 设置活跃集合名
```

---

## 5. 核心层 (Core Layer)

核心层实现系统的核心业务逻辑，包括文档处理、文本切分、数据库操作、API 适配等。

### 5.1 模块说明

| 模块 | 职责 | 关键类/函数 |
|------|------|------------|
| `api.py` | Embedding/Rerank API 适配器 | `EmbeddingAPI`, `RerankAPI` |
| `chunking.py` | 文本切分 | `split_text()`, `chunk_single_document()` |
| `database.py` | 数据库操作（CRUD + ACID） | `DocumentDatabase` |
| `document.py` | 文档读取和加载 | `read_file()`, `load_all_documents()`, `get_document_paths()` |
| `maintenance.py` | 维护和清理工具 | `validate_hnsw()`, `cleanup_orphan_shadows()` |
| `scheduler.py` | 任务调度器 | `TaskScheduler`, `get_scheduler()` |
| `utils.py` | 工具函数 | `content_hash()`, `md5_short()` |

### 5.2 核心模块详解

#### 5.2.1 API 适配器 (api.py)

管理 Embedding 和 Rerank 的云端/本地模式，提供统一的接口。

```python
class EmbeddingAPI:
    """统一的 Embedding API 适配器"""
    
    def __init__(self):
        # 根据 EMBEDDING_MODE 自动选择云端或本地
        self._mode = "cloud" | "local"
        self._provider = "openai" | "cohere"
        self._model = "BAAI/bge-m3"
    
    def embed(self, texts: list[str]) -> list[list[float]]:
        """同步向量化"""
        
    async def embed_async(self, texts: list[str]) -> list[list[float]]:
        """异步向量化"""
    
    def health_check(self) -> tuple[bool, str]:
        """健康检查"""
    
    def get_info(self) -> dict:
        """返回配置信息"""


class RerankAPI:
    """统一的 Rerank API 适配器"""
    
    def rerank(self, query: str, documents: list[str]) -> tuple[list[float], list[int]]:
        """同步重排"""
    
    async def rerank_async(self, query: str, documents: list[str]) -> tuple[list[float], list[int]]:
        """异步重排"""
```

#### 5.2.2 文本切分 (chunking.py)

提供多种文本切分策略，支持递归切分和扁平切分。

```python
def split_text(text: str, cfg: dict) -> List[str]:
    """按模板配置切片"""
    
def chunk_single_document(doc: dict, chunk_cfg: dict, source_type: str = "local_file") -> List[dict]:
    """对单个文档切片，生成带元数据的 chunk 列表"""
```

**切片策略：**
- `recursive`：递归分层切片（段落 → 句子 → 字符）
- `flat`：扁平切片

#### 5.2.3 数据库操作 (database.py)

提供 ChromaDB 的 CRUD 操作和 ACID 事务支持。

```python
class DocumentDatabase:
    """
    统一的数据库操作类
    
    ACID 策略：
    - add:     直接写入 + 幂等
    - delete:  直接删除（原子操作）
    - update:  直接操作
    - sync:    直接操作（增量）
    - rebuild: 影子集合策略（全量重建）
    """
    
    # 读操作
    def count(self) -> int
    def exists(self, source: str) -> bool
    def get_hash(self, source: str) -> Optional[str]
    def list_documents(self) -> List[dict]
    def list_sources(self) -> set
    def search(self, query_vec, n_results=5)
    
    # 写操作
    def add(self, doc: dict, chunk_cfg: dict, source_type: str = "local_file") -> int
    def delete(self, source: str)
    def update(self, doc: dict, chunk_cfg: dict, source_type: str = "local_file") -> int
    def sync(self, documents: List[dict], chunk_cfg: dict, ...) -> dict
    def rebuild(self, documents: List[dict], chunk_cfg: dict, ...) -> int
    
    # 维护操作
    def check_orphan_records(self, *local_dirs: str) -> List[dict]
    def clean_orphan_records(self, *local_dirs: str) -> int
```

**同步策略优化：**
- 使用延迟加载，只读取变化的文件
- 直接操作，不使用影子集合
- 每个 add/delete 操作都是原子的

#### 5.2.4 文档处理 (document.py)

提供文件读取和文档加载功能。

```python
# 文件读取
def read_pdf(filepath: str) -> str
def read_docx(filepath: str) -> str
def read_txt(filepath: str) -> str
def read_file(filepath: str) -> str

# 文档加载
def load_all_documents(*dirs: Path) -> List[dict]
def get_document_paths(*dirs: Path) -> List[str]

# 支持的文件扩展名
SUPPORTED_EXT = {
    ".pdf": read_pdf, ".docx": read_docx, ".txt": read_txt, ".md": read_md,
    ".py": read_txt, ".js": read_txt, ...
}
```

#### 5.2.5 任务调度器 (scheduler.py)

支持 Embedding 的优先级队列调度，确保建库和查询请求互不阻塞。

```python
class TaskScheduler:
    """优先级队列调度器"""
    
    def embed_sync(self, texts, priority=100, timeout=300):
        """同步 embedding（priority=0 为 VIP 查询）"""
    
    async def embed_async(self, texts, priority=0, timeout=60):
        """异步 embedding"""

def get_scheduler() -> TaskScheduler:
    """获取全局单例调度器"""
```

---

## 6. 服务层 (Service Layer)

服务层提供各种后端服务，包括 Web API、ChromaDB、Embedding、Rerank、MCP 等。

### 6.1 服务列表

| 服务 | 端口 | 说明 |
|------|------|------|
| Web API | 9767 | REST API + 静态文件托管 |
| ChromaDB | 9898 | 向量数据库 |
| Embedding | 1234 | 本地 Embedding 服务（可选） |
| Rerank | 5001 | 本地 Rerank 服务（可选） |
| MCP | 9766 | MCP 服务 |

### 6.2 Web API 服务器 (web.py)

提供 REST API 接口和前端静态文件托管。

**API 端点：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/system/health` | GET | 系统健康检查 |
| `/api/system/status` | GET | 系统状态 |
| `/api/config` | GET/PUT | 获取/更新配置 |
| `/api/documents` | GET | 文档列表 |
| `/api/documents/import` | POST | 导入文档 |
| `/api/documents/import-all` | POST | 导入所有文档 |
| `/api/documents/sync` | POST | 同步文档 |
| `/api/documents/rebuild` | POST | 重建向量库 |
| `/api/documents/crawl` | POST | 爬取网页 |
| `/api/search` | POST | 搜索知识库 |
| `/api/services/start` | POST | 启动服务 |
| `/api/services/stop` | POST | 停止服务 |
| `/ws` | WebSocket | 实时进度推送 |

**搜索流程：**
```
用户查询 → EmbeddingAPI 向量化 → ChromaDB 检索 → RerankAPI 重排 → 返回结果
```

### 6.3 ChromaDB 服务 (chroma.py)

启动 ChromaDB 向量数据库服务。

### 6.4 Embedding 服务 (embedding.py)

启动本地 Embedding 服务（可选，云端模式无需启动）。

### 6.5 Rerank 服务 (rerank.py)

启动本地 Rerank 服务（可选，云端模式无需启动）。

### 6.6 MCP 服务 (mcp.py)

启动 MCP（Model Context Protocol）服务。

---

## 7. 交互层 (Interaction Layer)

交互层提供用户与系统交互的界面，包括 CLI 命令行界面和 Web 前端界面。

### 7.1 CLI 命令行界面

#### 7.1.1 主入口 (ezyrag.py)

```bash
# 使用方式
python ezyrag.py                    # 交互式菜单
python ezyrag.py quickstart         # 快速开始向导
python ezyrag.py service            # 服务管理
python ezyrag.py db                 # 文档管理
python ezyrag.py config             # 配置管理
python ezyrag.py health             # 健康检查
```

**菜单结构：**
```
┌─────────────────────────────────────────────────┐
  Ezy-RAG V0.0.18 知识库系统
═══════════════════════════════════════════════════
  1. 快速开始
  2. 服务管理
  3. 文档管理
  4. 配置管理
  5. 健康检查
  6. 退出
─────────────────────────────────────────────────
```

#### 7.1.2 文档管理 (db_manage.py)

```
操作:
1. 查看文档列表    # 支持数据源选择（all/docs/web）
2. 添加文档        # 输入文档名称，自动匹配
3. 批量添加        # 空格/逗号分隔
4. 删除文档        # 删除向量记录
5. 批量删除
6. 全部删除        # 删除所有向量记录
7. 网页爬取        # 爬取单个/批量网页
8. 同步文档        # 增量同步（延迟加载）
9. 全量重建        # 影子集合策略
10. 清理孤立
11. 返回
```

**数据源选择：**
```
选择数据源:
1. 所有数据 (docs + web)
2. 仅本地文档 (docs)
3. 仅网页数据 (web)
```

#### 7.1.3 服务管理 (start_all.py)

```
操作:
1. 启动全部
2. 停止全部
3. 刷新状态
4. 返回
```

#### 7.1.4 配置管理 (init.py)

```
操作:
1. 修改 Embedding 配置
2. 修改 Rerank 配置
3. 修改服务配置
4. 修改切块策略
5. 重置配置
6. 返回
```

#### 7.1.5 终端 UI 工具 (ui.py)

提供统一的终端 UI 组件：

```python
def header(title, desc)           # 标题栏
def status_card(services)         # 服务状态卡片
def info_card(title, items)       # 信息卡片
def table(headers, rows)          # 表格
def menu(title, options)          # 菜单选择
def select_data_source()          # 数据源选择
def confirm(message)              # 确认对话框
def log_ok/log_error/log_info()   # 日志输出
def progress_bar(current, total)  # 进度条
```

#### 7.1.6 CLI 公共逻辑 (cli_core.py)

```python
def check_port(host, port) -> bool          # 检查端口
def get_service_status() -> dict            # 获取服务状态
def connect_chroma() -> (client, db)        # 连接 ChromaDB
def get_local_documents(source) -> list     # 获取本地文档
def get_database_stats() -> dict            # 获取数据库统计
def get_document_list(source) -> list       # 获取文档列表
```

### 7.2 Web 前端界面

基于 Vue 3 + Element Plus 构建的响应式前端。

#### 7.2.1 页面结构

| 页面 | 路由 | 说明 |
|------|------|------|
| Home | `/` | 系统概览 |
| Documents | `/documents` | 文档管理 |
| Search | `/search` | 知识库搜索 |
| Config | `/config` | 配置管理 |
| Services | `/services` | 服务管理 |

#### 7.2.2 API 调用 (api/index.js)

```javascript
export const systemApi = {
  health: () => api.get('/system/health'),
  status: () => api.get('/system/status')
}

export const documentsApi = {
  list: () => api.get('/documents'),
  importFiles: (files) => api.post('/documents/import', { files }),
  sync: () => api.post('/documents/sync'),
  rebuild: () => api.post('/documents/rebuild'),
  crawl: (url) => api.post('/documents/crawl', { url })
}

export const searchApi = {
  search: (query) => api.post('/search', { query })
}
```

---

## 8. 数据流

### 8.1 文档导入流程

```
本地文件/网页 → 读取内容 → 文本切分 → Embedding 向量化 → 存入 ChromaDB
```

### 8.2 搜索流程

```
用户查询 → Embedding 向量化 → ChromaDB 检索 → Rerank 重排 → 返回结果
```

### 8.3 同步流程

```
获取本地文件路径 → 对比向量库 → 计算差异
├── 新增文档：读取内容 → 切分 → 向量化 → 存入
├── 更新文档：读取内容 → 对比 hash → 重新切分 → 向量化 → 更新
└── 删除文档：删除向量记录
```

### 8.4 重建流程

```
创建影子集合 → 读取所有文档 → 切分 → 向量化 → 验证 → 切换指针 → 清理旧集合
```

---

## 9. 设计原则

### 9.1 对称设计

本地文档（`data/docs`）和网页数据（`data/web`）使用相同的处理流程：

- **数据源区分**：两个目录分别存放
- **操作统一**：相同的 CRUD、同步、重建逻辑
- **数据源选择**：支持 all/docs/web 三种范围

### 9.2 延迟加载

同步操作使用延迟加载，只读取变化的文件：

- **路径对比**：先获取文件路径列表
- **差异计算**：对比路径和 hash
- **按需读取**：只读取需要处理的文件

### 9.3 最终一致性

同步操作采用直接操作策略：

- **原子操作**：每个 add/delete 都是原子的
- **可恢复**：中途停止可重新运行 sync 修复
- **高性能**：不使用影子集合，性能提升明显

### 9.4 配置可扩展

- **HNSW 参数**：可在 config.json 中配置
- **切片模板**：支持自定义模板
- **检索参数**：k、fetch_k 可调

---

## 10. 部署和运行

### 10.1 环境要求

- Python 3.11+
- uv（包管理器）
- Node.js（前端构建）

### 10.2 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 配置环境
cp config/.env.example config/.env
# 编辑 config/.env 填写 API Key

# 3. 启动服务
python -m servers.web

# 4. 访问前端
# http://127.0.0.1:9767
```

### 10.3 CLI 使用

```bash
# 快速开始
python ezyrag.py quickstart

# 服务管理
python ezyrag.py service

# 文档管理
python ezyrag.py db

# 健康检查
python ezyrag.py health
```

---

## 11. 扩展和优化

### 11.1 已实现的优化

- ✅ HNSW 参数可配置化
- ✅ 同步使用延迟加载
- ✅ 数据源选择（docs/web/all）
- ✅ 网页爬取保存到本地
- ✅ 全部删除功能

### 11.2 待优化项

- 混合检索（BM25 + 向量）
- 语义切分（Semantic Chunking）
- 查询重构（Query Rewriting）
- 检索评估系统
- Graph RAG 支持
