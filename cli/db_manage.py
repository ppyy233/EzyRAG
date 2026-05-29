# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.18 — 数据库管理工具
用法: python cli/db_manage.py [command]

命令：
  list              显示文档映射表
  status            显示数据库状态
  add [--all]       添加文档
  delete [--all]    删除向量记录
  update [--all]    更新文档
  sync              同步本地和向量库
  rebuild           全量重建
  clean             清理孤立记录
"""
import sys
import os
import argparse
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

import chromadb
from config.settings import get_chunk_config, get_collection_name
from config.pointer import get_active_collection, set_active_collection
from core.api import EmbeddingAPI
from core.database import DocumentDatabase, read_file, load_all_documents, SUPPORTED_EXT, validate_hnsw, cleanup_empty_chroma_dirs, cleanup_orphan_shadows


# ============================================================
#  连接辅助
# ============================================================

def connect_chroma():
    """统一的 ChromaDB 连接，返回 (client, db)"""
    host = os.getenv("CHROMA_SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("CHROMA_SERVER_PORT", "9898"))

    try:
        client = chromadb.HttpClient(host=host, port=port)
        client.heartbeat()
    except Exception as e:
        raise ConnectionError(f"无法连接 ChromaDB ({host}:{port}): {e or '连接被拒绝'}")

    try:
        emb_api = EmbeddingAPI()
    except Exception as e:
        raise ConnectionError(f"Embedding 服务初始化失败: {e or '请检查 .env 配置'}")

    # 启动清理
    cleanup_empty_chroma_dirs()
    cleanup_orphan_shadows(client, get_collection_name())

    collection_name = get_active_collection(get_collection_name())

    try:
        collection = client.get_collection(name=collection_name)
        # 验证 HNSW 完整性
        ok, detail = validate_hnsw(collection)
        if not ok:
            print(f"  [!] 集合 {collection_name} {detail}，自动重建...")
            client.delete_collection(collection_name)
            collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
            )
    except Exception:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "hnsw:sync_threshold": 100},
        )
        set_active_collection(get_collection_name(), collection_name)

    db = DocumentDatabase(collection, emb_api, client, collection_name)
    return client, db


def get_local_documents() -> list:
    """获取本地文档列表"""
    docs_dir = ROOT / "data" / "docs"
    if not docs_dir.exists():
        return []
    documents = []
    seen = set()
    for ext in SUPPORTED_EXT:
        for f in docs_dir.glob(f"**/*{ext}"):
            if f.is_file():
                key = str(f.resolve())
                if key not in seen:
                    seen.add(key)
                    documents.append(str(f))
    return sorted(documents)


# ============================================================
#  命令实现
# ============================================================

def show_status():
    """显示数据库状态"""
    print("\n" + "=" * 60)
    print("  数据库状态")
    print("=" * 60)
    try:
        _, db = connect_chroma()
        print(f"  集合: {db.collection_name}")
        print(f"  总记录数: {db.count()}")
        orphans = db.check_orphan_records(str(ROOT / "data" / "docs"))
        if orphans:
            print(f"  [!] 孤立记录: {len(orphans)} 个")
            for doc in orphans:
                print(f"      - {doc['source_name']}")
    except Exception as e:
        print(f"  连接失败: {e}")


def list_documents():
    """显示文档映射表"""
    print("\n" + "=" * 60)
    print("  文档映射表")
    print("=" * 60)
    try:
        _, db = connect_chroma()
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    local_docs = get_local_documents()
    vector_docs = {d["source"]: d for d in db.list_documents()}
    local_file_docs = {k: v for k, v in vector_docs.items() if v.get("source_type") == "local_file"}

    print(f"\n  本地文件映射:")
    print(f"  {'文件名':<40} {'状态':<10} {'chunks':<8}")
    print(f"  {'-'*60}")
    for doc in local_docs:
        doc_name = Path(doc).name
        if doc in local_file_docs:
            chunks = local_file_docs[doc]["chunks"]
            print(f"  {doc_name:<40} {'已添加':<10} {chunks:<8}")
        else:
            print(f"  {doc_name:<40} {'未添加':<10} {'-':<8}")

    orphans = [doc for doc in local_file_docs.values() if not Path(doc["source"]).exists()]
    if orphans:
        print(f"\n  孤立记录（本地文件已删除）:")
        for doc in orphans:
            print(f"  {doc['source_name']:<40} {doc['chunks']:<8}")

    web_docs = {k: v for k, v in vector_docs.items() if v.get("source_type") == "web_crawl"}
    if web_docs:
        print(f"\n  网页数据:")
        for doc in web_docs.values():
            url = doc["source"][:50] + "..." if len(doc["source"]) > 53 else doc["source"]
            print(f"  {url:<55} {doc['chunks']:<8}")

    total_chunks = sum(d["chunks"] for d in vector_docs.values())
    print(f"\n  本地: {len(local_docs)} 个  向量库: {len(vector_docs)} 个  chunks: {total_chunks}")


def add_documents(file_paths: list):
    """添加指定文件"""
    print(f"\n  添加文档到向量库...")
    try:
        _, db = connect_chroma()
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    chunk_cfg = get_chunk_config()
    total = 0
    for file_path in file_paths:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"  [FAIL] 文件不存在: {file_path}")
            continue
        ext = full_path.suffix.lower()
        if ext not in SUPPORTED_EXT:
            print(f"  [SKIP] 不支持的格式: {file_path}")
            continue
        try:
            text = read_file(str(full_path))
            if not text or not text.strip():
                print(f"  [SKIP] 内容为空: {file_path}")
                continue
            doc_name = full_path.stem
            text = f"[文件名: {doc_name}]\n{text}"
            doc = {"path": str(full_path), "text": text}
            count = db.add(doc, chunk_cfg, source_type="local_file")
            total += count
            print(f"  [OK] {full_path.name} ({count} chunks)")
        except Exception as e:
            print(f"  [FAIL] {full_path.name}: {e}")

    print(f"\n  添加完成! 共 {total} chunks")


def add_all_documents():
    """添加所有本地文档"""
    local_docs = get_local_documents()
    if not local_docs:
        print("  没有找到本地文档")
        return
    print(f"  找到 {len(local_docs)} 个本地文档")
    add_documents(local_docs)


def delete_vector_records(file_paths: list):
    """删除向量记录"""
    print(f"\n  删除向量记录...")
    try:
        _, db = connect_chroma()
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    total = 0
    for file_path in file_paths:
        try:
            db.delete(file_path)
            total += 1
            print(f"  [OK] {file_path}")
        except Exception as e:
            print(f"  [FAIL] {file_path}: {e}")
    print(f"\n  删除完成! 共 {total} 个")


def delete_all_vector_records():
    """删除所有向量记录"""
    try:
        _, db = connect_chroma()
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    vector_docs = db.list_documents()
    if not vector_docs:
        print("  向量库为空")
        return
    print(f"  找到 {len(vector_docs)} 个文档")
    confirm = input("  确认删除所有向量记录？(y/N): ").strip().lower()
    if confirm != "y":
        print("  取消")
        return
    delete_vector_records([d["source"] for d in vector_docs])


def update_documents(file_paths: list):
    """更新向量库中的文档"""
    print(f"\n  更新向量库文档...")
    try:
        _, db = connect_chroma()
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    chunk_cfg = get_chunk_config()
    total = 0
    for file_path in file_paths:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"  [FAIL] 文件不存在: {file_path}")
            continue
        try:
            text = read_file(str(full_path))
            if not text or not text.strip():
                print(f"  [SKIP] 内容为空: {file_path}")
                continue
            doc_name = full_path.stem
            text = f"[文件名: {doc_name}]\n{text}"
            doc = {"path": str(full_path), "text": text}
            count = db.update(doc, chunk_cfg, source_type="local_file")
            total += count
            print(f"  [OK] {full_path.name} ({count} chunks)")
        except Exception as e:
            print(f"  [FAIL] {full_path.name}: {e}")

    print(f"\n  更新完成! 共 {total} chunks")


def update_all_documents():
    """更新所有向量库文档"""
    try:
        _, db = connect_chroma()
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    local_file_docs = [d for d in db.list_documents() if d.get("source_type") == "local_file"]
    if not local_file_docs:
        print("  没有本地文件类型的向量记录")
        return
    print(f"  找到 {len(local_file_docs)} 个文档")
    update_documents([d["source"] for d in local_file_docs])


def sync_documents():
    """同步本地文件和向量库"""
    print(f"\n  同步本地文件和向量库...")
    try:
        _, db = connect_chroma()
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    chunk_cfg = get_chunk_config()
    docs_dir = ROOT / "data" / "docs"

    print(f"  加载本地文档...")
    documents = load_all_documents(docs_dir)
    if not documents:
        print("  没有本地文档")
        return

    stats = db.sync(documents, chunk_cfg)
    total_ops = stats["added"] + stats["updated"] + stats["deleted"]
    if total_ops == 0:
        print(f"\n  无变化（{stats['unchanged']} 个文件未变）")
    else:
        print(f"\n  新增: {stats['added']}  更新: {stats['updated']}  "
              f"未变: {stats['unchanged']}  删除: {stats['deleted']}")
    print(f"  同步完成! 当前 {db.count()} 条记录")


def rebuild_database():
    """全量重建向量库"""
    print(f"\n  全量重建向量库...")
    confirm = input("  [!] 警告：这将清空向量库并重新添加所有文档！确认？(y/N): ").strip().lower()
    if confirm != "y":
        print("  取消重建")
        return

    try:
        _, db = connect_chroma()
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    chunk_cfg = get_chunk_config()
    docs_dir = ROOT / "data" / "docs"

    print(f"  加载本地文档...")
    documents = load_all_documents(docs_dir)
    if not documents:
        print("  没有文档")
        return

    count = db.rebuild(documents, chunk_cfg)
    print(f"\n  重建完成! {count} chunks")


def clean_orphan_records():
    """清理孤立记录"""
    print(f"\n  清理孤立记录...")
    try:
        _, db = connect_chroma()
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    orphans = db.check_orphan_records(str(ROOT / "data" / "docs"))
    if not orphans:
        print("  没有孤立记录")
        return

    print(f"  找到 {len(orphans)} 个孤立记录:")
    for doc in orphans:
        print(f"    {doc['source_name']:<30} {doc['chunks']} chunks")

    confirm = input("\n  确认清理？(y/N): ").strip().lower()
    if confirm != "y":
        print("  取消")
        return

    count = db.clean_orphan_records(str(ROOT / "data" / "docs"))
    print(f"  清理完成! 共清理 {count} 个")


def delete_local_files(file_paths: list):
    """删除本地文件"""
    print(f"\n  删除本地文件...")
    total = 0
    for file_path in file_paths:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"  [SKIP] 不存在: {file_path}")
            continue
        try:
            full_path.unlink()
            total += 1
            print(f"  [OK] {file_path}")
        except Exception as e:
            print(f"  [FAIL] {file_path}: {e}")
    print(f"\n  删除完成! 共 {total} 个")


def add_web_content():
    """添加网页内容"""
    print(f"\n  添加网页内容到向量库...")
    url = input("  请输入网页 URL: ").strip()
    if not url:
        print("  URL 不能为空")
        return

    try:
        _, db = connect_chroma()
    except Exception as e:
        print(f"  连接失败: {e}")
        return

    try:
        import requests
        from bs4 import BeautifulSoup
        print(f"  正在爬取...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string if soup.title else url
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = " ".join(chunk for chunk in chunks if chunk)
        if not text:
            print(f"  网页内容为空")
            return
        doc = {
            "path": url,
            "text": f"[网页标题: {title}]\n[来源: {url}]\n{text}",
            "title": title,
        }
        chunk_cfg = get_chunk_config()
        count = db.add(doc, chunk_cfg, source_type="web_crawl")
        print(f"  [OK] {url} ({count} chunks)")
    except ImportError:
        print(f"  缺少依赖，请运行: uv pip install requests beautifulsoup4")
    except Exception as e:
        print(f"  失败: {e}")


def start_services():
    """启动所有服务"""
    import subprocess
    print("\n  启动所有服务...")
    subprocess.run([sys.executable, "start_all.py"], cwd=ROOT)


# ============================================================
#  主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Ezy-RAG V0.0.18 数据库管理工具")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="显示文档映射表")
    subparsers.add_parser("status", help="显示数据库状态")

    add_p = subparsers.add_parser("add", help="添加文档")
    add_p.add_argument("files", nargs="*")
    add_p.add_argument("--all", action="store_true")
    add_p.add_argument("--web", action="store_true")

    del_p = subparsers.add_parser("delete", help="删除向量记录")
    del_p.add_argument("files", nargs="*")
    del_p.add_argument("--all", action="store_true")

    del_local_p = subparsers.add_parser("delete-local", help="删除本地文件")
    del_local_p.add_argument("files", nargs="*")

    subparsers.add_parser("clean", help="清理孤立记录")

    upd_p = subparsers.add_parser("update", help="更新文档")
    upd_p.add_argument("files", nargs="*")
    upd_p.add_argument("--all", action="store_true")

    subparsers.add_parser("sync", help="同步本地和向量库")
    subparsers.add_parser("rebuild", help="全量重建")
    subparsers.add_parser("start", help="启动服务")

    args = parser.parse_args()

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
            print("  请指定文件路径或使用 --all/--web")
    elif args.command == "delete":
        if args.all:
            delete_all_vector_records()
        elif args.files:
            delete_vector_records(args.files)
        else:
            print("  请指定文件路径或使用 --all")
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
            print("  请指定文件路径或使用 --all")
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
            print("  Ezy-RAG V0.0.18 — 数据库管理")
            print("=" * 60)
            print("  1. 查看文档映射表")
            print("  2. 查看数据库状态")
            print("  3. 添加文档")
            print("  4. 删除向量记录")
            print("  5. 删除本地文件")
            print("  6. 清理孤立记录")
            print("  7. 更新文档")
            print("  8. 同步本地和向量库")
            print("  9. 全量重建")
            print("  10. 添加网页内容")
            print("  11. 启动服务")
            print("  12. 退出")
            choice = input("\n请选择 (1-12): ").strip()
            if choice == "1":
                list_documents()
            elif choice == "2":
                show_status()
            elif choice == "3":
                print("\n  1. 指定文件  2. 所有本地文档  3. 网页内容  4. 返回")
                sub = input("  请选择: ").strip()
                if sub == "1":
                    files = input("  文件路径（空格分隔）: ").strip().split()
                    if files:
                        add_documents(files)
                elif sub == "2":
                    add_all_documents()
                elif sub == "3":
                    add_web_content()
            elif choice == "4":
                print("\n  1. 指定文件  2. 所有记录  3. 返回")
                sub = input("  请选择: ").strip()
                if sub == "1":
                    files = input("  文件路径（空格分隔）: ").strip().split()
                    if files:
                        delete_vector_records(files)
                elif sub == "2":
                    delete_all_vector_records()
            elif choice == "5":
                files = input("  文件路径（空格分隔）: ").strip().split()
                if files:
                    delete_local_files(files)
            elif choice == "6":
                clean_orphan_records()
            elif choice == "7":
                print("\n  1. 指定文件  2. 所有记录  3. 返回")
                sub = input("  请选择: ").strip()
                if sub == "1":
                    files = input("  文件路径（空格分隔）: ").strip().split()
                    if files:
                        update_documents(files)
                elif sub == "2":
                    update_all_documents()
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
                print("  无效的选择")


if __name__ == "__main__":
    main()
