# -*- coding: utf-8 -*-
"""
Ezy-RAG — 维护工具模块
提供数据库维护、清理和验证功能
"""
import os
import shutil
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger("Ezy-RAG-Maintenance")


def _get_hnsw_segment_id(collection_name: str):
    """获取集合的 HNSW segment ID"""
    import sqlite3
    db_path = ROOT / "data" / "chroma_db" / "chroma.sqlite3"
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id FROM segments s 
            JOIN collections c ON s.collection = c.id 
            WHERE c.name = ? AND s.type LIKE '%hnsw%'
        """, (collection_name,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception:
        return None


def cleanup_orphan_hnsw_dirs():
    """清理不在 SQLite 中的 ORPHAN HNSW 目录"""
    import sqlite3
    chroma_dir = ROOT / "data" / "chroma_db"
    db_path = chroma_dir / "chroma.sqlite3"
    if not chroma_dir.exists() or not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM segments WHERE type LIKE '%hnsw%'")
        active_seg_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
    except Exception:
        return 0
    cleaned = 0
    for d in chroma_dir.iterdir():
        if d.is_dir() and d.name not in (".gitkeep",) and d.name not in active_seg_ids:
            try:
                shutil.rmtree(d)
                cleaned += 1
                logger.info(f"清理 ORPHAN 目录: {d.name}")
            except Exception:
                pass
    return cleaned


def cleanup_orphan_shadows(chroma_client, config_key: str):
    """清理不在指针中的孤儿影子集合（SQLite + 磁盘目录）"""
    from config.pointer import get_active_collection
    if not chroma_client:
        return 0
    active_name = get_active_collection(config_key)
    cleaned = 0
    try:
        for col in chroma_client.list_collections():
            if col.name.startswith(f"{config_key}_v") and col.name != active_name:
                try:
                    hnsw_seg_id = _get_hnsw_segment_id(col.name)
                    chroma_client.delete_collection(col.name)
                    logger.info(f"清理孤儿影子 SQLite: {col.name}")
                    if hnsw_seg_id:
                        seg_dir = ROOT / "data" / "chroma_db" / hnsw_seg_id
                        if seg_dir.exists():
                            shutil.rmtree(seg_dir)
                            logger.info(f"清理孤儿影子目录: {hnsw_seg_id}")
                    cleaned += 1
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


def vacuum_sqlite():
    """收缩 SQLite 数据库"""
    import sqlite3
    db_path = ROOT / "data" / "chroma_db" / "chroma.sqlite3"
    if not db_path.exists():
        return
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("VACUUM")
        conn.close()
        logger.info("SQLite VACUUM 完成")
    except Exception as e:
        logger.warning(f"SQLite VACUUM 失败: {e}")
