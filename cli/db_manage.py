# -*- coding: utf-8 -*-
"""
Ezy-RAG — 文档管理
参考前端设计的简洁文档管理界面"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli.ui import (
    header, info_card, table, menu, confirm, 
    log_ok, log_error, log_info, log_warn, log_step, progress_bar,
    select_data_source
)
from cli.cli_core import (
    connect_chroma, get_local_documents, get_database_stats, 
    get_document_list, reload_env
)


def get_optimal_workers() -> int:
    """根据硬件条件自动检测最优并发数
    
    文件读取是 I/O 密集型，可以使用比 CPU 核心数更多的线程
    """
    cpu_count = os.cpu_count() or 4
    # 经验公式：CPU 核心数 * 2，但不超过 16
    optimal = min(cpu_count * 2, 16)
    return max(2, optimal)


def read_files_parallel(paths: list, max_workers: int = None) -> tuple:
    """多线程并行读取文件
    
    Args:
        paths: 文件路径列表
        max_workers: 并发线程数，None 则自动检测
        
    Returns:
        (documents, errors) - 文档列表和错误列表
    """
    from core.document import read_file
    
    if max_workers is None:
        max_workers = get_optimal_workers()
    
    documents = []
    errors = []
    
    def read_single_file(path):
        try:
            text = read_file(path)
            if text.strip():
                doc_name = Path(path).stem
                text = f"[文件名: {doc_name}]\n{text}"
                return {"type": "success", "path": path, "text": text}
            return None
        except Exception as e:
            return {"type": "error", "path": path, "message": str(e)}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(read_single_file, p): p for p in paths}
        for future in as_completed(futures):
            result = future.result()
            if result:
                if result["type"] == "error":
                    errors.append(result)
                else:
                    documents.append({"path": result["path"], "text": result["text"]})
    
    return documents, errors


def find_doc_in_docs(filename: str) -> str | None:
    """在 docs 目录中查找文档，返回完整路径"""
    docs_dir = ROOT / "data" / "docs"
    if not docs_dir.exists():
        return None
    
    # 精确匹配
    for f in docs_dir.rglob("*"):
        if f.is_file() and f.name == filename:
            return str(f)
    
    # 模糊匹配（包含关键词）
    matches = []
    for f in docs_dir.rglob("*"):
        if f.is_file() and filename.lower() in f.name.lower():
            matches.append(str(f))
    
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        log_info(f"找到多个匹配: {[Path(m).name for m in matches]}")
        return matches[0]
    
    return None


def show_document_list(source: str = "all"):
    """显示文档列表"""
    docs = get_document_list(source)
    
    if not docs:
        log_info("没有找到文档")
        return
    
    # 准备表格数据
    headers = ["文件名", "来源", "状态", "Chunks"]
    rows = []
    for doc in docs:
        source_text = {"docs": "本地", "web": "网页"}.get(doc.get("source", ""), "未知")
        status_text = {
            "imported": "已导入",
            "local": "未导入",
            "orphan": "孤立"
        }.get(doc["status"], doc["status"])
        
        chunks_text = str(doc["chunks"]) if doc["chunks"] > 0 else "-"
        rows.append([doc["name"], source_text, status_text, chunks_text])
    
    # 显示统计
    stats = get_database_stats()
    info_card("文档统计", {
        "本地文档": f"{stats['docs_count']} 个",
        "网页数据": f"{stats['web_count']} 个",
        "已导入": f"{stats['vector_docs']} 个",
        "向量块": f"{stats['chunks']} 个",
    })
    
    # 显示表格
    table(headers, rows)


def add_document():
    """添加单个文档"""
    from core.document import read_file
    from config.settings import get_chunk_config
    
    filename = input("\n  请输入文档名称: ").strip()
    if not filename:
        log_info("已取消")
        return
    
    # 查找文档
    doc_path = find_doc_in_docs(filename)
    if not doc_path:
        log_error(f"未找到文档: {filename}")
        return
    
    log_step(f"添加文档: {Path(doc_path).name}")
    
    try:
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        text = read_file(doc_path)
        if not text or not text.strip():
            log_error("文档内容为空")
            return
        
        doc_name = Path(doc_path).stem
        text = f"[文件名: {doc_name}]\n{text}"
        doc = {"path": doc_path, "text": text}
        
        count = db.add(doc, chunk_cfg, source_type="local_file")
        log_ok(f"添加成功: {Path(doc_path).name} ({count} chunks)")
        
    except Exception as e:
        log_error(f"添加失败: {e}")


def add_documents_batch():
    """批量添加文档"""
    from core.document import read_file
    from config.settings import get_chunk_config
    
    print("\n  请输入文档名称（多个用空格或逗号分隔）:")
    input_str = input("  > ").strip()
    if not input_str:
        log_info("已取消")
        return
    
    # 解析文件名列表
    names = []
    for sep in [",", " ", "\t"]:
        names = [n.strip() for n in input_str.split(sep) if n.strip()]
        if names:
            break
    
    if not names:
        log_info("未输入有效的文档名称")
        return
    
    log_step(f"批量添加 {len(names)} 个文档")
    
    try:
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        success = 0
        failed = 0
        total_chunks = 0
        
        for i, name in enumerate(names, 1):
            doc_path = find_doc_in_docs(name)
            if not doc_path:
                log_error(f"[{i}/{len(names)}] 未找到: {name}")
                failed += 1
                continue
            
            try:
                text = read_file(doc_path)
                if not text or not text.strip():
                    log_info(f"[{i}/{len(names)}] 跳过空文件: {Path(doc_path).name}")
                    continue
                
                doc_name = Path(doc_path).stem
                text = f"[文件名: {doc_name}]\n{text}"
                doc = {"path": doc_path, "text": text}
                
                count = db.add(doc, chunk_cfg, source_type="local_file")
                total_chunks += count
                success += 1
                log_ok(f"[{i}/{len(names)}] {Path(doc_path).name} ({count} chunks)")
            except Exception as e:
                log_error(f"[{i}/{len(names)}] 失败: {Path(doc_path).name} - {e}")
                failed += 1
        
        print()
        log_ok(f"批量添加完成: {success} 成功, {failed} 失败, 共 {total_chunks} chunks")
        
    except Exception as e:
        log_error(f"连接数据库失败: {e}")


def delete_document():
    """删除单个文档的向量记录"""
    filename = input("\n  请输入文档名称: ").strip()
    if not filename:
        log_info("已取消")
        return
    
    try:
        _, db = connect_chroma()
        
        # 查找匹配的向量记录
        docs = db.list_documents()
        matches = [d for d in docs if filename.lower() in d["source_name"].lower()]
        
        if not matches:
            log_error(f"未找到匹配的向量记录: {filename}")
            return
        
        if len(matches) > 1:
            log_info("找到多个匹配:")
            for d in matches:
                log_info(f"  - {d['source_name']} ({d['chunks']} chunks)")
        
        doc = matches[0]
        log_step(f"删除向量记录: {doc['source_name']}")
        
        if not confirm(f"确定删除 {doc['source_name']} ({doc['chunks']} chunks)?"):
            return
        
        db.delete(doc["source"])
        log_ok(f"删除成功: {doc['source_name']}")
        
    except Exception as e:
        log_error(f"删除失败: {e}")


def delete_documents_batch():
    """批量删除文档的向量记录"""
    print("\n  请输入文档名称（多个用空格或逗号分隔）:")
    input_str = input("  > ").strip()
    if not input_str:
        log_info("已取消")
        return
    
    # 解析文件名列表
    names = []
    for sep in [",", " ", "\t"]:
        names = [n.strip() for n in input_str.split(sep) if n.strip()]
        if names:
            break
    
    if not names:
        log_info("未输入有效的文档名称")
        return
    
    try:
        _, db = connect_chroma()
        docs = db.list_documents()
        
        # 查找所有匹配
        to_delete = []
        for name in names:
            matches = [d for d in docs if name.lower() in d["source_name"].lower()]
            if matches:
                to_delete.extend(matches)
            else:
                log_warn(f"未找到: {name}")
        
        if not to_delete:
            log_info("没有找到匹配的文档")
            return
        
        # 去重
        seen = set()
        unique_delete = []
        for d in to_delete:
            if d["source"] not in seen:
                seen.add(d["source"])
                unique_delete.append(d)
        
        log_step(f"批量删除 {len(unique_delete)} 个文档的向量记录")
        
        # 显示将要删除的文档
        for d in unique_delete:
            log_info(f"  - {d['source_name']} ({d['chunks']} chunks)")
        
        if not confirm("确定删除以上记录?"):
            return
        
        success = 0
        failed = 0
        for d in unique_delete:
            try:
                db.delete(d["source"])
                log_ok(f"已删除: {d['source_name']}")
                success += 1
            except Exception as e:
                log_error(f"删除失败: {d['source_name']} - {e}")
                failed += 1
        
        print()
        log_ok(f"批量删除完成: {success} 成功, {failed} 失败")
        
    except Exception as e:
        log_error(f"连接数据库失败: {e}")


def delete_all_documents():
    """删除所有向量记录"""
    log_step("删除所有向量记录")
    
    try:
        _, db = connect_chroma()
        
        # 获取所有文档
        docs = db.list_documents()
        if not docs:
            log_info("向量库为空")
            return
        
        total_chunks = sum(d["chunks"] for d in docs)
        log_info(f"找到 {len(docs)} 个文档，共 {total_chunks} 个向量块")
        
        # 显示文档列表
        for d in docs[:10]:  # 只显示前10个
            log_info(f"  - {d['source_name']} ({d['chunks']} chunks)")
        if len(docs) > 10:
            log_info(f"  ... 还有 {len(docs) - 10} 个文档")
        
        if not confirm("确定删除所有向量记录？此操作不可恢复", default=False):
            return
        
        # 删除所有文档
        success = 0
        failed = 0
        for i, d in enumerate(docs, 1):
            try:
                db.delete(d["source"])
                success += 1
                progress_bar(i, len(docs), prefix="删除中", suffix=d["source_name"])
            except Exception as e:
                failed += 1
                log_error(f"删除失败: {d['source_name']} - {e}")
        
        print()
        log_ok(f"全部删除完成: {success} 成功, {failed} 失败")
        
    except Exception as e:
        log_error(f"删除失败: {e}")


def crawl_webpage():
    """爬取单个网页"""
    from core.utils import md5_short
    
    url = input("\n  请输入网页 URL: ").strip()
    if not url:
        log_info("已取消")
        return
    
    log_step(f"爬取网页: {url}")
    
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        log_error("缺少依赖，请运行: uv pip install requests beautifulsoup4")
        return
    
    try:
        # 1. 爬取网页
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string if soup.title else url
        
        # 2. 提取纯文本
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        text = " ".join(text.split())
        
        if not text:
            log_error("网页内容为空")
            return
        
        # 3. 保存到 data/web 目录
        web_dir = ROOT / "data" / "web"
        web_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{md5_short(url)}.txt"
        filepath = web_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"[网页标题: {title}]\n")
            f.write(f"[来源: {url}]\n")
            f.write(f"[爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n\n")
            f.write(text)
        
        # 4. 添加到向量库
        from core.document import read_file
        from config.settings import get_chunk_config
        
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        text_content = read_file(str(filepath))
        doc_name = filepath.stem
        doc = {"path": str(filepath), "text": f"[文件名: {doc_name}]\n{text_content}"}
        count = db.add(doc, chunk_cfg, source_type="local_file")
        
        log_ok(f"爬取成功: {filename} ({count} chunks)")
        
    except Exception as e:
        log_error(f"爬取失败: {e}")


def crawl_webpages_batch():
    """批量爬取网页"""
    from core.utils import md5_short
    
    print("\n  请输入网页 URL（多个用空格或逗号分隔）:")
    input_str = input("  > ").strip()
    if not input_str:
        log_info("已取消")
        return
    
    # 解析 URL 列表
    urls = []
    for sep in [",", " ", "\t"]:
        urls = [u.strip() for u in input_str.split(sep) if u.strip()]
        if urls:
            break
    
    if not urls:
        log_info("未输入有效的 URL")
        return
    
    log_step(f"批量爬取 {len(urls)} 个网页")
    
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        log_error("缺少依赖，请运行: uv pip install requests beautifulsoup4")
        return
    
    from core.document import read_file
    from config.settings import get_chunk_config
    
    web_dir = ROOT / "data" / "web"
    web_dir.mkdir(parents=True, exist_ok=True)
    
    _, db = connect_chroma()
    chunk_cfg = get_chunk_config()
    
    success = 0
    failed = 0
    total_chunks = 0
    
    for i, url in enumerate(urls, 1):
        try:
            # 爬取网页
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string if soup.title else url
            
            # 提取纯文本
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            text = " ".join(text.split())
            
            if not text:
                log_info(f"[{i}/{len(urls)}] 跳过空网页: {url}")
                continue
            
            # 保存到本地
            filename = f"{md5_short(url)}.txt"
            filepath = web_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"[网页标题: {title}]\n")
                f.write(f"[来源: {url}]\n")
                f.write(f"[爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n\n")
                f.write(text)
            
            # 添加到向量库
            text_content = read_file(str(filepath))
            doc_name = filepath.stem
            doc = {"path": str(filepath), "text": f"[文件名: {doc_name}]\n{text_content}"}
            count = db.add(doc, chunk_cfg, source_type="local_file")
            
            total_chunks += count
            success += 1
            log_ok(f"[{i}/{len(urls)}] {title} ({count} chunks)")
            
        except Exception as e:
            failed += 1
            log_error(f"[{i}/{len(urls)}] 失败: {url} - {e}")
    
    print()
    log_ok(f"批量爬取完成: {success} 成功, {failed} 失败, 共 {total_chunks} chunks")


def sync_documents(source: str = "all"):
    """同步文档（对比 hash，自动增删改）"""
    from core.document import get_document_paths
    from config.settings import get_chunk_config
    from core.utils import content_hash
    
    log_step("同步文档...")
    
    try:
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        # 根据数据源获取文档路径
        dirs = []
        if source in ("all", "docs"):
            dirs.append(ROOT / "data" / "docs")
        if source in ("all", "web"):
            dirs.append(ROOT / "data" / "web")
        
        paths = get_document_paths(*dirs)
        
        if not paths:
            log_info("没有本地文档")
            return
        
        # 显示文件数量信息
        if source == "all":
            docs_paths = get_document_paths(ROOT / "data" / "docs")
            web_paths = get_document_paths(ROOT / "data" / "web")
            log_info(f"找到 {len(paths)} 个文档 ({len(docs_paths)} docs + {len(web_paths)} web)")
        else:
            log_info(f"找到 {len(paths)} 个文档")
        
        # 计算差异（不读取文件内容）
        current_sources = set(paths)
        stored_sources = db.list_sources()
        new_sources = current_sources - stored_sources
        common_sources = current_sources & stored_sources
        delete_sources = stored_sources - current_sources
        
        # 多线程读取需要处理的文件（带进度条）
        files_to_read = [p for p in paths if p in new_sources or p in common_sources]
        total_to_read = len(files_to_read)
        
        if total_to_read > 0:
            log_info(f"读取 {total_to_read} 个文件...")
            workers = get_optimal_workers()
            log_info(f"使用 {workers} 个线程并行读取")
            
            start_time = time.time()
            documents, errors = read_files_parallel(files_to_read, max_workers=workers)
            read_time = time.time() - start_time
            
            print()  # 换行
            if errors:
                log_warn(f"读取失败: {len(errors)} 个文件")
                for err in errors[:5]:
                    log_error(f"  - {Path(err['path']).name}: {err['message']}")
            
            log_info(f"读取完成: {len(documents)} 个文件, 耗时 {read_time:.1f} 秒")
        else:
            documents = []
        
        log_info(f"需要处理: {len(new_sources)} 新增, {len(common_sources)} 检查更新, {len(delete_sources)} 删除")
        
        # 进度回调
        def on_progress(op, idx, total, name, count):
            if op == "add":
                progress_bar(idx, total, prefix="新增", suffix=f"{name} ({count} chunks)")
            elif op == "update":
                progress_bar(idx, total, prefix="更新", suffix=f"{name} ({count} chunks)")
            elif op == "delete":
                log_info(f"删除: {name}")
        
        # 传递 stored_sources 避免重复查询
        stats = db.sync(documents, chunk_cfg, on_progress=on_progress, stored_sources=stored_sources)
        
        print()  # 换行
        if stats["added"] + stats["updated"] + stats["deleted"] == 0:
            log_info(f"无变化 ({stats['unchanged']} 个文件未变)")
        else:
            log_ok(f"同步完成: 新增 {stats['added']}, 更新 {stats['updated']}, 删除 {stats['deleted']}, 未变 {stats['unchanged']}")
        
    except Exception as e:
        log_error(f"同步失败: {e}")


def rebuild_documents(source: str = "all"):
    """全量重建向量库"""
    from core.document import get_document_paths
    from config.settings import get_chunk_config
    
    if not confirm("确定要全量重建向量库？这将清空现有数据并重新处理所有文档", default=False):
        return
    
    log_step("全量重建向量库...")
    
    try:
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        # 根据数据源获取文件路径
        dirs = []
        if source in ("all", "docs"):
            dirs.append(ROOT / "data" / "docs")
        if source in ("all", "web"):
            dirs.append(ROOT / "data" / "web")
        
        paths = get_document_paths(*dirs)
        
        if not paths:
            log_info("没有本地文档")
            return
        
        # 显示文件数量信息
        if source == "all":
            docs_paths = get_document_paths(ROOT / "data" / "docs")
            web_paths = get_document_paths(ROOT / "data" / "web")
            log_info(f"找到 {len(paths)} 个文档 ({len(docs_paths)} docs + {len(web_paths)} web)")
        else:
            log_info(f"找到 {len(paths)} 个文档")
        
        # 多线程读取文件内容（带进度条）
        log_info("读取文件内容...")
        documents = []
        errors = []
        workers = get_optimal_workers()
        log_info(f"使用 {workers} 个线程并行读取")
        
        start_time = time.time()
        documents, errors = read_files_parallel(paths, max_workers=workers)
        read_time = time.time() - start_time
        
        print()  # 换行
        if errors:
            log_warn(f"读取失败: {len(errors)} 个文件")
            for err in errors[:5]:
                log_error(f"  - {Path(err['path']).name}: {err['message']}")
        
        log_info(f"读取完成: {len(documents)} 个文件, 耗时 {read_time:.1f} 秒")
        
        # 进度回调
        def on_progress(op, idx, total, name, count):
            progress_bar(idx, total, prefix="重建中", suffix=f"{name} ({count} chunks)")
        
        total_chunks = db.rebuild(documents, chunk_cfg, on_progress=on_progress)
        
        print()  # 换行
        log_ok(f"重建完成: {total_chunks} chunks, {len(documents)} 个文档")
        
    except Exception as e:
        log_error(f"重建失败: {e}")


def clean_orphan_records():
    """清理孤立记录"""
    log_step("检查孤立记录...")
    
    try:
        _, db = connect_chroma()
        docs_dir = str(ROOT / "data" / "docs")
        web_dir = str(ROOT / "data" / "web")
        
        orphans = db.check_orphan_records(docs_dir, web_dir)
        
        if not orphans:
            log_info("没有孤立记录")
            return
        
        log_info(f"找到 {len(orphans)} 个孤立记录")
        for doc in orphans:
            log_info(f"  - {doc['source_name']} ({doc['chunks']} chunks)")
        
        if not confirm("确定清理这些孤立记录？"):
            return
        
        count = 0
        for doc in orphans:
            try:
                db.delete(doc["source"])
                count += 1
            except Exception:
                pass
        log_ok(f"清理完成: {count} 个孤立记录")
        
    except Exception as e:
        log_error(f"清理失败: {e}")


def main():
    """主函数"""
    while True:
        header("Ezy-RAG 文档管理")
        
        # 显示统计
        stats = get_database_stats()
        info_card("文档统计", {
            "本地文档": f"{stats['docs_count']} 个",
            "网页数据": f"{stats['web_count']} 个",
            "已导入": f"{stats['vector_docs']} 个",
            "向量块": f"{stats['chunks']} 个",
        })
        
        # 菜单
        choice = menu("操作", [
            "查看文档列表",
            "添加文档",
            "批量添加",
            "删除文档",
            "批量删除",
            "全部删除",
            "网页爬取",
            "同步文档",
            "全量重建",
            "清理孤立",
            "返回"
        ])
        
        if choice == 1:
            source = select_data_source("选择查看范围")
            show_document_list(source)
        elif choice == 2:
            add_document()
        elif choice == 3:
            add_documents_batch()
        elif choice == 4:
            delete_document()
        elif choice == 5:
            delete_documents_batch()
        elif choice == 6:
            delete_all_documents()
        elif choice == 7:
            # 网页爬取子菜单
            sub_choice = menu("网页爬取", [
                "爬取单个网页",
                "批量爬取网页",
                "返回"
            ])
            if sub_choice == 1:
                crawl_webpage()
            elif sub_choice == 2:
                crawl_webpages_batch()
        elif choice == 8:
            source = select_data_source("选择同步范围")
            sync_documents(source)
        elif choice == 9:
            source = select_data_source("选择重建范围")
            rebuild_documents(source)
        elif choice == 10:
            clean_orphan_records()
        elif choice == 11:
            break
        
        if choice != 11:
            from cli.ui import pause
            pause()


if __name__ == "__main__":
    main()
