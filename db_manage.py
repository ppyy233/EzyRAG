# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.14 — 数据库管理脚本
用法: python db_manage.py
"""
import subprocess
import sys
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def show_status():
    """显示数据库状态"""
    import chromadb
    from config.settings import get_collection_name
    from core.repository import DocumentRepository
    from core.embedder import get_lm_proxy
    
    print("\n" + "=" * 60)
    print("  数据库状态")
    print("=" * 60)
    
    # 连接 ChromaDB
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
        print(f"  ChromaDB: 已连接")
    except Exception as e:
        print(f"  ChromaDB: 未连接 ({e})")
        return
    
    # 获取集合
    collection_name = get_active_collection_name()
    try:
        collection = client.get_collection(name=collection_name)
        emb_proxy = get_lm_proxy()
        repo = DocumentRepository(collection, emb_proxy)
        
        print(f"  集合名: {collection_name}")
        print(f"  总记录数: {repo.count()}")
        
        # 列出文档
        docs = repo.list_documents()
        if docs:
            print(f"\n  文档列表:")
            print(f"  {'-'*50}")
            for doc in docs:
                source = Path(doc['source']).name
                print(f"  {source:<30} {doc['chunks']} chunks")
            print(f"  {'-'*50}")
            print(f"  总计: {len(docs)} 个文档, {repo.count()} 个 chunks")
        else:
            print(f"\n  数据库为空")
    except Exception as e:
        print(f"  集合不存在: {e}")


def get_active_collection_name():
    """获取当前活跃集合名"""
    import json
    pointer_file = ROOT / "runtime" / "state" / "collection_pointer.json"
    if pointer_file.exists():
        with open(pointer_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("default_collection", "default_collection")
    return "default_collection"


def rebuild_database():
    """全量重建数据库"""
    print("\n全量重建数据库...")
    subprocess.run([sys.executable, "-m", "core.builder", "--full"], cwd=ROOT)


def update_database():
    """增量更新数据库"""
    print("\n增量更新数据库...")
    subprocess.run([sys.executable, "-m", "core.builder"], cwd=ROOT)


def clean_old_collections():
    """清理旧的影子集合"""
    import chromadb
    
    print("\n清理旧的影子集合...")
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        
        active = get_active_collection_name()
        collections = client.list_collections()
        
        deleted = 0
        for col in collections:
            if col.name != active and not col.name.startswith("test_"):
                try:
                    client.delete_collection(col.name)
                    print(f"  删除: {col.name}")
                    deleted += 1
                except Exception as e:
                    print(f"  跳过: {col.name} ({e})")
        
        print(f"  清理完成，删除了 {deleted} 个集合")
    except Exception as e:
        print(f"  清理失败: {e}")


def clean_empty_folders():
    """清理空的 UUID 文件夹"""
    chroma_dir = ROOT / "data" / "chroma_db"
    
    print("\n清理空文件夹...")
    deleted = 0
    for item in chroma_dir.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            # 检查是否为空
            files = list(item.iterdir())
            if not files:
                item.rmdir()
                print(f"  删除: {item.name}")
                deleted += 1
    
    print(f"  清理完成，删除了 {deleted} 个空文件夹")


def start_services():
    """启动所有服务"""
    print("\n启动所有服务...")
    subprocess.run([sys.executable, "start_all.py"], cwd=ROOT)


def main():
    """主函数"""
    while True:
        print("\n" + "=" * 60)
        print("  Ezy-RAG V0.0.14 — 数据库管理")
        print("=" * 60)
        print("1. 查看数据库状态")
        print("2. 增量更新")
        print("3. 全量重建")
        print("4. 清理旧集合")
        print("5. 清理空文件夹")
        print("6. 启动服务")
        print("7. 退出")
        
        choice = input("\n请选择 (1-7): ").strip()
        
        if choice == "1":
            show_status()
        elif choice == "2":
            update_database()
        elif choice == "3":
            rebuild_database()
        elif choice == "4":
            clean_old_collections()
        elif choice == "5":
            clean_empty_folders()
        elif choice == "6":
            start_services()
        elif choice == "7":
            break
        else:
            print("无效的选择")


if __name__ == "__main__":
    main()
