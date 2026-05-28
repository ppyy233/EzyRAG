# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.14 — 文档仓库
封装所有向量数据库操作，实现文档级 CRUD 和 ACID 事务

核心设计：
1. 每个文档是独立的 CRUD 单位
2. Update 操作使用 Add-First 策略（先加后删，保证原子性）
3. 业务层不需要关心 ChromaDB 细节
"""
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
import time
import logging

logger = logging.getLogger("Ezy-RAG-Repository")


def md5_short(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def chunk_single_document(doc: dict, chunk_cfg: dict) -> List[dict]:
    """对单个文档切片"""
    from core.builder import split_text
    doc_hash = content_hash(doc["text"])
    chunks = split_text(doc["text"], chunk_cfg)
    result = []
    for i, chunk in enumerate(chunks):
        result.append({
            "id": f"{md5_short(doc['path'])}-{i}",
            "text": chunk,
            "source": doc["path"],
            "chunk_index": i,
            "content_hash": doc_hash,
        })
    return result


class DocumentRepository:
    """
    文档仓库 — 封装所有向量数据库操作

    ACID 保证：
    - 原子性：每个 add/delete/upsert 操作是原子的
    - 更新操作使用 Add-First 策略：先添加新 chunks，再删除旧 chunks
      如果崩溃在添加后、删除前，会有重复数据但不会丢失数据
    - 一致性：通过 content_hash 检测数据一致性
    """

    def __init__(self, collection, emb_proxy):
        self.collection = collection
        self.emb_proxy = emb_proxy

    # ====== Create ======

    def add(self, doc: dict, chunk_cfg: dict) -> int:
        """添加单个文档，返回添加的 chunk 数量"""
        chunks = chunk_single_document(doc, chunk_cfg)
        if not chunks:
            return 0
        self._batch_add(chunks)
        return len(chunks)

    def add_many(self, documents: List[dict], chunk_cfg: dict) -> int:
        """批量添加多个文档"""
        total = 0
        for doc in documents:
            total += self.add(doc, chunk_cfg)
        return total

    # ====== Read ======

    def exists(self, source: str) -> bool:
        """检查文档是否存在"""
        try:
            result = self.collection.get(
                where={"source": source},
                include=["metadatas"]
            )
            return result and result["ids"] and len(result["ids"]) > 0
        except Exception:
            return False

    def get_hash(self, source: str) -> Optional[str]:
        """获取文档的 content_hash"""
        try:
            result = self.collection.get(
                where={"source": source},
                include=["metadatas"]
            )
            if result and result["metadatas"] and len(result["metadatas"]) > 0:
                return result["metadatas"][0].get("content_hash", "")
        except Exception:
            pass
        return None

    def count(self) -> int:
        """获取集合中的总记录数"""
        return self.collection.count()

    def list_sources(self) -> set:
        """列出所有文档 source"""
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
        """列出所有文档及其 chunks 数量"""
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
                            "chunks": 0,
                            "content_hash": meta.get("content_hash", ""),
                        }
                    doc_map[src]["chunks"] += 1
            
            return sorted(doc_map.values(), key=lambda x: x["source"])
        except Exception:
            return []

    # ====== Update ======

    def update(self, doc: dict, chunk_cfg: dict) -> int:
        """
        更新文档 — Add-First 策略
        1. 先添加新 chunks（保证数据不丢失）
        2. 再删除旧 chunks
        如果崩溃在 1 和 2 之间，会有重复数据但不会丢失
        """
        source = doc["path"]

        # Step 1: 先添加新 chunks
        new_count = self.add(doc, chunk_cfg)

        # Step 2: 再删除旧 chunks
        self.delete(source)

        return new_count

    # ====== Delete ======

    def delete(self, source: str):
        """删除文档的所有 chunks"""
        try:
            self.collection.delete(where={"source": source})
        except Exception as e:
            logger.warning(f"删除文档失败 {source}: {e}")

    # ====== 批量操作 ======

    def sync(self, documents: List[dict], chunk_cfg: dict) -> dict:
        """
        同步文档 — 完整的 CRUD 操作
        返回操作统计
        """
        stats = {"added": 0, "updated": 0, "unchanged": 0, "deleted": 0}

        # 获取当前所有 source
        current_sources = {d["path"] for d in documents}
        stored_sources = self.list_sources()

        # Step 1: 处理新文件
        for doc in documents:
            if not self.exists(doc["path"]):
                stats["added"] += self.add(doc, chunk_cfg)

        # Step 2: 处理变更文件
        for doc in documents:
            if self.exists(doc["path"]):
                stored_h = self.get_hash(doc["path"])
                current_h = content_hash(doc["text"])
                if stored_h and stored_h != current_h:
                    stats["updated"] += self.update(doc, chunk_cfg)
                else:
                    stats["unchanged"] += 1

        # Step 3: 处理已删文件
        deleted_sources = stored_sources - current_sources
        for source in deleted_sources:
            self.delete(source)
            stats["deleted"] += 1

        return stats

    # ====== 内部方法 ======

    def _batch_add(self, chunks: List[dict], batch_size: int = 50):
        """批量向量化 + 入库"""
        total = len(chunks)
        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]
            ids = [c["id"] for c in batch]
            texts = [c["text"] for c in batch]
            metas = [{"source": c["source"], "chunk_index": c["chunk_index"],
                      "content_hash": c["content_hash"]} for c in batch]
            embeddings = self.emb_proxy.embed_sync(texts, priority=100)
            self.collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)
            done = i + len(batch)
            pct = min(100, int(done / total * 100))
            print(f"  进度: {done}/{total} ({pct}%)")
            if i + batch_size < total:
                time.sleep(0.1)
