# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.14 — 知识库构建脚本 (Client-Server 模式)
读取 data/docs/ 中的文档 → 中文友好切片 → 调用 Embedding 服务向量化 → 存入 ChromaDB Server

支持：PDF / Word / TXT / 代码文件等 30+ 格式

用法:
  python -m core.builder              增量更新（默认，只处理变化文件）
  python -m core.builder --full        全量重建（影子集合，原子切换）
  python -m core.builder --full -c x   全量重建指定集合
"""
import os, sys, time, json, hashlib, argparse
from pathlib import Path
from typing import List, Optional
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import get_docs_dir, get_collection_name, get_chunk_config, get_chunk_templates
import chromadb
from pypdf import PdfReader
from docx import Document as DocxDocument

from core.embedder import get_lm_proxy

# 从配置文件读取
DOCS_DIR = get_docs_dir()
COLLECTION_NAME = get_collection_name()

POINTER_FILE = ROOT / "runtime" / "state" / "collection_pointer.json"


def read_pointer() -> dict:
    if POINTER_FILE.exists():
        with open(POINTER_FILE, "r", encoding="utf-8") as fp:
            return json.load(fp)
    return {}


def write_pointer(data: dict):
    POINTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POINTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_active_collection(config_key: str) -> str:
    """读取指针文件中配置的当前活跃集合名，没有则回退到默认"""
    p = read_pointer()
    return p.get(config_key, COLLECTION_NAME)


def set_active_collection(config_key: str, name: str):
    p = read_pointer()
    p[config_key] = name
    write_pointer(p)


def read_pdf(filepath: str) -> str:
    reader = PdfReader(filepath)
    texts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            texts.append(t)
    return "\n".join(texts)


def read_docx(filepath: str) -> str:
    doc = DocxDocument(filepath)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def read_txt(filepath: str) -> str:
    for enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return ""


def read_md(filepath: str) -> str:
    return read_txt(filepath)


SUPPORTED_EXT = {
    ".pdf": read_pdf, ".docx": read_docx, ".txt": read_txt, ".md": read_md,
    ".py": read_txt, ".js": read_txt, ".ts": read_txt, ".java": read_txt,
    ".c": read_txt, ".cpp": read_txt, ".go": read_txt, ".rs": read_txt,
    ".r": read_txt, ".R": read_txt, ".sh": read_txt, ".ps1": read_txt,
    ".swift": read_txt, ".kt": read_txt, ".rb": read_txt, ".lua": read_txt,
    ".sql": read_txt, ".json": read_txt, ".yaml": read_txt, ".yml": read_txt,
    ".csv": read_txt, ".xml": read_txt, ".toml": read_txt, ".ini": read_txt,
    ".cfg": read_txt, ".conf": read_txt, ".log": read_txt, ".html": read_txt,
    ".css": read_txt,
}


def load_all_documents(docs_dir: Path) -> List[dict]:
    documents = []
    seen = set()
    for ext, reader_fn in SUPPORTED_EXT.items():
        for f in docs_dir.glob(f"**/*{ext}"):
            if not f.is_file():
                continue
            key = str(f.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                text = reader_fn(str(f))
                if text.strip():
                    rel = f.relative_to(docs_dir)
                    doc_name = os.path.splitext(f.name)[0]
                    text = f"[文件名: {doc_name}]\n{text}"
                    documents.append({"path": str(f), "text": text})
                    print(f"  [OK] {rel} ({len(text)} 字)")
                else:
                    print(f"  [跳过] {f.name} (无文字内容)")
            except Exception as e:
                print(f"  [失败] {f.name}: {e}")
    print(f"\n共加载 {len(documents)} 份文档")
    return documents


def split_text(text: str, cfg: dict) -> List[str]:
    """按模板配置切片。strategy='recursive' 时保留段落结构"""
    chunk_size = cfg["chunk_size"]
    overlap = cfg["overlap"]
    strategy = cfg.get("strategy", "flat")
    separators = cfg["separators"]

    if strategy == "recursive":
        return _split_recursive(text, chunk_size, overlap, separators)
    else:
        return _split_flat(text, chunk_size, overlap, separators)


def _split_recursive(text: str, chunk_size: int, overlap: int, separators: list) -> List[str]:
    """递归分层切片：段落 → 句子 → 字符。保留学术文献的段落完整性"""
    # 1. 从最粗分隔符开始：段落
    para_seps = [s for s in separators if s in ("\n\n", "\r\n\r\n", "\r\n")]
    if not para_seps:
        para_seps = ["\n\n"]

    paragraphs = [text]
    for s in para_seps:
        expanded = []
        for p in paragraphs:
            expanded.extend(p.split(s))
        paragraphs = expanded
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # 2. 逐段落处理
    # 句子级分隔符（从粗到细）
    sent_seps = [s for s in separators
                 if s not in ("\n\n", "\r\n\r\n", "\r\n", " ", "") and s]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(para) <= chunk_size:
            if current:
                _add_segment(current, para, chunk_size, overlap, chunks)
            current = _update_current(current, para, chunk_size, overlap)
            if para == paragraphs[-1]:
                continue
            continue

        # 段落太长 → 先按句切
        sentences = [para]
        for raw_s in sent_seps:
            s = "\n" if raw_s == "\n" else raw_s
            if s == "\n" and "\n\n" in separators:
                continue
            expanded = []
            for seg in sentences:
                expanded.extend(seg.split(s))
            sentences = expanded
        sentences = [seg.strip() + _pick_suffix(para, seg) for seg in sentences if seg.strip()]
        sentences = [seg.rstrip() for seg in sentences if seg.strip()]

        # 对每个句子按段内方式拼接
        for sent in sentences:
            if len(sent) > chunk_size:
                # 单句过长，按空格硬切
                _hard_split_long(sent, chunk_size, overlap, chunks)
                current = ""
                continue
            _add_segment(current, sent, chunk_size, overlap, chunks)
            current = _update_current(current, sent, chunk_size, overlap)

    if current.strip():
        chunks.append(current.strip())

    return _final_pass(chunks, chunk_size)


def _split_flat(text: str, chunk_size: int, overlap: int, separators: list) -> List[str]:
    """扁平切片（兼容旧逻辑），不保留段落结构"""
    parts = [text]
    for s in separators:
        if not s:
            continue
        new_parts = []
        for p in parts:
            new_parts.extend(p.split(s))
        parts = new_parts
    segments = [seg.strip() for seg in parts if seg.strip()]

    chunks = []
    current = ""
    for seg in segments:
        if current and len(current) + len(seg) > chunk_size:
            chunks.append(current.strip())
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + " " + seg
            else:
                current = seg
        else:
            current = current + " " + seg if current else seg
    if current.strip():
        chunks.append(current.strip())
    return _final_pass(chunks, chunk_size)


def _add_segment(current: str, seg: str, chunk_size: int, overlap: int, chunks: list):
    """将当前段落添加到 chunk，超出则切分"""
    if not current:
        return
    if len(current) + len(seg) > chunk_size:
        chunks.append(current.strip())


def _update_current(current: str, seg: str, chunk_size: int, overlap: int) -> str:
    """计算下一段落的 current 状态"""
    if not current:
        return seg
    if len(current) + len(seg) > chunk_size:
        if overlap > 0 and len(current) > overlap:
            return current[-overlap:] + " " + seg
        return seg
    return current + " " + seg


def _pick_suffix(text: str, seg: str) -> str:
    """恢复按句切时丢失的标点"""
    idx = text.find(seg)
    if idx < 0:
        return ""
    end = idx + len(seg)
    if end < len(text) and text[end] in ".。!！?？;；":
        return text[end]
    return ""


def _hard_split_long(text: str, chunk_size: int, overlap: int, chunks: list):
    """对超长文本硬切，优先在空格处断"""
    i = 0
    while i < len(text):
        end = min(i + chunk_size, len(text))
        if end >= len(text):
            chunks.append(text[i:].strip())
            break
        # 尝试在空格处断
        cut = text.rfind(" ", i, end)
        if cut > i + chunk_size // 2:
            chunks.append(text[i:cut].strip())
            i = max(i, cut - overlap)
        else:
            chunks.append(text[i:end].strip())
            i = max(i, end - overlap)
        if i >= len(text):
            break


def _final_pass(chunks: list, chunk_size: int) -> List[str]:
    """对超长子串兜底硬切"""
    result = []
    for ch in chunks:
        if len(ch) <= chunk_size * 1.5:
            result.append(ch)
            continue
        i = 0
        while i < len(ch):
            end = min(i + chunk_size, len(ch))
            result.append(ch[i:end].strip())
            i += chunk_size
    return result


def md5_short(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def clean_old_shadows(chroma_client, collection_key):
    """清理旧版本化影子集合，不碰当前活跃集合"""
    active = get_active_collection(collection_key)
    try:
        collections = chroma_client.list_collections()
        for col in collections:
            if col.name.startswith(f"{collection_key}_v") and col.name != active:
                chroma_client.delete_collection(col.name)
                print(f"  清理旧影子: {col.name}")
    except Exception:
        pass


def chunk_documents(documents: List[dict], chunk_cfg: dict) -> List[dict]:
    """对所有文档切片，生成带 content_hash 的 chunk 列表"""
    all_chunks = []
    for doc in documents:
        doc_hash = content_hash(doc["text"])
        chunks = split_text(doc["text"], chunk_cfg)
        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "id": f"{md5_short(doc['path'])}-{i}",
                "text": chunk,
                "source": doc["path"],
                "chunk_index": i,
                "content_hash": doc_hash,
            })
    return all_chunks





def build_full(collection_key: str, chroma_client, documents, emb_proxy, chunk_cfg: dict):
    """
    全量重建 — 删除旧集合，重新创建并添加所有文档
    """
    collection_name = get_active_collection(collection_key)

    # Step 1: 删除旧集合
    try:
        chroma_client.delete_collection(collection_name)
        print(f"  已删除旧集合: {collection_name}")
    except Exception:
        pass

    # Step 2: 创建新集合
    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
    )
    from core.repository import DocumentRepository
    repo = DocumentRepository(collection, emb_proxy)

    print(f"  新集合: {collection.name}")

    # Step 3: 添加所有文档
    stats = {"added": 0}
    for i, doc in enumerate(documents, 1):
        count = repo.add(doc, chunk_cfg, source_type="local_file")
        stats["added"] += count
        rel = Path(doc["path"]).name
        print(f"  [{i}/{len(documents)}] {rel} ({count} chunks)")

    print(f"\n  全量重建完成! 共添加 {stats['added']} chunks")
    return repo.count()


def build_incremental(collection_key: str, chroma_client, documents, emb_proxy, chunk_cfg: dict):
    """
    增量更新 — 通过 Repository 实现文档级 CRUD
    1. 新文件 → add
    2. 变更文件 → update (Add-First 策略)
    3. 未变文件 → 跳过（零开销）
    4. 已删文件 → delete
    """
    collection = get_or_create_collection(chroma_client, collection_key)
    from core.repository import DocumentRepository
    repo = DocumentRepository(collection, emb_proxy)

    print(f"  集合: {collection.name} ({repo.count()} 条记录)")

    # 执行同步
    stats = repo.sync(documents, chunk_cfg)

    # 输出结果
    total_ops = stats["added"] + stats["updated"] + stats["deleted_vectors"]
    if total_ops == 0:
        print(f"\n  无变化，跳过建库（{stats['unchanged']} 个文件未变）")
        return repo.count()

    print(f"\n  新增: {stats['added']} chunks  更新: {stats['updated']} chunks"
          f"  未变: {stats['unchanged']}  删除: {stats['deleted_vectors']} 个文件")
    print(f"  更新完成! 集合当前: {repo.count()} 条记录")
    return repo.count()


def get_or_create_collection(chroma_client, collection_key: str):
    """获取或创建集合"""
    collection_name = get_active_collection(collection_key)
    try:
        return chroma_client.get_collection(name=collection_name)
    except Exception:
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
        )
        set_active_collection(collection_key, collection_name)
        return collection


def build_knowledge_base(collection_name: str = None, full_rebuild: bool = False, template_name: str = None):
    if collection_name is None:
        collection_name = COLLECTION_NAME

    chunk_cfg = get_chunk_config(template_name)

    docs_dir = ROOT / DOCS_DIR

    mode = "全量重建" if full_rebuild else "增量更新"
    
    # 读取 Embedding 配置
    embedding_mode = os.getenv("EMBEDDING_MODE", "cloud").lower()
    if embedding_mode == "local":
        embedding_url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
        embedding_model = os.getenv("EMBEDDING_LOCAL_MODEL", "text-embedding-qwen3-embedding-4b")
        embedding_dim = os.getenv("EMBEDDING_LOCAL_DIM", "2560")
    else:
        embedding_url = os.getenv("EMBEDDING_CLOUD_URL", "https://api.siliconflow.cn/v1/embeddings")
        embedding_model = os.getenv("EMBEDDING_CLOUD_MODEL", "BAAI/bge-m3")
        embedding_dim = os.getenv("EMBEDDING_CLOUD_DIM", "1024")
    
    print("=" * 60)
    print(f"  Ezy-RAG V0.0.17 — 知识库构建 ({mode})")
    print("=" * 60)
    print(f"  Embedding: {'本地' if embedding_mode == 'local' else '云端'} ({embedding_model}, {embedding_dim}维)")
    print(f"  切块模板: {chunk_cfg['name']} ({chunk_cfg['strategy']}, {chunk_cfg['chunk_size']}字)")
    print("=" * 60)

    if not docs_dir.exists():
        print(f"\n创建文档文件夹: {docs_dir}")
        docs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n文档目录: {docs_dir}")
    print(f"ChromaDB Server: {os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}")
    print(f"集合标识: {collection_name}")

    # Step 1: 清理 + 连接
    print("\n[1/5] 连接 ChromaDB Server...")
    chroma_client = chromadb.HttpClient(
        host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
    )
    try:
        heartbeat = chroma_client.heartbeat()
        print(f"  已连接 (心跳: {heartbeat} ns)")
    except Exception as e:
        print(f"  无法连接 ChromaDB Server: {e}")
        print(f"  请先启动: python -m servers.chroma")
        return
    clean_old_shadows(chroma_client, collection_name)

    # Step 2: 获取 Embedding 代理
    print("\n[2/5] 初始化 Embedding 代理...")
    try:
        emb_proxy = get_lm_proxy()
        print(f"  代理就绪")
    except Exception as e:
        print(f"  无法连接 Embedding 服务: {e}")
        return

    # Step 3: 加载文档
    print("\n[3/5] 加载文档...")
    documents = load_all_documents(docs_dir)
    if not documents:
        print("没有找到任何文档，请将文件放入 data/docs/ 文件夹后重试。")
        return

    # Step 4: 建库
    print(f"\n[4/5] 向量化并存入 ChromaDB ({mode})...")
    if full_rebuild:
        count = build_full(collection_name, chroma_client, documents, emb_proxy, chunk_cfg)
    else:
        count = build_incremental(collection_name, chroma_client, documents, emb_proxy, chunk_cfg)

    active = get_active_collection(collection_name)
    print(f"\n" + "=" * 60)
    print(f"  建库完成！活跃集合: {active}: {count} 个向量，{len(documents)} 份文档")
    print(f"  ChromaDB Server: {os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}")
    print(f"  下一步: 启动 MCP 服务器 → python -m servers.mcp")
    print("=" * 60)


if __name__ == "__main__":
    chunk_templates = get_chunk_templates()
    parser = argparse.ArgumentParser(description="Ezy-RAG 知识库构建工具")
    parser.add_argument("--collection", "-c", type=str, default=None,
                        help=f"集合标识 (默认: {COLLECTION_NAME})")
    parser.add_argument("--full", action="store_true",
                        help="全量重建（影子集合 + 原子切换）")
    parser.add_argument("--template", "-t", type=str, default=None,
                        help=f"切块模板 (可选: {', '.join(chunk_templates.keys())})")
    args = parser.parse_args()
    build_knowledge_base(collection_name=args.collection, full_rebuild=args.full,
                         template_name=args.template)
