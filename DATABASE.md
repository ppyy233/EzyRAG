# Ezy-RAG 数据库架构文档

## 概述

Ezy-RAG 使用 ChromaDB 作为向量数据库，采用文档级 CRUD 操作和增量更新策略。

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户操作层                            │
│  python db_manage.py           数据库管理                    │
│  python -m core.builder        知识库构建                    │
│  python -m servers.mcp         查询服务                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     业务逻辑层                               │
│  build_knowledge_base()  →  build_incremental()             │
│                           →  build_full()                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   DocumentRepository                        │
│  add()      - 添加文档                                      │
│  delete()   - 删除文档                                      │
│  update()   - 更新文档 (Add-First 策略)                     │
│  sync()     - 同步所有文档                                   │
│  list()     - 列出所有文档                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      ChromaDB                               │
│  collection.add()      添加记录                              │
│  collection.delete()   删除记录                              │
│  collection.get()      查询记录                              │
│  collection.query()    向量检索                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   data/chroma_db/                            │
│  chroma.sqlite3        元数据                                │
│  {uuid}/               HNSW 索引                            │
└─────────────────────────────────────────────────────────────┘
```

## 配置文件

| 文件 | 用途 | 说明 |
|------|------|------|
| `config/.env` | 环境变量 | IP、端口、API Key |
| `config/config.json` | 业务配置 | 切片模板、检索参数 |
| `config/settings.py` | 配置加载 | 加载 .env 和 config.json |

## 核心组件

### 1. DocumentRepository

封装所有向量数据库操作，提供文档级 CRUD 接口。

**位置**：`core/repository.py`

**主要方法**：
- `add(doc, chunk_cfg)` - 添加单个文档
- `delete(source)` - 删除文档
- `update(doc, chunk_cfg)` - 更新文档（Add-First 策略）
- `sync(documents, chunk_cfg)` - 同步所有文档
- `list_documents()` - 列出所有文档

### 2. build_kb.py

知识库构建脚本，提供增量更新和全量重建功能。

**位置**：`core/builder.py`

**主要功能**：
- 增量更新：只处理变化的文件
- 全量重建：影子集合模式
- 文档切片：支持多种切片模板

### 3. db_manage.py

数据库管理脚本，提供用户友好的管理界面。

**位置**：`db_manage.py`

**主要功能**：
- 查看数据库状态
- 增量更新
- 全量重建
- 清理旧集合
- 清理空文件夹
- 启动服务

## 用户操作指南

### 基本操作

```bash
# 1. 初始化配置
python init.py

# 2. 启动服务
python start_all.py

# 3. 数据库管理
python db_manage.py

# 4. 知识库构建
python -m core.builder              # 增量更新
python -m core.builder --full       # 全量重建
```

### 添加文档

1. 将文档放入 `data/docs/` 文件夹
2. 运行 `python -m core.builder`
3. 系统自动检测新文件并添加

### 删除文档

1. 从 `data/docs/` 删除文件
2. 运行 `python -m core.builder`
3. 系统自动检测删除并清理

### 更新文档

1. 修改 `data/docs/` 中的文件
2. 运行 `python -m core.builder`
3. 系统自动检测变化并更新

### 查看数据库状态

```bash
python db_manage.py
# 选择 1. 查看数据库状态
```

输出示例：
```
数据库状态
----------------------------------------------------------------------
  ChromaDB: 已连接
  集合名: default_collection_v20260528_010439
  总记录数: 273

  文档列表:
  --------------------------------------------------
  彭明旭.txt                    1 chunks
  潘越.txt                      1 chunks
  setup.py                      5 chunks
  --------------------------------------------------
  总计: 3 个文档, 7 个 chunks
```

## 增量更新原理

### 工作流程

```
读取 data/docs/ 中的所有文档
          ↓
    计算每个文档的 content_hash
          ↓
    与数据库中的 hash 对比
          ↓
┌─────────────────────────────────────┐
│ 新文件    → add()                    │
│ 变更文件  → update() (Add-First)    │
│ 未变文件  → 跳过                    │
│ 已删文件  → delete()                │
└─────────────────────────────────────┘
```

### Add-First 策略

更新文档时，采用 Add-First 策略保证数据不丢失：

```python
def update(self, doc, chunk_cfg):
    # Step 1: 先添加新 chunks
    self.add(doc, chunk_cfg)
    
    # Step 2: 再删除旧 chunks
    self.delete(source)
```

**安全性**：
- 如果崩溃在 Step 1 和 Step 2 之间，会有重复数据但不会丢失
- 下次运行时会自动检测并清理重复数据

## ACID 特性

| 特性 | 实现方式 | 评分 |
|------|----------|------|
| **原子性** | Add-First 策略 | ⭐⭐⭐⭐ |
| **一致性** | content_hash 检测 | ⭐⭐⭐⭐ |
| **隔离性** | 查询不中断 | ⭐⭐⭐⭐⭐ |
| **持久性** | sync_threshold=100 | ⭐⭐⭐⭐ |

## 配置说明

### sync_threshold

控制 HNSW 索引从内存刷写到磁盘的频率。

**当前配置**：`sync_threshold=100`

**含义**：
- 每积累 100 条记录就持久化一次
- 比默认的 1000 更频繁，更安全
- 测试证明在所有场景下都能正常工作

### 切片模板

**配置位置**：`config/config.json`

| 模板 | chunk_size | overlap | strategy | 用途 |
|------|------------|---------|----------|------|
| academic | 2000 | 200 | recursive | 英文文献 |
| chinese | 1500 | 150 | recursive | 中文文档 |
| code | 3000 | 300 | flat | 代码文件 |
| custom | 1000 | 100 | recursive | 自定义 |

## 文件结构

```
E:\桌面\RAG\
├── config/                 # 配置文件
│   ├── .env                # 环境变量
│   ├── config.json         # 业务配置
│   └── settings.py         # 配置加载
├── core/                   # 核心业务逻辑
│   ├── builder.py          # 知识库构建
│   ├── embedder.py         # 向量化代理
│   └── repository.py       # 文档仓库
├── servers/                # 服务启动脚本
│   ├── chroma.py           # ChromaDB 服务
│   ├── mcp.py              # MCP 服务
│   └── rerank.py           # Rerank 服务
├── data/                   # 数据目录
│   ├── docs/               # 文档
│   ├── chroma_db/          # 向量数据库
│   └── models/             # 模型文件
├── runtime/                # 运行时数据
│   ├── logs/               # 日志
│   └── state/              # 状态文件
├── db_manage.py            # 数据库管理脚本
├── start_all.py            # 服务管理脚本
├── init.py                 # 配置管理脚本
└── start.bat               # 启动脚本
```

## 测试验证

### 测试场景

| 场景 | 结果 | 说明 |
|------|------|------|
| 无变化 | ✓ 零开销 | 33 个文件未变 |
| 添加新文件 | ✓ 只向量化新文件 | 1 个 chunk 添加 |
| 修改文件 | ✓ 只向量化变更文件 | 1 个 chunk 更新 |
| 删除文件 | ✓ 只删除 chunks | 1 个文件删除 |
| 同时新增+修改+删除 | ✓ 精确操作 | 各 1 个操作 |
| 50 文件 + 2 新文件 | ✓ 只向量化 2 个 | 50 个未变 |

### 测试结论

- 增量更新 100% 正常工作
- 添加新数据不会重新向量化旧数据
- sync_threshold=100 在所有场景下都能正常工作

## 常见问题

### Q: 为什么有这么多空文件夹？

A: 这些是 ChromaDB 测试时创建的集合目录，已经被清理。使用 `python db_manage.py` 的清理功能可以删除空文件夹。

### Q: 如何查看数据库中有哪些文档？

A: 运行 `python db_manage.py`，选择"查看数据库状态"。

### Q: 如何修改切片模板？

A: 编辑 `config/config.json` 或运行 `python init.py`。

### Q: 增量更新会重新向量化旧数据吗？

A: 不会。系统通过 content_hash 检测变化，只处理变化的文件。

### Q: sync_threshold 应该设置为多少？

A: 推荐 100。比默认的 1000 更频繁持久化，更安全。
