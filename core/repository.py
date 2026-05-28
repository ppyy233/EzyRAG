# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 — 文档仓库
封装所有向量数据库操作，实现文档级 CRUD 和 ACID 事务

核心设计：
1. 每个文档是独立的 CRUD 单位
2. 向量库与本地文档库分离，删除本地文件不影响向量记录
3. 支持多种数据来源：local_file, web_crawl, api, manual
4. 孤立记录（本地文件已删除）保留并标记
"""
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import time
import logging

logger = logging.getLogger("Ezy-RAG-Repository")


def md5_short(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def chunk_single_document(doc: dict, chunk_cfg: dict, source_type: str = "local_file") -> List[dict]:
    """对单个文档切片"""
    from core.builder import split_text
    doc_hash = content_hash(doc["text"])
    chunks = split_text(doc["text"], chunk_cfg)
    result = []
    
    # 确定 source_name
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


class DocumentRepository:
    """
    文档仓库 — 封装所有向量数据库操作

    分离式设计：
    - 向量库是独立的，本地文档只是数据源之一
    - 删除本地文件时，向量库记录保留
    - 孤立记录（本地文件已删除）保留并标记
    """

    def __init__(self, collection, emb_proxy):
        self.collection = collection
        self.emb_proxy = emb_proxy

    # ====== Create ======

    def add(self, doc: dict, chunk_cfg: dict, source_type: str = "local_file") -> int:
        """添加单个文档，返回添加的 chunk 数量"""
        chunks = chunk_single_document(doc, chunk_cfg, source_type)
        if not chunks:
            return 0
        self._batch_add(chunks)
        return len(chunks)

    def add_many(self, documents: List[dict], chunk_cfg: dict, source_type: str = "local_file") -> int:
        """批量添加多个文档"""
        total = 0
        for doc in documents:
            total += self.add(doc, chunk_cfg, source_type)
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
        """获取单个文档的详细信息"""
        try:
            result = self.collection.get(
                where={"source": source},
                include=["metadatas"]
            )
            if not result or not result["metadatas"]:
                return None
            
            meta = result["metadatas"][0]
            doc_info = {
                "source": source,
                "source_type": meta.get("source_type", "local_file"),
                "source_name": meta.get("source_name", Path(source).name),
                "chunks": len(result["metadatas"]),
                "content_hash": meta.get("content_hash", ""),
                "created_at": meta.get("created_at", ""),
                "chunk_ids": result["ids"],
            }
            return doc_info
        except Exception:
            return None

    def check_orphan_records(self, local_docs_dir: str) -> List[dict]:
        """检查孤立记录（本地文件已删除但向量记录保留）"""
        orphans = []
        all_docs = self.list_documents()
        
        for doc in all_docs:
            if doc["source_type"] == "local_file":
                # 检查本地文件是否存在
                if not Path(doc["source"]).exists():
                    orphans.append(doc)
        
        return orphans

    # ====== Update ======

    def update(self, doc: dict, chunk_cfg: dict, source_type: str = "local_file") -> int:
        """
        更新文档 — 先删后加策略
        """
        source = doc["path"]

        # Step 1: 先删除旧 chunks
        self.delete(source)

        # Step 2: 再添加新 chunks
        new_count = self.add(doc, chunk_cfg, source_type)

        return new_count

    # ====== Delete ======

    def delete(self, source: str):
        """删除文档的所有向量记录"""
        try:
            self.collection.delete(where={"source": source})
            logger.info(f"已删除向量记录: {source}")
        except Exception as e:
            logger.warning(f"删除向量记录失败 {source}: {e}")

    def delete_local_file(self, file_path: str) -> bool:
        """删除本地文件（不影响向量记录）"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info(f"已删除本地文件: {file_path}")
                return True
            else:
                logger.warning(f"本地文件不存在: {file_path}")
                return False
        except Exception as e:
            logger.warning(f"删除本地文件失败 {file_path}: {e}")
            return False

    def clean_orphan_records(self, local_docs_dir: str) -> int:
        """清理孤立记录"""
        orphans = self.check_orphan_records(local_docs_dir)
        count = 0
        for doc in orphans:
            self.delete(doc["source"])
            count += 1
            logger.info(f"已清理孤立记录: {doc['source']}")
        return count

    # ====== 批量操作 ======

    def sync(self, documents: List[dict], chunk_cfg: dict, source_type: str = "local_file") -> dict:
        """
        同步文档 — 完整的 CRUD 操作
        返回操作统计

        注意：分离式设计下，不会自动删除本地文件
        """
        stats = {"added": 0, "updated": 0, "unchanged": 0, "deleted_vectors": 0}

        # 获取当前所有 source
        current_sources = {d["path"] for d in documents}
        stored_sources = self.list_sources()

        # Step 1: 处理新文件
        for doc in documents:
            if not self.exists(doc["path"]):
                stats["added"] += self.add(doc, chunk_cfg, source_type)

        # Step 2: 处理变更文件
        for doc in documents:
            if self.exists(doc["path"]):
                stored_h = self.get_hash(doc["path"])
                current_h = content_hash(doc["text"])
                if stored_h and stored_h != current_h:
                    stats["updated"] += self.update(doc, chunk_cfg, source_type)
                else:
                    stats["unchanged"] += 1

        # Step 3: 处理已删文件（只删除向量记录，不影响本地文件）
        deleted_sources = stored_sources - current_sources
        for source in deleted_sources:
            # 检查是否是本地文件
            doc_info = self.get_document_info(source)
            if doc_info and doc_info["source_type"] == "local_file":
                # 本地文件已删除，保留向量记录（孤立记录）
                logger.info(f"检测到孤立记录（本地文件已删除）: {source}")
            else:
                # 非本地文件，删除向量记录
                self.delete(source)
                stats["deleted_vectors"] += 1

        return stats

    # ====== 内部方法 ======

    def _batch_add(self, chunks: List[dict], batch_size: int = 50):
        """批量向量化 + 入库"""
        total = len(chunks)
        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]
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
            embeddings = self.emb_proxy.embed_sync(texts, priority=100)
            self.collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)
            done = i + len(batch)
            pct = min(100, int(done / total * 100))
            print(f"  进度: {done}/{total} ({pct}%)")
            if i + batch_size < total:
                time.sleep(0.1)
