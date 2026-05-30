# -*- coding: utf-8 -*-
"""
Ezy-RAG — 数据库操作模块
提供 ChromaDB 的 CRUD 操作和 ACID 事务支持

ACID 策略：
  add     → 直接写入 + 幂等（先检查exists，存在则delete）
  delete  → 直接删除（ChromaDB原子操作）
  update  → 影子集合策略（原子性保证）
  sync    → 影子集合策略（批量增删改）
  rebuild → 影子集合策略（全量重建）

用法:
  from core.database import DocumentDatabase
"""
import os
import sys
import logging
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.pointer import (
    read_pointer, write_pointer, get_active_collection, set_active_collection,
)
from config.settings import get_chroma_hnsw_metadata
from core.maintenance import _get_hnsw_segment_id, validate_hnsw
from core.chunking import chunk_single_document
from core.utils import content_hash
import chromadb

# Embedding API 单次最大批量（从环境变量读取，默认 50）
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "50"))

logger = logging.getLogger("Ezy-RAG-DB")


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
            if result and result["metadatas"]:
                return {m.get("source", "") for m in result["metadatas"]}
        except Exception:
            pass
        return set()

    def list_documents(self) -> List[dict]:
        try:
            result = self.collection.get(include=["metadatas"])
            if result and result["metadatas"]:
                docs = []
                seen = {}
                for m in result["metadatas"]:
                    source = m.get("source", "")
                    if not source:
                        continue
                    if source not in seen:
                        seen[source] = {
                            "source": source,
                            "source_name": m.get("source_name", ""),
                            "source_type": m.get("source_type", ""),
                            "content_hash": m.get("content_hash", ""),
                            "created_at": m.get("created_at", ""),
                            "chunks": 1,
                        }
                    else:
                        seen[source]["chunks"] += 1
                return list(seen.values())
        except Exception:
            pass
        return []

    def check_orphan_records(self, *local_dirs: str) -> List[dict]:
        """检查孤立记录（本地文件已删除，但向量记录还在）
        
        Args:
            *local_dirs: 一个或多个本地目录路径
            
        Returns:
            孤立记录列表
        """
        # 收集所有本地文件路径
        all_local_files = set()
        for dir_path in local_dirs:
            p = Path(dir_path)
            if p.exists():
                for f in p.rglob("*"):
                    if f.is_file():
                        all_local_files.add(str(f.resolve()))
        
        # 检查向量记录
        orphans = []
        for doc in self.list_documents():
            if doc["source_type"] == "local_file":
                source = Path(doc["source"])
                # 检查文件是否存在
                if not source.exists() and str(source.resolve()) not in all_local_files:
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
        更新单个文档 — 直接操作
        直接删除旧文档，添加新文档
        """
        source = doc["path"]
        
        # 直接删除旧文档
        self.delete(source)
        
        # 直接添加新文档
        chunks = chunk_single_document(doc, chunk_cfg, source_type)
        if chunks:
            self._add_to_collection(self.collection, chunks)
        
        logger.info(f"更新成功: {source}")
        return len(chunks)

    def sync(self, documents: List[dict], chunk_cfg: dict, source_type: str = "local_file", on_progress=None, stored_sources: set = None) -> dict:
        """
        同步文档 — 延迟加载（直接操作）
        对比 hash，自动增删改
        
        设计说明：
        - 直接在现有集合上操作，不使用影子集合
        - 每个 add/delete 操作都是原子的
        - 如果中途停止，可以重新运行 sync 修复（最终一致性）
        - 使用延迟加载：只读取变化的文件内容
        
        on_progress(op, idx, total, name, count) — 进度回调
        stored_sources: 已查询的源集合（避免重复查询）
        """
        stats = {"added": 0, "updated": 0, "unchanged": 0, "deleted": 0}
        
        current_sources = {d["path"] for d in documents}
        # 如果外部已经查询过，直接使用；否则查询一次
        if stored_sources is None:
            stored_sources = self.list_sources()
        
        # 计算差异
        new_sources = current_sources - stored_sources      # 需要添加
        delete_sources = stored_sources - current_sources   # 需要删除
        common_sources = current_sources & stored_sources   # 需要检查更新
        
        n = len(documents)
        
        # 1. 处理新增文档
        for idx, doc in enumerate(documents, 1):
            if doc["path"] in new_sources:
                fname = Path(doc["path"]).name
                chunks = chunk_single_document(doc, chunk_cfg, source_type)
                if chunks:
                    self._add_to_collection(self.collection, chunks)
                    stats["added"] += len(chunks)
                    if on_progress:
                        on_progress("add", idx, n, fname, len(chunks))
        
        # 2. 处理更新文档（对比 hash，延迟加载）
        for idx, doc in enumerate(documents, 1):
            if doc["path"] in common_sources:
                fname = Path(doc["path"]).name
                stored_h = self.get_hash(doc["path"])
                # 使用延迟加载：doc["text"] 已经在调用前读取
                current_h = content_hash(doc["text"])
                if stored_h != current_h:
                    # 直接更新
                    self.update(doc, chunk_cfg, source_type)
                    stats["updated"] += 1
                    if on_progress:
                        on_progress("update", idx, n, fname, 0)
                else:
                    stats["unchanged"] += 1
        
        # 3. 处理删除文档
        for source in delete_sources:
            self.delete(source)
            stats["deleted"] += 1
            if on_progress:
                on_progress("delete", 0, 0, Path(source).name, 0)
        
        logger.info(f"同步完成: 新增 {stats['added']}, 更新 {stats['updated']}, 删除 {stats['deleted']}, 未变 {stats['unchanged']}")
        return stats

    def rebuild(self, documents: List[dict], chunk_cfg: dict, source_type: str = "local_file", on_progress=None) -> int:
        """
        全量重建 — 影子集合策略
        on_progress(op, idx, total, name, count) — 进度回调
        """
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

        # 从配置获取 ChromaDB 支持的 HNSW 参数
        metadata = get_chroma_hnsw_metadata()

        shadow = self.chroma_client.get_or_create_collection(
            name=shadow_name,
            metadata=metadata,
        )
        logger.info(f"创建影子集合: {shadow_name}")
        return shadow_name, shadow

    def _copy_to_shadow(self, shadow_collection, on_progress=None):
        """将当前集合数据复制到影子集合（重新向量化）"""
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
        """清理旧的影子集合（SQLite + 磁盘目录）"""
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
                    hnsw_seg_id = _get_hnsw_segment_id(col.name)
                    self.chroma_client.delete_collection(col.name)
                    logger.info(f"清理旧影子 SQLite: {col.name}")
                    if hnsw_seg_id:
                        seg_dir = ROOT / "data" / "chroma_db" / hnsw_seg_id
                        if seg_dir.exists():
                            shutil.rmtree(seg_dir)
                            logger.info(f"清理旧影子目录: {hnsw_seg_id}")
        except Exception as e:
            logger.warning(f"清理旧影子失败: {e}")

    def _cleanup_failed_shadow(self, shadow_name):
        """清理失败的影子集合（SQLite + 磁盘目录）"""
        if not shadow_name or not self.chroma_client:
            return
        try:
            hnsw_seg_id = _get_hnsw_segment_id(shadow_name)
            self.chroma_client.delete_collection(shadow_name)
            logger.info(f"清理失败影子 SQLite: {shadow_name}")
            if hnsw_seg_id:
                seg_dir = ROOT / "data" / "chroma_db" / hnsw_seg_id
                if seg_dir.exists():
                    shutil.rmtree(seg_dir)
                    logger.info(f"清理失败影子目录: {hnsw_seg_id}")
        except Exception as e:
            logger.warning(f"清理失败影子失败: {e}")

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
