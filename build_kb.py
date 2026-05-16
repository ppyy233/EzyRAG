# -*- coding: utf-8 -*-
"""
QwenKB V1.2 — 知识库构建脚本 (Client-Server 模式)
读取 docs/ 中的文档 → 中文友好切片 → 调用 LM Studio 向量化 → 存入 ChromaDB Server

支持：PDF / Word / TXT / 代码文件等 30+ 格式

用法:
  python build_kb.py              增量更新（默认，只处理变化文件）
  python build_kb.py --full        全量重建（影子集合，原子切换）
  python build_kb.py --full -c x   全量重建指定集合
"""
import os
import sys
import shutil
import time
import json
import hashlib
import argparse
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from openai import OpenAI
import chromadb
from pypdf import PdfReader
from docx import Document as DocxDocument

import config

POINTER_FILE = "collection_pointer.json"


def get_base_dir() -> Path:
    return Path(__file__).resolve().parent


def get_pointer_file() -> Path:
    return get_base_dir() / POINTER_FILE


def read_pointer() -> dict:
    f = get_pointer_file()
    if f.exists():
        with open(f, "r", encoding="utf-8") as fp:
            return json.load(fp)
    return {}


def write_pointer(data: dict):
    with open(get_pointer_file(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_active_collection(config_key: str) -> str:
    """读取指针文件中配置的当前活跃集合名，没有则回退到 config 默认"""
    p = read_pointer()
    return p.get(config_key, config.COLLECTION_NAME)


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
                    documents.append({"path": str(f), "text": text})
                    print(f"  [OK] {rel} ({len(text)} 字)")
                else:
                    print(f"  [跳过] {f.name} (无文字内容)")
            except Exception as e:
                print(f"  [失败] {f.name}: {e}")
    print(f"\n共加载 {len(documents)} 份文档")
    return documents


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    sep = config.CHINESE_SEPARATORS
    parts = [text]
    for s in sep:
        if not s:
            continue
        new_parts = []
        for p in parts:
            new_parts.extend(p.split(s))
        parts = new_parts
    segments = [seg.strip() for seg in parts if seg.strip()]
    chunks = []
    current_chunk = ""
    for seg in segments:
        if current_chunk and len(current_chunk) + len(seg) > chunk_size:
            chunks.append(current_chunk.strip())
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + seg
            else:
                current_chunk = seg
        else:
            current_chunk = current_chunk + " " + seg if current_chunk else seg
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    for i, ch in enumerate(chunks):
        if len(ch) > chunk_size * 1.5:
            sub_chunks = []
            for j in range(0, len(ch), chunk_size):
                sub_chunks.append(ch[j:j + chunk_size])
            chunks[i:i + 1] = sub_chunks
    return chunks


def md5_short(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class EmbeddingClient:
    """LM Studio 嵌入客户端"""

    def __init__(self, openai_client: OpenAI, model: str, dim: int):
        self._client = openai_client
        self._model = model
        self._dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        batch_size = 20
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = self._client.embeddings.create(model=self._model, input=batch)
            for item in resp.data:
                vec = item.embedding
                if len(vec) != self._dim:
                    raise ValueError(
                        f"LM Studio 返回向量维度 {len(vec)}，期望 {self._dim}。"
                        f"请检查 {self._model} 模型配置"
                    )
                embeddings.append(vec)
        return embeddings


def clean_orphan_dirs(chroma_dir: Path):
    """清理 chroma_db/ 下所有孤立 UUID 目录"""
    if not chroma_dir.exists():
        return
    for d in chroma_dir.iterdir():
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            print(f"  清理孤立目录: {d.name}")


def chunk_documents(documents: List[dict]) -> List[dict]:
    all_chunks = []
    for doc in documents:
        doc_hash = content_hash(doc["text"])
        chunks = split_text(doc["text"], config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "id": f"{md5_short(doc['path'])}-{i}",
                "text": chunk,
                "source": doc["path"],
                "chunk_index": i,
                "content_hash": doc_hash,
            })
    return all_chunks


def batch_add(collection, chunks: List[dict], emb_client: EmbeddingClient,
              add_batch_size: int = 50, total: int = None):
    """批量向量化 + 入库"""
    if total is None:
        total = len(chunks)
    for i in range(0, len(chunks), add_batch_size):
        batch = chunks[i:i + add_batch_size]
        ids = [c["id"] for c in batch]
        texts = [c["text"] for c in batch]
        metas = [{"source": c["source"], "chunk_index": c["chunk_index"],
                  "content_hash": c["content_hash"]} for c in batch]
        embeddings = emb_client.embed(texts)
        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)
        done = i + len(batch)
        pct = min(100, int(done / total * 100))
        print(f"  进度: {done}/{total} ({pct}%)")
        if i + add_batch_size < len(chunks):
            time.sleep(0.1)


def build_full(collection_key: str, chroma_client, documents, emb_client):
    """
    全量重建 — 影子集合模式
    1. 建影子集合 {name}_{timestamp}
    2. 全部 add
    3. 更新指针 → 查询立即可用新集合
    4. 删旧集合（有空再清理）
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shadow_name = f"{collection_key}_v{timestamp}"

    print(f"\n  影子集合: {shadow_name}")

    try:
        chroma_client.delete_collection(shadow_name)
    except Exception:
        pass

    shadow = chroma_client.create_collection(
        name=shadow_name,
        metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100000},
    )

    all_chunks = chunk_documents(documents)
    print(f"  共切出 {len(all_chunks)} 个文本块")

    try:
        batch_add(shadow, all_chunks, emb_client, total=len(all_chunks))
    except Exception:
        print("  建库失败，清理影子集合")
        chroma_client.delete_collection(shadow_name)
        raise

    count = shadow.count()
    print(f"\n  影子集合完成: {count} 条")

    # 原子切换：更新指针
    old = get_active_collection(collection_key)
    set_active_collection(collection_key, shadow_name)
    print(f"  已切换: {old} → {shadow_name}")

    # 异步清理旧集合
    try:
        if old and old != shadow_name:
            chroma_client.delete_collection(old)
            print(f"  已清理旧集合: {old}")
    except Exception as e:
        print(f"  清理旧集合失败 (可手动删除): {e}")

    return count


def build_incremental(collection_key: str, chroma_client, documents, emb_client):
    """
    增量更新 — 影子集合模式
    1. 读旧集合全部数据（含向量）
    2. 分类文件：未变 / 新增+变更 / 已删
    3. 建影子集合：未变文件直接 copy 旧向量
    4. embed + add 新/变文件
    5. 指针原子切换 → 删旧集合
    """
    current = get_active_collection(collection_key)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shadow_name = f"{collection_key}_v{timestamp}"

    print(f"  影子集合: {shadow_name}")

    # Step 1: 获取旧集合元数据
    try:
        active = chroma_client.get_collection(name=current)
    except Exception:
        print("  旧集合不存在，按全量重建")
        return build_full(collection_key, chroma_client, documents, emb_client)

    # 先只取 metadata（轻量），做 hash 对比
    try:
        meta_result = active.get(include=["metadatas"])
        existing_metas = meta_result["metadatas"] if meta_result and meta_result["ids"] else []
        existing_ids = meta_result["ids"] if meta_result and meta_result["ids"] else []
    except Exception:
        existing_metas = []
        existing_ids = []

    # Step 2: 分类文件
    stored_hashes = {}
    for meta in existing_metas:
        src = meta.get("source", "")
        stored_hashes[src] = meta.get("content_hash", "")

    new_docs = []
    changed_docs = []
    unchanged_count = 0
    current_sources = {d["path"] for d in documents}

    for doc in documents:
        h = content_hash(doc["text"])
        stored_h = stored_hashes.get(doc["path"], "")
        if doc["path"] not in stored_hashes:
            new_docs.append(doc)
        elif not stored_h:
            # 旧数据无 content_hash，按 chunk 数比较
            old_chunk_count = sum(1 for m in existing_metas
                                  if m.get("source") == doc["path"])
            new_chunks = split_text(doc["text"], config.CHUNK_SIZE, config.CHUNK_OVERLAP)
            if len(new_chunks) != old_chunk_count:
                changed_docs.append(doc)
            else:
                unchanged_count += 1
        elif stored_h != h:
            changed_docs.append(doc)
        else:
            unchanged_count += 1

    all_changed = new_docs + changed_docs
    changed_sources = {d["path"] for d in all_changed}
    deleted_sources = set(stored_hashes.keys()) - current_sources

    print(f"  新文件: {len(new_docs)}  变更: {len(changed_docs)}"
          f"  未变: {unchanged_count}  已删: {len(deleted_sources)}")

    # Step 3: 建影子集合
    try:
        chroma_client.delete_collection(shadow_name)
    except Exception:
        pass

    shadow = chroma_client.create_collection(
        name=shadow_name,
        metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100000},
    )

    # Step 4: 无变化 → 跳过
    if not all_changed and not deleted_sources:
        print(f"\n  无变化，跳过建库（{unchanged_count} 个文件未变）")
        return active.count()

    # 有变化 → 全量影子集合（1.5.9 get 带 embedding 不可靠，不复制向量）
    print(f"  处理 {len(all_changed)} 个变化文件 + {unchanged_count} 个未变文件...")
    return build_full(collection_key, chroma_client, documents, emb_client)


def build_knowledge_base(collection_name: str = None, full_rebuild: bool = False):
    if collection_name is None:
        collection_name = config.COLLECTION_NAME

    base_dir = get_base_dir()
    docs_dir = base_dir / config.DOCS_DIR
    chroma_dir = base_dir / config.CHROMA_DIR

    mode = "全量重建" if full_rebuild else "增量更新"
    print("=" * 60)
    print(f"  QwenKB V1.2 — 知识库构建 ({mode})")
    print("=" * 60)

    if not docs_dir.exists():
        print(f"\n创建文档文件夹: {docs_dir}")
        docs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n文档目录: {docs_dir}")
    print(f"ChromaDB Server: {config.CHROMA_SERVER_HOST}:{config.CHROMA_SERVER_PORT}")
    print(f"集合标识: {collection_name}")

    # Step 1: 清理 + 连接
    print("\n[1/5] 连接 ChromaDB Server...")
    clean_orphan_dirs(chroma_dir)
    chroma_client = chromadb.HttpClient(
        host=config.CHROMA_SERVER_HOST,
        port=config.CHROMA_SERVER_PORT,
    )
    try:
        heartbeat = chroma_client.heartbeat()
        print(f"  已连接 (心跳: {heartbeat} ns)")
    except Exception as e:
        print(f"  无法连接 ChromaDB Server: {e}")
        print(f"  请先启动: start_chroma_server.bat")
        return

    # Step 2: 检查 LM Studio
    print("\n[2/5] 检查 LM Studio...")
    oai_client = OpenAI(
        api_key=config.EMBEDDING_API_KEY,
        base_url=config.EMBEDDING_API_URL.rsplit("/v1/", 1)[0] + "/v1/",
    )
    try:
        models_resp = oai_client.models.list()
        print(f"  已连接 (模型数: {len(models_resp.data)})")
    except Exception as e:
        print(f"  无法连接 LM Studio: {e}")
        print(f"  请启动 LM Studio 并加载 {config.EMBEDDING_MODEL} 模型后重试")
        return

    emb_client = EmbeddingClient(oai_client, config.EMBEDDING_MODEL, config.EMBEDDING_DIM)

    # Step 3: 加载文档
    print("\n[3/5] 加载文档...")
    documents = load_all_documents(docs_dir)
    if not documents:
        print("没有找到任何文档，请将文件放入 docs/ 文件夹后重试。")
        return

    # Step 4: 建库
    print(f"\n[4/5] 向量化并存入 ChromaDB ({mode})...")
    if full_rebuild:
        count = build_full(collection_name, chroma_client, documents, emb_client)
    else:
        count = build_incremental(collection_name, chroma_client, documents, emb_client)

    active = get_active_collection(collection_name)
    print(f"\n" + "=" * 60)
    print(f"  建库完成！活跃集合: {active}: {count} 个向量，{len(documents)} 份文档")
    print(f"  ChromaDB Server: {config.CHROMA_SERVER_HOST}:{config.CHROMA_SERVER_PORT}")
    print(f"  下一步: 启动 MCP 服务器 → python mcp_server.py")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QwenKB 知识库构建工具")
    parser.add_argument("--collection", "-c", type=str, default=None,
                        help=f"集合标识 (默认: {config.COLLECTION_NAME})")
    parser.add_argument("--full", action="store_true",
                        help="全量重建（影子集合 + 原子切换）")
    args = parser.parse_args()
    build_knowledge_base(collection_name=args.collection, full_rebuild=args.full)
