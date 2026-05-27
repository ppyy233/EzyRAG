# ============================================================
# QwenKB V1.0 — 集中配置文件
# 
# ⚠  本地环境参数（IP、端口、模型名、密钥等）通过 .env 注入
#    .env 已加入 .gitignore，复制 .env.example 创建并填入你的值
# ============================================================
import os
from dotenv import load_dotenv

load_dotenv()

# ====== LM Studio 本地嵌入服务（来自 .env） ======
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "http://127.0.0.1:5000/v1/embeddings")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL  = os.getenv("EMBEDDING_MODEL", "text-embedding-qwen3-embedding-4b")
EMBEDDING_DIM    = int(os.getenv("EMBEDDING_DIM", "2560"))

# ====== DeepSeek 对话 API（opencode 后端用） ======
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# ====== 文档和存储路径 ======
DOCS_DIR   = "data/docs"
CHROMA_DIR = "data/chroma_db"
CHROMA_SERVER_HOST = os.getenv("CHROMA_SERVER_HOST", "127.0.0.1")
CHROMA_SERVER_PORT = int(os.getenv("CHROMA_SERVER_PORT", "9898"))
COLLECTION_NAME    = "default_collection"

# ====== 文档切片模板 ======
# 通过 .env CHUNK_TEMPLATE 或命令行 --template 选择
# strategy: "recursive"（推荐，保留段落结构） / "flat"（兼容旧逻辑）
CHUNK_TEMPLATES = {
    "academic": {
        "name": "英文文献专用",
        "chunk_size": 2000,
        "overlap": 200,
        "strategy": "recursive",
        "separators": ["\n\n", "\n", "\r\n", "。", ". ", "！", "?", "？", "!", "；", ";", "，", ",", "、", " ", ""],
    },
    "chinese": {
        "name": "中文专用",
        "chunk_size": 1500,
        "overlap": 150,
        "strategy": "recursive",
        "separators": ["\n\n", "\n", "。", "！", "？", "；", "，", "、", " ", ""],
    },
    "code": {
        "name": "数据分析/代码专用",
        "chunk_size": 3000,
        "overlap": 300,
        "strategy": "flat",
        "separators": ["\n\n\n", "\n\n", "\n", ". ", " ", ""],
    },
}

CHUNK_TEMPLATE = os.getenv("CHUNK_TEMPLATE", "academic")


def get_chunk_config(template_name: str = None) -> dict:
    """返回当前激活的切块模板配置"""
    name = template_name or CHUNK_TEMPLATE
    if name not in CHUNK_TEMPLATES:
        name = "academic"
    return CHUNK_TEMPLATES[name]


# ====== 检索参数 ======
RETRIEVAL_K          = 5
RETRIEVAL_FETCH_K    = 15
RETRIEVAL_LAMBDA     = 0.7
RETRIEVAL_THRESHOLD  = 0.3

# ====== 重排（Rerank）参数（来自 .env，可选） ======
# 不启用重排: RERANK_ENABLED=false
# 本地 BGE:    RERANK_API_URL=http://127.0.0.1:5001  RERANK_API_KEY=
# 云端 Cohere: RERANK_API_URL=https://api.cohere.ai/v1  RERANK_API_KEY=xxx
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "false").lower() == "true"
RERANK_API_URL = os.getenv("RERANK_API_URL", "http://127.0.0.1:5001")
RERANK_API_KEY = os.getenv("RERANK_API_KEY", "")

# ====== MCP 服务器参数（来自 .env） ======
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "9766"))

# ====== LLM 问答提示词 ======
# 知识库优先 + 不禁止外部知识 + 标注来源
ANSWER_PROMPT = """你是一个专业的问答助手。回答用户问题时请遵循以下规则：

1. 优先参考提供的【知识库资料】来回答问题。
2. 如果知识库中有相关答案，用它回答，并注明来源。
3. 如果知识库信息不足以回答，可以结合你的通用知识补充，但要明确区分：
   - 【来自知识库：xxx】
   - 【来自通用知识：xxx】
4. 如果知识库信息与通用知识矛盾，指出来，让用户自行判断。
5. 保持回答简洁、准确、客观。

【知识库资料】
{context}

【用户问题】
{question}

【回答】"""
