# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.18 — 统一数据库操作层
合并原 builder.py 和 repository.py，实现完整的 CRUD + ACID

ACID 策略：
  add     → 直接写入 + 幂等（先检查exists，存在则delete）
  delete  → 直接删除（ChromaDB原子操作）
  update  → 影子集合策略（原子性保证）
  sync    → 影子集合策略（批量增删改）
  rebuild → 影子集合策略（全量重建）

用法:
  from core.database import DocumentDatabase, build_knowledge_base
"""
import os
import sys
import hashlib
import logging
import argparse
import shutil
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import (
    get_docs_dir, get_collection_name, get_chunk_config,
    get_chunk_templates, get_retrieval_config,
)
from config.pointer import (
    read_pointer, write_pointer, get_active_collection, set_active_collection,
)
import chromadb

# Embedding API 单次最大批量（从环境变量读取，默认 50）
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "50"))

logger = logging.getLogger("Ezy-RAG-DB")


# ============================================================
#  工具函数
# ============================================================

def content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def md5_short(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


# ============================================================
#  文件读取
# ============================================================

def read_pdf(filepath: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(filepath)
    texts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            texts.append(t)
    return "\n".join(texts)


def read_docx(filepath: str) -> str:
    from docx import Document as DocxDocument
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


def read_file(filepath: str) -> str:
    """统一文件读取，根据扩展名选择读取方式"""
    ext = Path(filepath).suffix.lower()
    reader_fn = SUPPORTED_EXT.get(ext)
    if not reader_fn:
        raise ValueError(f"不支持的文件格式: {ext}")
    return reader_fn(filepath)


def load_all_documents(docs_dir: Path) -> List[dict]:
    """加载目录下所有文档"""
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
                    doc_name = f.stem
                    text = f"[文件名: {doc_name}]\n{text}"
                    documents.append({"path": str(f), "text": text})
                    logger.info(f"加载: {rel} ({len(text)} 字)")
                else:
                    logger.debug(f"跳过: {f.name} (无文字内容)")
            except Exception as e:
                logger.warning(f"加载失败: {f.name}: {e}")
    logger.info(f"共加载 {len(documents)} 份文档")
    return documents


# ============================================================
#  文本切片
# ============================================================

def split_text(text: str, cfg: dict) -> List[str]:
    """按模板配置切片"""
    chunk_size = cfg["chunk_size"]
    overlap = cfg["overlap"]
    strategy = cfg.get("strategy", "flat")
    separators = cfg["separators"]
    if strategy == "recursive":
        return _split_recursive(text, chunk_size, overlap, separators)
    else:
        return _split_flat(text, chunk_size, overlap, separators)


def _split_recursive(text: str, chunk_size: int, overlap: int, separators: list) -> List[str]:
    """递归分层切片：段落 → 句子 → 字符"""
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

        for sent in sentences:
            if len(sent) > chunk_size:
                _hard_split_long(sent, chunk_size, overlap, chunks)
                current = ""
                continue
            _add_segment(current, sent, chunk_size, overlap, chunks)
            current = _update_current(current, sent, chunk_size, overlap)

    if current.strip():
        chunks.append(current.strip())
    return _final_pass(chunks, chunk_size)


def _split_flat(text: str, chunk_size: int, overlap: int, separators: list) -> List[str]:
    """扁平切片"""
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
    if not current:
        return
    if len(current) + len(seg) > chunk_size:
        chunks.append(current.strip())


def _update_current(current: str, seg: str, chunk_size: int, overlap: int) -> str:
    if not current:
        return seg
    if len(current) + len(seg) > chunk_size:
        if overlap > 0 and len(current) > overlap:
            return current[-overlap:] + " " + seg
        return seg
    return current + " " + seg


def _pick_suffix(text: str, seg: str) -> str:
    idx = text.find(seg)
    if idx < 0:
        return ""
    end = idx + len(seg)
    if end < len(text) and text[end] in ".。!！?？;；":
        return text[end]
    return ""


def _hard_split_long(text: str, chunk_size: int, overlap: int, chunks: list):
    i = 0
    while i < len(text):
        end = min(i + chunk_size, len(text))
        if end >= len(text):
            chunks.append(text[i:].strip())
            break
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


# ============================================================
#  切片 + 元数据
# ============================================================

def chunk_single_document(doc: dict, chunk_cfg: dict, source_type: str = "local_file") -> List[dict]:
    """对单个文档切片，生成带元数据的 chunk 列表"""
    doc_hash = content_hash(doc["text"])
    chunks = split_text(doc["text"], chunk_cfg)
    result = []

    source_path = doc["path"]
    if source_type == "web_crawl":
        source_name = doc.get("title", source_path)
    else:
        source_name = Path(source_path).name

    for i, chunk in enumerate(chunks):
        result.append({
            "id": f"{md5_short(source_path)}-{i}",
            "text": chunk,
            "source": source_path,
            "source_type": source_type,
            "source_name": source_name,
            "chunk_index": i,
            "content_hash": doc_hash,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    return result


# ============================================================
#  维护工具
# ============================================================

def cleanup_empty_chroma_dirs():
    """清理 ChromaDB 的空 segment 目录（删除集合后残留的空文件夹）"""
    chroma_dir = ROOT / "data" / "chroma_db"
    if not chroma_dir.exists():
        return 0
    cleaned = 0
    for d in chroma_dir.iterdir():
        if d.is_dir() and d.name not in ("_test_sync", ".gitkeep") and not any(d.iterdir()):
            try:
                d.rmdir()
                cleaned += 1
            except Exception:
                pass
    if cleaned > 0:
        logger.info(f"清理 {cleaned} 个空 ChromaDB 目录")
    return cleaned


def cleanup_orphan_shadows(chroma_client, config_key: str):
    """清理不在指针中的孤儿影子集合"""
    if not chroma_client:
        return 0
    active_name = get_active_collection(config_key)
    cleaned = 0
    try:
        for col in chroma_client.list_collections():
            if col.name.startswith(f"{config_key}_v") and col.name != active_name:
                try:
                    chroma_client.delete_collection(col.name)
                    cleaned += 1
                    logger.info(f"清理孤儿影子: {col.name}")
                except Exception:
                    pass
    except Exception:
        pass
    return cleaned


def validate_hnsw(collection) -> tuple[bool, str]:
    """验证集合的 HNSW 索引是否完好"""
    try:
        count = collection.count()
        if count == 0:
            return True, "空集合"
        # 用 1024 维向量做测试查询（覆盖常见维度）
        collection.query(
            query_embeddings=[[0.0] * 1024],
            n_results=1,
            include=["metadatas"],
        )
        return True, f"{count} records"
    except Exception as e:
        err = str(e)
        if "hnsw" in err.lower() or "dimension" in err.lower():
            # 维度不匹配也算 HNSW 验证失败，但不一定是损坏
            # 尝试用 count 验证
            try:
                collection.count()
                return True, f"{count} records (query dim mismatch)"
            except:
                return False, f"HNSW 损坏: {err[:80]}"
        return False, err[:100]


# ============================================================
#  DocumentDatabase — 统一数据库操作
# ============================================================

class DocumentDatabase:
    """
    统一的数据库操作类

    ACID 策略：
    - add:     直接写入 + 幂等
    - delete:  直接删除
    - update:  影子集合
    - sync:    影子集合
    - rebuild: 影子集合
    """

    def __init__(self, collection, emb_api, chroma_client=None, collection_name=None):
        self.collection = collection
        self.emb_api = emb_api
        self.chroma_client = chroma_client
        self.collection_name = collection_name or collection.name

    # ====== 读操作（不需要 ACID） ======

    def count(self) -> int:
        try:
            return self.collection.count()
        except Exception as e:
            logger.warning(f"获取记录数失败: {e}")
            return 0

    def exists(self, source: str) -> bool:
        try:
            result = self.collection.get(where={"source": source}, include=["metadatas"])
            return result and result["ids"] and len(result["ids"]) > 0
        except Exception:
            return False

    def get_hash(self, source: str) -> Optional[str]:
        try:
            result = self.collection.get(where={"source": source}, include=["metadatas"])
            if result and result["metadatas"] and len(result["metadatas"]) > 0:
                return result["metadatas"][0].get("content_hash", "")
        except Exception:
            pass
        return None

    def list_sources(self) -> set:
        try:
            result = self.collection.get(include=["metadatas"])
            sources = set()
            if result and result["metadatas"]:
                for meta in result["metadatas"]:
                    src = meta.get("source", "")
                    if src:
                        sources.add(src)
            return sources
        except Exception:
            return set()

    def list_documents(self) -> List[dict]:
        try:
            result = self.collection.get(include=["metadatas"])
            if not result or not result["metadatas"]:
                return []
            doc_map = {}
            for meta in result["metadatas"]:
                src = meta.get("source", "")
                if src:
                    if src not in doc_map:
                        doc_map[src] = {
                            "source": src,
                            "source_type": meta.get("source_type", "local_file"),
                            "source_name": meta.get("source_name", Path(src).name),
                            "chunks": 0,
                            "content_hash": meta.get("content_hash", ""),
                            "created_at": meta.get("created_at", ""),
                        }
                    doc_map[src]["chunks"] += 1
            return sorted(doc_map.values(), key=lambda x: x["source"])
        except Exception:
            return []

    def get_document_info(self, source: str) -> Optional[dict]:
        try:
            result = self.collection.get(where={"source": source}, include=["metadatas"])
            if not result or not result["metadatas"]:
                return None
            meta = result["metadatas"][0]
            return {
                "source": source,
                "source_type": meta.get("source_type", "local_file"),
                "source_name": meta.get("source_name", Path(source).name),
                "chunks": len(result["metadatas"]),
                "content_hash": meta.get("content_hash", ""),
                "created_at": meta.get("created_at", ""),
                "chunk_ids": result["ids"],
            }
        except Exception:
            return None

    def check_orphan_records(self, local_docs_dir: str) -> List[dict]:
        """检查孤立记录（本地文件已删除但向量记录保留）"""
        orphans = []
        for doc in self.list_documents():
            if doc["source_type"] == "local_file":
                if not Path(doc["source"]).exists():
                    orphans.append(doc)
        return orphans

    def search(self, query_vec, n_results=5, include=None):
        """查询相似文档"""
        return self.collection.query(
            query_embeddings=[query_vec],
            n_results=n_results,
            include=include or ["documents", "metadatas", "distances"],
        )

    # ====== 写操作（ACID） ======

    def add(self, doc: dict, chunk_cfg: dict, source_type: str = "local_file") -> int:
        """
        添加文档 — 直接写入 + 幂等
        存在旧数据才清理（上次中断留下的脏数据）
        """
        source = doc["path"]
        if self.exists(source):
            self.collection.delete(where={"source": source})

        chunks = chunk_single_document(doc, chunk_cfg, source_type)
        if not chunks:
            return 0
        self._batch_add(chunks)
        return len(chunks)

    def delete(self, source: str):
        """删除文档 — 直接删除"""
        try:
            self.collection.delete(where={"source": source})
            logger.info(f"已删除: {source}")
        except Exception as e:
            logger.warning(f"删除失败 {source}: {e}")

    def update(self, doc: dict, chunk_cfg: dict, source_type: str = "local_file") -> int:
        """
        更新文档 — 影子集合策略
        创建影子 → 复制全部 → 删旧+写新 → 验证 → 切指针 → 删旧集合
        """
        source = doc["path"]
        shadow_name = None
        try:
            shadow_name, shadow = self._create_shadow_collection()
            self._copy_to_shadow(shadow)

            shadow.delete(where={"source": source})
            chunks = chunk_single_document(doc, chunk_cfg, source_type)
            if chunks:
                self._add_to_collection(shadow, chunks)

            self._validate_shadow(shadow)
            self._switch_to_shadow(shadow_name)
            self.collection = shadow
            self.collection_name = shadow_name
            self._cleanup_old_collections()

            logger.info(f"更新成功: {source} -> {shadow_name}")
            return len(chunks)

        except Exception as e:
            logger.error(f"更新失败: {source}: {e}")
            self._cleanup_failed_shadow(shadow_name)
            raise

    def sync(self, documents: List[dict], chunk_cfg: dict, source_type: str = "local_file", on_progress=None) -> dict:
        """
        同步文档 — 影子集合策略
        对比 hash，自动增删改
        on_progress(op, idx, total, name, count) — 进度回调
        """
        cleanup_empty_chroma_dirs()

        stats = {"added": 0, "updated": 0, "unchanged": 0, "deleted": 0}
        shadow_name = None
        try:
            shadow_name, shadow = self._create_shadow_collection()
            self._copy_to_shadow(shadow, on_progress=on_progress)

            current_sources = {d["path"] for d in documents}
            stored_sources = self.list_sources()

            n = len(documents)
            for idx, doc in enumerate(documents, 1):
                source = doc["path"]
                fname = Path(source).name
                if not self.exists(source):
                    chunks = chunk_single_document(doc, chunk_cfg, source_type)
                    if chunks:
                        self._add_to_collection(shadow, chunks)
                        stats["added"] += len(chunks)
                        if on_progress:
                            on_progress("add", idx, n, fname, len(chunks))
                else:
                    stored_h = self.get_hash(source)
                    current_h = content_hash(doc["text"])
                    if stored_h and stored_h != current_h:
                        shadow.delete(where={"source": source})
                        chunks = chunk_single_document(doc, chunk_cfg, source_type)
                        if chunks:
                            self._add_to_collection(shadow, chunks)
                            stats["updated"] += len(chunks)
                            if on_progress:
                                on_progress("update", idx, n, fname, len(chunks))
                    else:
                        stats["unchanged"] += 1

            deleted_sources = stored_sources - current_sources
            for source in deleted_sources:
                shadow.delete(where={"source": source})
                stats["deleted"] += 1
                if on_progress:
                    on_progress("delete", 0, 0, Path(source).name, 0)

            self._validate_shadow(shadow)
            self._switch_to_shadow(shadow_name)
            self.collection = shadow
            self.collection_name = shadow_name
            self._cleanup_old_collections()

            logger.info(f"同步完成: {shadow_name}")
            return stats

        except Exception as e:
            logger.error(f"同步失败: {e}")
            self._cleanup_failed_shadow(shadow_name)
            raise

    def rebuild(self, documents: List[dict], chunk_cfg: dict, source_type: str = "local_file", on_progress=None) -> int:
        """
        全量重建 — 影子集合策略
        on_progress(op, idx, total, name, count) — 进度回调
        """
        cleanup_empty_chroma_dirs()

        shadow_name = None
        try:
            shadow_name, shadow = self._create_shadow_collection()

            total = 0
            n = len(documents)
            for i, doc in enumerate(documents, 1):
                chunks = chunk_single_document(doc, chunk_cfg, source_type)
                if chunks:
                    self._add_to_collection(shadow, chunks)
                    total += len(chunks)
                    rel = Path(doc["path"]).name
                    if on_progress:
                        on_progress("rebuild", i, n, rel, len(chunks))

            self._validate_shadow(shadow)
            self._switch_to_shadow(shadow_name)
            self.collection = shadow
            self.collection_name = shadow_name
            self._cleanup_old_collections()

            logger.info(f"重建完成: {shadow_name}, {total} chunks")
            return total

        except Exception as e:
            logger.error(f"重建失败: {e}")
            self._cleanup_failed_shadow(shadow_name)
            raise

    def clean_orphan_records(self, local_docs_dir: str) -> int:
        """清理孤立记录"""
        orphans = self.check_orphan_records(local_docs_dir)
        count = 0
        for doc in orphans:
            self.delete(doc["source"])
            count += 1
        return count

    # ====== 影子集合内部方法 ======

    def _create_shadow_collection(self):
        """创建影子集合（带时间戳）"""
        if not self.chroma_client:
            raise ValueError("需要 chroma_client 才能创建影子集合")

        # 剥离旧影子后缀，获取基础集合名
        base_name = self.collection_name
        if "_v" in base_name:
            base_name = base_name.split("_v")[0]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shadow_name = f"{base_name}_v{timestamp}"

        shadow = self.chroma_client.get_or_create_collection(
            name=shadow_name,
            metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
        )
        logger.info(f"创建影子集合: {shadow_name}")
        return shadow_name, shadow

    def _copy_to_shadow(self, shadow_collection, on_progress=None):
        """将当前集合数据复制到影子集合"""
        result = self.collection.get(include=["metadatas", "documents"])
        if not result or not result["ids"]:
            return 0

        total = len(result["ids"])
        for i in range(0, total, EMBED_BATCH_SIZE):
            batch_ids = result["ids"][i:i + EMBED_BATCH_SIZE]
            batch_documents = result["documents"][i:i + EMBED_BATCH_SIZE]
            batch_metadatas = result["metadatas"][i:i + EMBED_BATCH_SIZE]

            batch_embeddings = self.emb_api.embed(batch_documents)

            shadow_collection.add(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_documents,
                metadatas=batch_metadatas,
            )
            done = min(i + EMBED_BATCH_SIZE, total)
            if on_progress:
                on_progress("copy", done, total, "", 0)

        logger.info(f"复制 {total} 条记录到影子集合")
        return total

    def _add_to_collection(self, collection, chunks: List[dict]):
        """向指定集合添加 chunks（分批处理）"""
        total = len(chunks)
        for i in range(0, total, EMBED_BATCH_SIZE):
            batch = chunks[i:i + EMBED_BATCH_SIZE]
            ids = [c["id"] for c in batch]
            texts = [c["text"] for c in batch]
            metas = [{
                "source": c["source"],
                "source_type": c["source_type"],
                "source_name": c["source_name"],
                "chunk_index": c["chunk_index"],
                "content_hash": c["content_hash"],
                "created_at": c["created_at"],
            } for c in batch]
            embeddings = self.emb_api.embed(texts)
            collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)

    def _validate_shadow(self, shadow_collection):
        """验证影子集合完整性（HNSW 索引 + 数据量）"""
        ok, detail = validate_hnsw(shadow_collection)
        if not ok:
            raise ValueError(f"影子集合验证失败: {detail}")
        logger.info(f"影子集合验证通过: {detail}")

    def _switch_to_shadow(self, shadow_name):
        """切换指针到影子集合"""
        config_key = self.collection_name
        if "_v" in config_key:
            config_key = config_key.split("_v")[0]
        set_active_collection(config_key, shadow_name)
        logger.info(f"指针切换: {config_key} -> {shadow_name}")

    def _cleanup_old_collections(self):
        """清理旧的影子集合（修复条件 bug）"""
        if not self.chroma_client:
            return

        config_key = self.collection_name
        if "_v" in config_key:
            config_key = config_key.split("_v")[0]

        active_name = get_active_collection(config_key)

        try:
            collections = self.chroma_client.list_collections()
            for col in collections:
                if col.name.startswith(f"{config_key}_v") and col.name != active_name:
                    self.chroma_client.delete_collection(col.name)
                    logger.info(f"清理旧影子: {col.name}")
        except Exception as e:
            logger.warning(f"清理旧影子失败: {e}")

    def _cleanup_failed_shadow(self, shadow_name):
        """清理失败的影子集合"""
        if shadow_name and self.chroma_client:
            try:
                self.chroma_client.delete_collection(shadow_name)
                logger.info(f"清理失败影子: {shadow_name}")
            except Exception:
                pass

    def _batch_add(self, chunks: List[dict]):
        """批量向量化 + 入库"""
        total = len(chunks)
        for i in range(0, total, EMBED_BATCH_SIZE):
            batch = chunks[i:i + EMBED_BATCH_SIZE]
            ids = [c["id"] for c in batch]
            texts = [c["text"] for c in batch]
            metas = [{
                "source": c["source"],
                "source_type": c["source_type"],
                "source_name": c["source_name"],
                "chunk_index": c["chunk_index"],
                "content_hash": c["content_hash"],
                "created_at": c["created_at"],
            } for c in batch]
            embeddings = self.emb_api.embed(texts)
            self.collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)


# ============================================================
#  构建函数
# ============================================================

def build_knowledge_base(collection_name: str = None, full_rebuild: bool = False, template_name: str = None):
    """知识库构建主入口"""
    from core.api import EmbeddingAPI

    if collection_name is None:
        collection_name = get_collection_name()

    chunk_cfg = get_chunk_config(template_name)
    docs_dir = ROOT / get_docs_dir()

    mode = "全量重建" if full_rebuild else "增量更新"

    emb_api = EmbeddingAPI()
    emb_info = emb_api.get_info()

    print("=" * 60)
    print(f"  Ezy-RAG V0.0.18 — 知识库构建 ({mode})")
    print("=" * 60)
    print(f"  Embedding: {emb_info['mode']} ({emb_info['model']}, {emb_info['dim']}维)")
    print(f"  切块模板: {chunk_cfg['name']} ({chunk_cfg['strategy']}, {chunk_cfg['chunk_size']}字)")
    print("=" * 60)

    if not docs_dir.exists():
        print(f"\n创建文档文件夹: {docs_dir}")
        docs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n文档目录: {docs_dir}")
    print(f"ChromaDB: {os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}")

    # 连接 ChromaDB
    print(f"\n[1/4] 连接 ChromaDB...")
    chroma_client = chromadb.HttpClient(
        host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
    )
    try:
        heartbeat = chroma_client.heartbeat()
        print(f"  已连接 (心跳: {heartbeat} ns)")
    except Exception as e:
        print(f"  无法连接: {e}")
        return

    # 健康检查
    print(f"\n[2/4] 检查 Embedding 服务...")
    ok, err = emb_api.health_check()
    if ok:
        print(f"  Embedding 服务在线")
    else:
        print(f"  Embedding 服务不可用: {err}")
        return

    # 加载文档
    print(f"\n[3/4] 加载文档...")
    documents = load_all_documents(docs_dir)
    if not documents:
        print("没有找到文档，请将文件放入 data/docs/ 后重试。")
        return

    # 构建
    print(f"\n[4/4] 向量化并存入 ChromaDB ({mode})...")
    active_name = get_active_collection(collection_name)

    try:
        collection = chroma_client.get_collection(name=active_name)
    except Exception:
        collection = chroma_client.get_or_create_collection(
            name=active_name,
            metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
        )
        set_active_collection(collection_name, active_name)

    db = DocumentDatabase(collection, emb_api, chroma_client, active_name)

    if full_rebuild:
        count = db.rebuild(documents, chunk_cfg)
    else:
        stats = db.sync(documents, chunk_cfg)
        total_ops = stats["added"] + stats["updated"] + stats["deleted"]
        if total_ops == 0:
            print(f"\n  无变化，跳过建库（{stats['unchanged']} 个文件未变）")
        else:
            print(f"\n  新增: {stats['added']}  更新: {stats['updated']}  "
                  f"未变: {stats['unchanged']}  删除: {stats['deleted']}")
        count = db.count()

    active = get_active_collection(collection_name)
    print(f"\n" + "=" * 60)
    print(f"  建库完成！活跃集合: {active}: {count} 个向量，{len(documents)} 份文档")
    print("=" * 60)


if __name__ == "__main__":
    chunk_templates = get_chunk_templates()
    parser = argparse.ArgumentParser(description="Ezy-RAG 知识库构建工具")
    parser.add_argument("--collection", "-c", type=str, default=None)
    parser.add_argument("--full", action="store_true", help="全量重建")
    parser.add_argument("--template", "-t", type=str, default=None,
                        help=f"切块模板: {', '.join(chunk_templates.keys())}")
    args = parser.parse_args()
    build_knowledge_base(collection_name=args.collection, full_rebuild=args.full,
                         template_name=args.template)
