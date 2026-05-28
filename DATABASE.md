# Ezy-RAG V0.0.14 技术文档

## 1. 系统概述

Ezy-RAG 是一个基于向量数据库的知识库系统，支持文档的切片、向量化、存储和检索。

### 核心理念

**本地库和向量库分离管理**：
- 本地库（`data/docs/`）：用户管理的原始文档
- 向量库（ChromaDB）：系统管理的向量数据
- 两者通过 `source` 字段建立映射关系

---

## 2. 项目结构

```
E:\桌面\RAG\
├── config/                     # 配置文件
│   ├── .env                    # 环境变量（不入 Git）
│   ├── .env.example            # 配置模板（入 Git）
│   ├── config.json             # 业务配置
│   └── settings.py             # 配置加载模块
│
├── core/                       # 核心业务逻辑
│   ├── builder.py              # 知识库构建（全量/增量）
│   ├── embedder.py             # Embedding 代理
│   └── repository.py           # 文档仓库（CRUD 封装）
│
├── servers/                    # 服务启动脚本
│   ├── chroma.py               # ChromaDB Server
│   ├── mcp.py                  # MCP Server（查询接口）
│   └── rerank.py               # Rerank Server
│
├── data/                       # 数据目录
│   ├── docs/                   # 本地文档库
│   ├── chroma_db/              # 向量数据库存储
│   └── models/                 # 模型文件
│
├── runtime/                    # 运行时数据（不入 Git）
│   ├── logs/                   # 日志
│   └── state/                  # 状态文件（集合指针）
│
├── db_manage.py                # 数据库管理脚本
├── start_all.py                # 服务管理脚本
├── init.py                     # 配置管理脚本
├── db.bat                      # 数据库管理快捷方式
├── start.bat                   # 服务管理快捷方式
└── DATABASE.md                 # 数据库架构文档
```

---

## 3. 配置系统

### 3.1 配置分层

| 文件 | 类型 | 内容 | 入 Git |
|------|------|------|--------|
| `.env` | 环境变量 | IP、端口、API Key | 否 |
| `.env.example` | 模板 | .env 的示例 | 是 |
| `config.json` | 业务配置 | 切片模板、检索参数 | 是 |
| `settings.py` | 加载器 | 加载上述文件 | 是 |

### 3.2 环境变量（.env）

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

### 3.3 业务配置（config.json）

```json
{
  "collection": {"name": "default_collection"},
  "docs": {"dir": "data/docs"},
  "chroma": {"dir": "data/chroma_db"},
  "chunk": {
    "templates": {
      "academic": {"name": "英文文献专用", "chunk_size": 2000, "overlap": 200, "strategy": "recursive"},
      "chinese":  {"name": "中文专用", "chunk_size": 1500, "overlap": 150, "strategy": "recursive"},
      "code":     {"name": "代码专用", "chunk_size": 3000, "overlap": 300, "strategy": "flat"},
      "custom":   {"name": "自定义模板", "chunk_size": 1000, "overlap": 100, "strategy": "recursive"}
    },
    "default_template": "academic"
  },
  "retrieval": {"k": 5, "fetch_k": 15, "lambda": 0.7, "threshold": 0.3}
}
```

---

## 4. 数据库架构

### 4.1 核心组件

```
用户操作
    ↓
db_manage.py / core/builder.py
    ↓
DocumentRepository (core/repository.py)
    ↓
ChromaDB (向量数据库)
    ↓
data/chroma_db/
```

### 4.2 DocumentRepository

**位置**：`core/repository.py`

**核心方法**：

| 方法 | 类型 | 说明 |
|------|------|------|
| `add(doc, chunk_cfg)` | Create | 添加单个文档 |
| `add_many(documents, chunk_cfg)` | Create | 批量添加文档 |
| `exists(source)` | Read | 检查文档是否存在 |
| `get_hash(source)` | Read | 获取文档的 content_hash |
| `list_documents()` | Read | 列出所有文档（映射表） |
| `get_document_info(source)` | Read | 获取单个文档详情 |
| `count()` | Read | 获取记录总数 |
| `update(doc, chunk_cfg)` | Update | 更新文档（Add-First 策略） |
| `delete(source)` | Delete | 删除文档 |
| `sync(documents, chunk_cfg)` | CRUD | 自动同步 |

### 4.3 元数据结构

每个 chunk 的元数据：

```python
{
    "source": "E:/桌面/RAG/data/docs/彭明旭.txt",  # 来源文档路径
    "chunk_index": 0,                              # 切片索引
    "content_hash": "86e70fca8a5ae452a2b4d97b09b1ac96"  # 文档内容哈希
}
```

### 4.4 ACID 特性

| 特性 | 实现方式 |
|------|----------|
| **原子性** | Add-First 策略：先加新 chunks，再删旧 chunks |
| **一致性** | content_hash 检测数据变化 |
| **隔离性** | 查询和写入分离，查询不中断 |
| **持久性** | sync_threshold=100 控制刷盘频率 |

### 4.5 sync_threshold 配置

**当前值**：100

**含义**：每积累 100 条记录就将 HNSW 索引持久化到磁盘

**测试验证**：
- 写入 50 条 (< 100) + 重启 → 数据完整
- 写入 100 条 (= 100) + 重启 → 数据完整
- 写入 200 条 (> 100) + 重启 → 数据完整

---

## 5. 用户操作指南

### 5.1 安装配置

```bash
# 1. 克隆项目
git clone <repo>

# 2. 安装依赖
uv sync

# 3. 初始化配置
python init.py

# 4. 启动服务
python start_all.py
```

### 5.2 数据库管理

```bash
# 查看文档映射表
python db_manage.py list

# 查看数据库状态
python db_manage.py status

# 添加单个文档
python db_manage.py add data/docs/new_doc.txt

# 添加多个文档
python db_manage.py add data/docs/doc1.txt data/docs/doc2.txt

# 添加所有本地文档
python db_manage.py add --all

# 删除单个文档
python db_manage.py delete data/docs/old_doc.txt

# 删除所有向量库文档
python db_manage.py delete --all

# 更新单个文档
python db_manage.py update data/docs/modified_doc.txt

# 更新所有向量库文档
python db_manage.py update --all

# 同步本地文件和向量库
python db_manage.py sync

# 全量重建向量库
python db_manage.py rebuild
```

### 5.3 知识库构建

```bash
# 增量更新（自动同步）
python -m core.builder

# 全量重建
python -m core.builder --full

# 指定切片模板
python -m core.builder --template chinese
```

### 5.4 查询服务

```bash
# 启动 MCP 服务
python -m servers.mcp

# 健康检查
curl http://127.0.0.1:9766/health
```

---

## 6. 服务管理

### 6.1 服务列表

| 服务 | 端口 | 说明 |
|------|------|------|
| ChromaDB | 9898 | 向量数据库 |
| MCP | 9766 | 查询接口 |
| Rerank | 5001 | 重排服务（可选） |
| LM Studio | 5000 | Embedding 服务（外部） |

### 6.2 服务管理

```bash
# 启动所有服务
python start_all.py

# 查看服务状态
python start_all.py  # 选择 1

# 启动单个服务
python start_all.py  # 选择 2

# 停止所有服务
python start_all.py  # 选择 3

# 重启服务
python start_all.py  # 选择 4
```

---

## 7. 测试验证

### 7.1 CRUD 测试

| 操作 | 命令 | 结果 |
|------|------|------|
| 添加单个文件 | `add data/docs/彭明旭.txt` | 1 chunk 添加 |
| 添加多个文件 | `add --all` | 219 chunks 添加 |
| 查看文档列表 | `list` | 34 个文档显示 |
| 删除所有文档 | `delete --all` | 35 个文档删除 |
| 更新单个文件 | `update data/docs/彭明旭.txt` | 1 chunk 更新 |
| 自动同步 | `sync` | 34 个文档同步 |

### 7.2 增量更新测试

| 场景 | 结果 |
|------|------|
| 无变化 | 0 个向量化，34 个未变 |
| 添加 1 个新文件 | 1 个向量化，34 个未变 |
| 修改 1 个文件 | 1 个向量化，33 个未变 |
| 删除 1 个文件 | 0 个向量化，1 个删除 |

### 7.3 sync_threshold 测试

| 场景 | 结果 |
|------|------|
| 写入 50 条 (< 100) + 重启 | 数据完整 |
| 写入 100 条 (= 100) + 重启 | 数据完整 |
| 写入 150 条 (> 100) + 重启 | 数据完整 |
| 写入 200 条 (> 100) + 重启 | 数据完整 |
| CRUD 操作 + 重启 | 数据完整 |

---

## 8. 常见问题

### Q: 如何查看数据库中有哪些文档？

A: 运行 `python db_manage.py list`

### Q: 如何添加新文档到向量库？

A: 将文档放入 `data/docs/`，然后运行 `python db_manage.py add data/docs/新文档.txt`

### Q: 如何删除向量库中的文档？

A: 运行 `python db_manage.py delete data/docs/文档.txt`

### Q: 如何修改切片模板？

A: 编辑 `config/config.json` 或运行 `python init.py`

### Q: 向量库有很多空文件夹怎么办？

A: 运行 `python db_manage.py` 选择"清理空文件夹"

### Q: 增量更新会重新向量化旧数据吗？

A: 不会。系统通过 content_hash 检测变化，只处理变化的文件。

### Q: sync_threshold 应该设置为多少？

A: 推荐 100。测试证明在所有场景下都能正常工作。
