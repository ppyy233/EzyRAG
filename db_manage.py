# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.14 — 数据库管理脚本
用法: python db_manage.py

功能：
1. 查看文档映射表（本地文档 vs 向量库文档）
2. 添加文档到向量库
3. 从向量库删除文档
4. 更新向量库中的文档
5. 同步本地文件和向量库
6. 全量重建向量库
7. 启动服务
"""
import subprocess
import sys
import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import chromadb
from config.settings import get_chunk_config, get_collection_name
from core.embedder import get_lm_proxy
from core.repository import DocumentRepository


def get_local_documents() -> List[str]:
    """获取本地文档列表"""
    docs_dir = ROOT / "data" / "docs"
    if not docs_dir.exists():
        return []
    
    documents = []
    for f in docs_dir.glob("**/*"):
        if f.is_file() and f.suffix in {".txt", ".md", ".pdf", ".docx", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs"}:
            # 使用完整绝对路径
            documents.append(str(f))
    
    return sorted(documents)


def get_vector_documents() -> Dict[str, dict]:
    """获取向量库文档列表"""
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        
        collection_name = get_active_collection_name()
        collection = client.get_collection(name=collection_name)
        emb_proxy = get_lm_proxy()
        repo = DocumentRepository(collection, emb_proxy)
        
        docs = repo.list_documents()
        return {doc["source"]: doc for doc in docs}
    except Exception as e:
        print(f"  获取向量库文档失败: {e}")
        return {}


def get_active_collection_name() -> str:
    """获取当前活跃集合名"""
    pointer_file = ROOT / "runtime" / "state" / "collection_pointer.json"
    if pointer_file.exists():
        with open(pointer_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("default_collection", "default_collection")
    return "default_collection"


def show_status():
    """显示数据库状态"""
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
    except Exception as e:
        print(f"  集合不存在: {e}")


def list_documents():
    """显示本地文档和向量库文档的映射"""
    print("\n" + "=" * 60)
    print("  文档映射表")
    print("=" * 60)
    
    # 获取本地文档
    local_docs = get_local_documents()
    
    # 获取向量库文档
    vector_docs = get_vector_documents()
    
    # 显示映射关系
    print(f"\n  {'本地文件':<40} {'向量库状态':<10} {'chunks':<8}")
    print(f"  {'-'*60}")
    
    for doc in local_docs:
        doc_name = Path(doc).name
        if doc in vector_docs:
            chunks = vector_docs[doc]["chunks"]
            print(f"  {doc_name:<40} {'已添加':<10} {chunks:<8}")
        else:
            print(f"  {doc_name:<40} {'未添加':<10} {'-':<8}")
    
    print(f"  {'-'*60}")
    print(f"  本地文档: {len(local_docs)} 个")
    print(f"  向量库文档: {len(vector_docs)} 个, {sum(d['chunks'] for d in vector_docs.values())} 个 chunks")


def add_documents(file_paths: List[str]):
    """添加指定文件到向量库"""
    print(f"\n  添加文档到向量库...")
    
    # 连接 ChromaDB
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
    except Exception as e:
        print(f"  无法连接 ChromaDB: {e}")
        return
    
    # 获取 Embedding 代理
    try:
        emb_proxy = get_lm_proxy()
    except Exception as e:
        print(f"  无法连接 Embedding 服务: {e}")
        return
    
    # 获取集合
    collection_name = get_active_collection_name()
    try:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
        )
    except Exception as e:
        print(f"  无法创建集合: {e}")
        return
    
    # 创建 Repository
    repo = DocumentRepository(collection, emb_proxy)
    
    # 添加文档
    chunk_cfg = get_chunk_config()
    total_added = 0
    
    for file_path in file_paths:
        # 检查文件是否存在
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"  [FAIL] 文件不存在: {file_path}")
            continue
        
        # 读取文件内容
        try:
            text = full_path.read_text(encoding="utf-8")
            doc_name = full_path.stem
            text = f"[文件名: {doc_name}]\n{text}"
        except Exception as e:
            print(f"  [FAIL] 读取文件失败: {file_path} ({e})")
            continue
        
        # 添加到向量库
        doc = {"path": file_path, "text": text}
        try:
            count = repo.add(doc, chunk_cfg)
            total_added += count
            print(f"  [OK] 添加成功: {file_path} ({count} chunks)")
        except Exception as e:
            print(f"  [FAIL] 添加失败: {file_path} ({e})")
    
    print(f"\n  添加完成! 共添加 {total_added} 个 chunks")


def add_all_documents():
    """添加所有本地文件到向量库"""
    local_docs = get_local_documents()
    if not local_docs:
        print("  没有找到本地文档")
        return
    
    print(f"  找到 {len(local_docs)} 个本地文档")
    add_documents(local_docs)


def delete_documents(file_paths: List[str]):
    """从向量库删除指定文件"""
    print(f"\n  从向量库删除文档...")
    
    # 连接 ChromaDB
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
    except Exception as e:
        print(f"  无法连接 ChromaDB: {e}")
        return
    
    # 获取 Embedding 代理
    try:
        emb_proxy = get_lm_proxy()
    except Exception as e:
        print(f"  无法连接 Embedding 服务: {e}")
        return
    
    # 获取集合
    collection_name = get_active_collection_name()
    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        print(f"  集合不存在: {e}")
        return
    
    # 创建 Repository
    repo = DocumentRepository(collection, emb_proxy)
    
    # 删除文档
    total_deleted = 0
    
    for file_path in file_paths:
        try:
            repo.delete(file_path)
            total_deleted += 1
            print(f"  [OK] 删除成功: {file_path}")
        except Exception as e:
            print(f"  [FAIL] 删除失败: {file_path} ({e})")
    
    print(f"\n  删除完成! 共删除 {total_deleted} 个文档")


def delete_all_documents():
    """从向量库删除所有文件"""
    vector_docs = get_vector_documents()
    if not vector_docs:
        print("  向量库为空")
        return
    
    print(f"  找到 {len(vector_docs)} 个向量库文档")
    delete_documents(list(vector_docs.keys()))


def update_documents(file_paths: List[str]):
    """更新向量库中的指定文件"""
    print(f"\n  更新向量库文档...")
    
    # 连接 ChromaDB
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
    except Exception as e:
        print(f"  无法连接 ChromaDB: {e}")
        return
    
    # 获取 Embedding 代理
    try:
        emb_proxy = get_lm_proxy()
    except Exception as e:
        print(f"  无法连接 Embedding 服务: {e}")
        return
    
    # 获取集合
    collection_name = get_active_collection_name()
    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        print(f"  集合不存在: {e}")
        return
    
    # 创建 Repository
    repo = DocumentRepository(collection, emb_proxy)
    
    # 更新文档
    chunk_cfg = get_chunk_config()
    total_updated = 0
    
    for file_path in file_paths:
        # 检查文件是否存在
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"  [FAIL] 文件不存在: {file_path}")
            continue
        
        # 读取文件内容
        try:
            text = full_path.read_text(encoding="utf-8")
            doc_name = full_path.stem
            text = f"[文件名: {doc_name}]\n{text}"
        except Exception as e:
            print(f"  [FAIL] 读取文件失败: {file_path} ({e})")
            continue
        
        # 更新向量库
        doc = {"path": file_path, "text": text}
        try:
            count = repo.update(doc, chunk_cfg)
            total_updated += count
            print(f"  [OK] 更新成功: {file_path} ({count} chunks)")
        except Exception as e:
            print(f"  [FAIL] 更新失败: {file_path} ({e})")
    
    print(f"\n  更新完成! 共更新 {total_updated} 个 chunks")


def update_all_documents():
    """更新向量库中的所有文件"""
    vector_docs = get_vector_documents()
    if not vector_docs:
        print("  向量库为空")
        return
    
    print(f"  找到 {len(vector_docs)} 个向量库文档")
    update_documents(list(vector_docs.keys()))


def sync_documents():
    """自动同步本地文件和向量库"""
    print(f"\n  同步本地文件和向量库...")
    
    # 获取本地文档
    local_docs = set(get_local_documents())
    
    # 获取向量库文档
    vector_docs = set(get_vector_documents().keys())
    
    # 计算差异
    new_docs = local_docs - vector_docs
    deleted_docs = vector_docs - local_docs
    
    # 显示差异
    print(f"\n  同步预览:")
    print(f"  {'-'*40}")
    print(f"  新增: {len(new_docs)} 个文档")
    print(f"  删除: {len(deleted_docs)} 个文档")
    print(f"  {'-'*40}")
    
    if not new_docs and not deleted_docs:
        print(f"  无变化，跳过同步")
        return
    
    # 用户确认
    confirm = input(f"\n  确认执行同步？(y/N): ").strip().lower()
    if confirm != 'y':
        print(f"  取消同步")
        return
    
    # 执行同步
    if new_docs:
        add_documents(list(new_docs))
    
    if deleted_docs:
        delete_documents(list(deleted_docs))
    
    print(f"\n  同步完成!")


def rebuild_database():
    """全量重建向量库"""
    print(f"\n  全量重建向量库...")
    
    # 用户确认
    confirm = input(f"  ⚠ 警告：这将清空向量库并重新添加所有文档！确认？(y/N): ").strip().lower()
    if confirm != 'y':
        print(f"  取消重建")
        return
    
    # 连接 ChromaDB
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
    except Exception as e:
        print(f"  无法连接 ChromaDB: {e}")
        return
    
    # 删除旧集合
    collection_name = get_active_collection_name()
    try:
        client.delete_collection(collection_name)
        print(f"  ✓ 删除旧集合: {collection_name}")
    except Exception:
        pass
    
    # 添加所有本地文档
    add_all_documents()
    
    print(f"\n  全量重建完成!")


def start_services():
    """启动所有服务"""
    print("\n  启动所有服务...")
    subprocess.run([sys.executable, "start_all.py"], cwd=ROOT)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ezy-RAG 数据库管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # list 命令
    subparsers.add_parser("list", help="显示文档映射表")
    
    # status 命令
    subparsers.add_parser("status", help="显示数据库状态")
    
    # add 命令
    add_parser = subparsers.add_parser("add", help="添加文档到向量库")
    add_parser.add_argument("files", nargs="*", help="文件路径")
    add_parser.add_argument("--all", action="store_true", help="添加所有本地文档")
    
    # delete 命令
    delete_parser = subparsers.add_parser("delete", help="从向量库删除文档")
    delete_parser.add_argument("files", nargs="*", help="文件路径")
    delete_parser.add_argument("--all", action="store_true", help="删除所有向量库文档")
    
    # update 命令
    update_parser = subparsers.add_parser("update", help="更新向量库中的文档")
    update_parser.add_argument("files", nargs="*", help="文件路径")
    update_parser.add_argument("--all", action="store_true", help="更新所有向量库文档")
    
    # sync 命令
    subparsers.add_parser("sync", help="同步本地文件和向量库")
    
    # rebuild 命令
    subparsers.add_parser("rebuild", help="全量重建向量库")
    
    # start 命令
    subparsers.add_parser("start", help="启动所有服务")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_documents()
    elif args.command == "status":
        show_status()
    elif args.command == "add":
        if args.all:
            add_all_documents()
        elif args.files:
            add_documents(args.files)
        else:
            print("  请指定文件路径或使用 --all 参数")
    elif args.command == "delete":
        if args.all:
            delete_all_documents()
        elif args.files:
            delete_documents(args.files)
        else:
            print("  请指定文件路径或使用 --all 参数")
    elif args.command == "update":
        if args.all:
            update_all_documents()
        elif args.files:
            update_documents(args.files)
        else:
            print("  请指定文件路径或使用 --all 参数")
    elif args.command == "sync":
        sync_documents()
    elif args.command == "rebuild":
        rebuild_database()
    elif args.command == "start":
        start_services()
    else:
        # 交互式菜单
        while True:
            print("\n" + "=" * 60)
            print("  Ezy-RAG V0.0.14 — 数据库管理")
            print("=" * 60)
            print("1. 查看文档映射表")
            print("2. 查看数据库状态")
            print("3. 添加文档")
            print("4. 删除文档")
            print("5. 更新文档")
            print("6. 同步本地文件和向量库")
            print("7. 全量重建向量库")
            print("8. 启动服务")
            print("9. 退出")
            
            choice = input("\n请选择 (1-9): ").strip()
            
            if choice == "1":
                list_documents()
            elif choice == "2":
                show_status()
            elif choice == "3":
                print("\n添加文档：")
                print("1. 添加指定文件")
                print("2. 添加所有本地文件")
                print("3. 返回")
                
                sub_choice = input("\n请选择 (1-3): ").strip()
                
                if sub_choice == "1":
                    files = input("请输入文件路径（多个文件用空格分隔）: ").strip().split()
                    if files:
                        add_documents(files)
                elif sub_choice == "2":
                    add_all_documents()
                elif sub_choice == "3":
                    continue
                else:
                    print("无效的选择")
            
            elif choice == "4":
                print("\n删除文档：")
                print("1. 删除指定文件")
                print("2. 删除所有向量库文档")
                print("3. 返回")
                
                sub_choice = input("\n请选择 (1-3): ").strip()
                
                if sub_choice == "1":
                    files = input("请输入文件路径（多个文件用空格分隔）: ").strip().split()
                    if files:
                        delete_documents(files)
                elif sub_choice == "2":
                    delete_all_documents()
                elif sub_choice == "3":
                    continue
                else:
                    print("无效的选择")
            
            elif choice == "5":
                print("\n更新文档：")
                print("1. 更新指定文件")
                print("2. 更新所有向量库文档")
                print("3. 返回")
                
                sub_choice = input("\n请选择 (1-3): ").strip()
                
                if sub_choice == "1":
                    files = input("请输入文件路径（多个文件用空格分隔）: ").strip().split()
                    if files:
                        update_documents(files)
                elif sub_choice == "2":
                    update_all_documents()
                elif sub_choice == "3":
                    continue
                else:
                    print("无效的选择")
            
            elif choice == "6":
                sync_documents()
            elif choice == "7":
                rebuild_database()
            elif choice == "8":
                start_services()
            elif choice == "9":
                break
            else:
                print("无效的选择")


if __name__ == "__main__":
    main()
