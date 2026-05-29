# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 — 数据库管理脚本
用法: python db_manage.py

功能：
1. 查看文档映射表（本地文档 vs 向量库文档）
2. 添加文档到向量库
3. 从向量库删除文档（保留本地文件）
4. 删除本地文件（保留向量记录）
5. 清理孤立向量记录
6. 同步本地文件和向量库
7. 全量重建向量库
8. 添加网页内容到向量库
"""
import subprocess
import sys
import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional

# Windows 终端编码修复
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import chromadb
from config.settings import get_chunk_config, get_collection_name
from core.scheduler import get_scheduler
from core.repository import DocumentRepository
from core.builder import SUPPORTED_EXT


def get_local_documents() -> List[str]:
    """获取本地文档列表"""
    docs_dir = ROOT / "data" / "docs"
    if not docs_dir.exists():
        return []
    documents = []
    for f in docs_dir.glob("**/*"):
        if f.is_file() and f.suffix in {".txt", ".md", ".pdf", ".docx", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs"}:
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
        emb_proxy = get_scheduler()
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
    collection_name = get_active_collection_name()
    try:
        collection = client.get_collection(name=collection_name)
        emb_proxy = get_scheduler()
        repo = DocumentRepository(collection, emb_proxy)
        print(f"  集合: {collection_name}")
        print(f"  总记录数: {repo.count()}")
        orphans = repo.check_orphan_records(str(ROOT / "data" / "docs"))
        if orphans:
            print(f"  [!] 孤立记录: {len(orphans)} 个（本地文件已删除）")
    except Exception as e:
        print(f"  集合不存在: {e}")


def list_documents():
    """显示本地文档和向量库文档的映射"""
    print("\n" + "=" * 60)
    print("  文档映射表")
    print("=" * 60)
    local_docs = get_local_documents()
    vector_docs = get_vector_documents()
    local_file_docs = {k: v for k, v in vector_docs.items() if v.get("source_type") == "local_file"}
    web_crawl_docs = {k: v for k, v in vector_docs.items() if v.get("source_type") == "web_crawl"}
    other_docs = {k: v for k, v in vector_docs.items() if v.get("source_type") not in ["local_file", "web_crawl"]}
    print(f"\n  本地文件映射:")
    print(f"  {'文件名':<30} {'状态':<10} {'chunks':<8}")
    print(f"  {'-'*50}")
    for doc in local_docs:
        doc_name = Path(doc).name
        if doc in local_file_docs:
            chunks = local_file_docs[doc]["chunks"]
            print(f"  {doc_name:<30} {'已添加':<10} {chunks:<8}")
        else:
            print(f"  {doc_name:<30} {'未添加':<10} {'-':<8}")
    orphans = [doc for doc in local_file_docs.values() if not Path(doc["source"]).exists()]
    if orphans:
        print(f"\n  孤立记录（本地文件已删除）:")
        for doc in orphans:
            print(f"  {doc['source_name']:<30} {doc['chunks']:<8}")
    if web_crawl_docs:
        print(f"\n  网页爬取数据:")
        for doc in web_crawl_docs.values():
            url = doc["source"][:35] + "..." if len(doc["source"]) > 38 else doc["source"]
            print(f"  {url:<40} {doc['chunks']:<8}")
    print(f"\n  本地文档: {len(local_docs)} 个")
    print(f"  向量库文档: {len(vector_docs)} 个, {sum(d['chunks'] for d in vector_docs.values())} chunks")


def add_documents(file_paths: List[str]):
    """添加指定文件到向量库"""
    print(f"\n  添加文档到向量库...")
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
    except Exception as e:
        print(f"  无法连接 ChromaDB: {e}")
        return
    try:
        emb_proxy = get_scheduler()
    except Exception as e:
        print(f"  无法连接 Embedding 服务: {e}")
        return
    collection_name = get_active_collection_name()
    try:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
        )
    except Exception as e:
        print(f"  无法创建集合: {e}")
        return
    repo = DocumentRepository(collection, emb_proxy)
    chunk_cfg = get_chunk_config()
    total_added = 0
    for file_path in file_paths:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"  [FAIL] 文件不存在: {file_path}")
            continue
        ext = full_path.suffix.lower()
        if ext not in SUPPORTED_EXT:
            print(f"  [SKIP] 不支持的文件格式: {file_path}")
            continue
        try:
            reader_fn = SUPPORTED_EXT[ext]
            text = reader_fn(str(full_path))
            if not text or not text.strip():
                print(f"  [SKIP] 文件内容为空: {file_path}")
                continue
            doc_name = full_path.stem
            text = f"[文件名: {doc_name}]\n{text}"
        except Exception as e:
            print(f"  [FAIL] 读取文件失败: {file_path} ({e})")
            continue
        doc = {"path": file_path, "text": text}
        try:
            count = repo.add(doc, chunk_cfg, source_type="local_file")
            total_added += count
            print(f"  [OK] 添加成功: {file_path} ({count} chunks)")
        except Exception as e:
            print(f"  [FAIL] 添加失败: {file_path} ({e})")
    print(f"\n  添加完成! 共添加 {total_added} chunks")


def add_all_documents():
    """添加所有本地文件到向量库"""
    local_docs = get_local_documents()
    if not local_docs:
        print("  没有找到本地文档")
        return
    print(f"  找到 {len(local_docs)} 个本地文档")
    add_documents(local_docs)


def delete_vector_records(file_paths: List[str]):
    """从向量库删除指定文件的记录（保留本地文件）"""
    print(f"\n  从向量库删除文档记录...")
    print(f"  注意：此操作只删除向量记录，本地文件不受影响")
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
    except Exception as e:
        print(f"  无法连接 ChromaDB: {e}")
        return
    try:
        emb_proxy = get_scheduler()
    except Exception as e:
        print(f"  无法连接 Embedding 服务: {e}")
        return
    collection_name = get_active_collection_name()
    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        print(f"  集合不存在: {e}")
        return
    repo = DocumentRepository(collection, emb_proxy)
    total_deleted = 0
    for file_path in file_paths:
        try:
            repo.delete(file_path)
            total_deleted += 1
            print(f"  [OK] 删除成功: {file_path}")
        except Exception as e:
            print(f"  [FAIL] 删除失败: {file_path} ({e})")
    print(f"\n  删除完成! 共删除 {total_deleted} 个文档的向量记录")


def delete_all_vector_records():
    """从向量库删除所有文件的记录"""
    vector_docs = get_vector_documents()
    if not vector_docs:
        print("  向量库为空")
        return
    print(f"  找到 {len(vector_docs)} 个向量库文档")
    print(f"  注意：此操作只删除向量记录，本地文件不受影响")
    confirm = input(f"  确认删除所有向量记录？(y/N): ").strip().lower()
    if confirm != 'y':
        print(f"  取消删除")
        return
    delete_vector_records(list(vector_docs.keys()))


def delete_local_files(file_paths: List[str]):
    """删除本地文件（保留向量记录）"""
    print(f"\n  删除本地文件...")
    print(f"  注意：此操作只删除本地文件，向量记录将保留")
    total_deleted = 0
    for file_path in file_paths:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"  [SKIP] 文件不存在: {file_path}")
            continue
        try:
            full_path.unlink()
            total_deleted += 1
            print(f"  [OK] 删除成功: {file_path}")
        except Exception as e:
            print(f"  [FAIL] 删除失败: {file_path} ({e})")
    print(f"\n  删除完成! 共删除 {total_deleted} 个本地文件")
    print(f"  提示：向量记录已保留，可通过查询继续检索到这些内容")


def clean_orphan_records():
    """清理孤立向量记录"""
    print(f"\n  清理孤立向量记录...")
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
    except Exception as e:
        print(f"  无法连接 ChromaDB: {e}")
        return
    try:
        emb_proxy = get_scheduler()
    except Exception as e:
        print(f"  无法连接 Embedding 服务: {e}")
        return
    collection_name = get_active_collection_name()
    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        print(f"  集合不存在: {e}")
        return
    repo = DocumentRepository(collection, emb_proxy)
    orphans = repo.check_orphan_records(str(ROOT / "data" / "docs"))
    if not orphans:
        print(f"  没有孤立记录")
        return
    print(f"\n  找到 {len(orphans)} 个孤立记录:")
    for doc in orphans:
        print(f"  {doc['source_name']:<30} {doc['chunks']:<8}")
    confirm = input(f"\n  确认清理这些孤立记录？(y/N): ").strip().lower()
    if confirm != 'y':
        print(f"  取消清理")
        return
    count = repo.clean_orphan_records(str(ROOT / "data" / "docs"))
    print(f"\n  清理完成! 共清理 {count} 个孤立记录")


def update_documents(file_paths: List[str]):
    """更新向量库中的指定文件"""
    print(f"\n  更新向量库文档...")
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
    except Exception as e:
        print(f"  无法连接 ChromaDB: {e}")
        return
    try:
        emb_proxy = get_scheduler()
    except Exception as e:
        print(f"  无法连接 Embedding 服务: {e}")
        return
    collection_name = get_active_collection_name()
    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        print(f"  集合不存在: {e}")
        return
    repo = DocumentRepository(collection, emb_proxy)
    chunk_cfg = get_chunk_config()
    total_updated = 0
    for file_path in file_paths:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"  [FAIL] 文件不存在: {file_path}")
            continue
        try:
            text = full_path.read_text(encoding="utf-8")
            doc_name = full_path.stem
            text = f"[文件名: {doc_name}]\n{text}"
        except Exception as e:
            print(f"  [FAIL] 读取文件失败: {file_path} ({e})")
            continue
        doc = {"path": file_path, "text": text}
        try:
            count = repo.update(doc, chunk_cfg, source_type="local_file")
            total_updated += count
            print(f"  [OK] 更新成功: {file_path} ({count} chunks)")
        except Exception as e:
            print(f"  [FAIL] 更新失败: {file_path} ({e})")
    print(f"\n  更新完成! 共更新 {total_updated} chunks")


def update_all_documents():
    """更新向量库中的所有文件"""
    vector_docs = get_vector_documents()
    if not vector_docs:
        print("  向量库为空")
        return
    local_file_docs = {k: v for k, v in vector_docs.items() if v.get("source_type") == "local_file"}
    if not local_file_docs:
        print("  没有本地文件类型的向量记录")
        return
    print(f"  找到 {len(local_file_docs)} 个本地文件类型的向量记录")
    update_documents(list(local_file_docs.keys()))


def sync_documents():
    """自动同步本地文件和向量库"""
    print(f"\n  同步本地文件和向量库...")
    local_docs = set(get_local_documents())
    vector_docs = get_vector_documents()
    local_file_vector_docs = {k: v for k, v in vector_docs.items() if v.get("source_type") == "local_file"}
    local_file_sources = set(local_file_vector_docs.keys())
    new_docs = local_docs - local_file_sources
    deleted_docs = local_file_sources - local_docs
    print(f"\n  同步预览:")
    print(f"  {'-'*40}")
    print(f"  新增: {len(new_docs)} 个文档")
    print(f"  已删除本地文件: {len(deleted_docs)} 个文档")
    print(f"  {'-'*40}")
    if not new_docs and not deleted_docs:
        print(f"  无变化，跳过同步")
        return
    confirm = input(f"\n  确认执行同步？(y/N): ").strip().lower()
    if confirm != 'y':
        print(f"  取消同步")
        return
    if new_docs:
        add_documents(list(new_docs))
    if deleted_docs:
        print(f"\n  注意：以下本地文件已删除，但向量记录将保留：")
        for doc in deleted_docs:
            print(f"    - {Path(doc).name}")
        print(f"  如需清理这些孤立记录，请使用'清理孤立记录'功能")
    print(f"\n  同步完成!")


def rebuild_database():
    """全量重建向量库"""
    print(f"\n  全量重建向量库...")
    confirm = input(f"  [!] 警告：这将清空向量库并重新添加所有本地文档！确认？(y/N): ").strip().lower()
    if confirm != 'y':
        print(f"  取消重建")
        return
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
    except Exception as e:
        print(f"  无法连接 ChromaDB: {e}")
        return
    collection_name = get_active_collection_name()
    try:
        client.delete_collection(collection_name)
        print(f"  [OK] 删除旧集合: {collection_name}")
    except Exception:
        pass
    add_all_documents()
    print(f"\n  全量重建完成!")


def add_web_content():
    """添加网页内容到向量库"""
    print(f"\n  添加网页内容到向量库...")
    url = input("  请输入网页 URL: ").strip()
    if not url:
        print("  URL 不能为空")
        return
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
    except Exception as e:
        print(f"  无法连接 ChromaDB: {e}")
        return
    try:
        emb_proxy = get_scheduler()
    except Exception as e:
        print(f"  无法连接 Embedding 服务: {e}")
        return
    collection_name = get_active_collection_name()
    try:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
        )
    except Exception as e:
        print(f"  无法创建集合: {e}")
        return
    repo = DocumentRepository(collection, emb_proxy)
    try:
        import requests
        from bs4 import BeautifulSoup
        print(f"  正在爬取网页内容...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string if soup.title else url
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        if not text:
            print(f"  网页内容为空")
            return
        doc = {
            "path": url,
            "text": f"[网页标题: {title}]\n[来源: {url}]\n{text}",
            "title": title,
        }
        chunk_cfg = get_chunk_config()
        count = repo.add(doc, chunk_cfg, source_type="web_crawl")
        print(f"  [OK] 添加成功: {url} ({count} chunks)")
        web_dir = ROOT / "data" / "web"
        web_dir.mkdir(parents=True, exist_ok=True)
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        file_path = web_dir / f"{url_hash}.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"URL: {url}\n")
            f.write(f"标题: {title}\n")
            f.write(f"爬取时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"\n{'='*60}\n\n")
            f.write(text)
        print(f"  已保存到本地: {file_path}")
    except ImportError:
        print(f"  缺少依赖库，请运行: uv pip install requests beautifulsoup4")
    except Exception as e:
        print(f"  爬取网页失败: {e}")


def start_services():
    """启动所有服务"""
    print("\n  启动所有服务...")
    subprocess.run([sys.executable, "start_all.py"], cwd=ROOT)


def check_orphan_on_startup():
    """启动时检查孤立记录"""
    try:
        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()
        collection_name = get_active_collection_name()
        collection = client.get_collection(name=collection_name)
        emb_proxy = get_scheduler()
        repo = DocumentRepository(collection, emb_proxy)
        orphans = repo.check_orphan_records(str(ROOT / "data" / "docs"))
        if orphans:
            print(f"\n  [!] 检测到 {len(orphans)} 个孤立记录（本地文件已删除）")
            print(f"  使用 'python db_manage.py clean' 命令清理")
    except Exception:
        pass


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description="Ezy-RAG 数据库管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    subparsers.add_parser("list", help="显示文档映射表")
    subparsers.add_parser("status", help="显示数据库状态")
    add_parser = subparsers.add_parser("add", help="添加文档到向量库")
    add_parser.add_argument("files", nargs="*", help="文件路径")
    add_parser.add_argument("--all", action="store_true", help="添加所有本地文档")
    add_parser.add_argument("--web", action="store_true", help="添加网页内容")
    delete_parser = subparsers.add_parser("delete", help="删除向量记录（保留本地文件）")
    delete_parser.add_argument("files", nargs="*", help="文件路径")
    delete_parser.add_argument("--all", action="store_true", help="删除所有向量记录")
    delete_local_parser = subparsers.add_parser("delete-local", help="删除本地文件（保留向量记录）")
    delete_local_parser.add_argument("files", nargs="*", help="文件路径")
    subparsers.add_parser("clean", help="清理孤立向量记录")
    update_parser = subparsers.add_parser("update", help="更新向量库中的文档")
    update_parser.add_argument("files", nargs="*", help="文件路径")
    update_parser.add_argument("--all", action="store_true", help="更新所有向量库文档")
    subparsers.add_parser("sync", help="同步本地文件和向量库")
    subparsers.add_parser("rebuild", help="全量重建向量库")
    subparsers.add_parser("start", help="启动所有服务")
    args = parser.parse_args()
    check_orphan_on_startup()
    if args.command == "list":
        list_documents()
    elif args.command == "status":
        show_status()
    elif args.command == "add":
        if args.web:
            add_web_content()
        elif args.all:
            add_all_documents()
        elif args.files:
            add_documents(args.files)
        else:
            print("  请指定文件路径或使用 --all/--web 参数")
    elif args.command == "delete":
        if args.all:
            delete_all_vector_records()
        elif args.files:
            delete_vector_records(args.files)
        else:
            print("  请指定文件路径或使用 --all 参数")
    elif args.command == "delete-local":
        if args.files:
            delete_local_files(args.files)
        else:
            print("  请指定文件路径")
    elif args.command == "clean":
        clean_orphan_records()
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
        while True:
            print("\n" + "=" * 60)
            print("  Ezy-RAG V0.0.17 - 数据库管理")
            print("=" * 60)
            print("1. 查看文档映射表")
            print("2. 查看数据库状态")
            print("3. 添加文档")
            print("4. 删除向量记录（保留本地文件）")
            print("5. 删除本地文件（保留向量记录）")
            print("6. 清理孤立向量记录")
            print("7. 更新文档")
            print("8. 同步本地文件和向量库")
            print("9. 全量重建向量库")
            print("10. 添加网页内容")
            print("11. 启动服务")
            print("12. 退出")
            choice = input("\n请选择 (1-12): ").strip()
            if choice == "1":
                list_documents()
            elif choice == "2":
                show_status()
            elif choice == "3":
                print("\n添加文档:")
                print("1. 添加指定文件")
                print("2. 添加所有本地文档")
                print("3. 添加网页内容")
                print("4. 返回")
                sub_choice = input("\n请选择 (1-4): ").strip()
                if sub_choice == "1":
                    files = input("请输入文件路径（多个文件用空格分隔）: ").strip().split()
                    if files:
                        add_documents(files)
                elif sub_choice == "2":
                    add_all_documents()
                elif sub_choice == "3":
                    add_web_content()
                elif sub_choice == "4":
                    continue
                else:
                    print("无效的选择")
            elif choice == "4":
                print("\n删除向量记录（保留本地文件）:")
                print("1. 删除指定文件的向量记录")
                print("2. 删除所有向量记录")
                print("3. 返回")
                sub_choice = input("\n请选择 (1-3): ").strip()
                if sub_choice == "1":
                    files = input("请输入文件路径（多个文件用空格分隔）: ").strip().split()
                    if files:
                        delete_vector_records(files)
                elif sub_choice == "2":
                    delete_all_vector_records()
                elif sub_choice == "3":
                    continue
                else:
                    print("无效的选择")
            elif choice == "5":
                print("\n删除本地文件（保留向量记录）:")
                print("1. 删除指定本地文件")
                print("2. 返回")
                sub_choice = input("\n请选择 (1-2): ").strip()
                if sub_choice == "1":
                    files = input("请输入文件路径（多个文件用空格分隔）: ").strip().split()
                    if files:
                        delete_local_files(files)
                elif sub_choice == "2":
                    continue
                else:
                    print("无效的选择")
            elif choice == "6":
                clean_orphan_records()
            elif choice == "7":
                print("\n更新文档:")
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
            elif choice == "8":
                sync_documents()
            elif choice == "9":
                rebuild_database()
            elif choice == "10":
                add_web_content()
            elif choice == "11":
                start_services()
            elif choice == "12":
                break
            else:
                print("无效的选择")


if __name__ == "__main__":
    main()
