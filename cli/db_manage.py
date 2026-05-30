# -*- coding: utf-8 -*-
"""
Ezy-RAG 鈥?鏂囨。绠＄悊
鍙傝€冨墠绔璁＄殑绠€娲佹枃妗ｇ鐞嗙晫闈?"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime

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


def find_doc_in_docs(filename: str) -> str | None:
    """鍦?docs 鐩綍涓煡鎵炬枃妗ｏ紝杩斿洖瀹屾暣璺緞"""
    docs_dir = ROOT / "data" / "docs"
    if not docs_dir.exists():
        return None
    
    # 绮剧‘鍖归厤
    for f in docs_dir.rglob("*"):
        if f.is_file() and f.name == filename:
            return str(f)
    
    # 妯＄硦鍖归厤锛堝寘鍚叧閿瘝锛?    matches = []
    for f in docs_dir.rglob("*"):
        if f.is_file() and filename.lower() in f.name.lower():
            matches.append(str(f))
    
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        log_info(f"鎵惧埌澶氫釜鍖归厤: {[Path(m).name for m in matches]}")
        return matches[0]
    
    return None


def show_document_list(source: str = "all"):
    """鏄剧ず鏂囨。鍒楄〃"""
    docs = get_document_list(source)
    
    if not docs:
        log_info("娌℃湁鎵惧埌鏂囨。")
        return
    
    # 鍑嗗琛ㄦ牸鏁版嵁
    headers = ["鏂囦欢鍚?, "鏉ユ簮", "鐘舵€?, "Chunks"]
    rows = []
    for doc in docs:
        source_text = {"docs": "鏈湴", "web": "缃戦〉"}.get(doc.get("source", ""), "鏈煡")
        status_text = {
            "imported": "宸插鍏?,
            "local": "鏈鍏?,
            "orphan": "瀛ょ珛"
        }.get(doc["status"], doc["status"])
        
        chunks_text = str(doc["chunks"]) if doc["chunks"] > 0 else "-"
        rows.append([doc["name"], source_text, status_text, chunks_text])
    
    # 鏄剧ず缁熻
    stats = get_database_stats()
    info_card("鏂囨。缁熻", {
        "鏈湴鏂囨。": f"{stats['docs_count']} 涓?,
        "缃戦〉鏁版嵁": f"{stats['web_count']} 涓?,
        "宸插鍏?: f"{stats['vector_docs']} 涓?,
        "鍚戦噺鍧?: f"{stats['chunks']} 涓?,
    })
    
    # 鏄剧ず琛ㄦ牸
    table(headers, rows)


def add_document():
    """娣诲姞鍗曚釜鏂囨。"""
    from core.document import read_file
    from config.settings import get_chunk_config
    
    filename = input("\n  璇疯緭鍏ユ枃妗ｅ悕绉? ").strip()
    if not filename:
        log_info("宸插彇娑?)
        return
    
    # 鏌ユ壘鏂囨。
    doc_path = find_doc_in_docs(filename)
    if not doc_path:
        log_error(f"鏈壘鍒版枃妗? {filename}")
        return
    
    log_step(f"娣诲姞鏂囨。: {Path(doc_path).name}")
    
    try:
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        text = read_file(doc_path)
        if not text or not text.strip():
            log_error("鏂囨。鍐呭涓虹┖")
            return
        
        doc_name = Path(doc_path).stem
        text = f"[鏂囦欢鍚? {doc_name}]\n{text}"
        doc = {"path": doc_path, "text": text}
        
        count = db.add(doc, chunk_cfg, source_type="local_file")
        log_ok(f"娣诲姞鎴愬姛: {Path(doc_path).name} ({count} chunks)")
        
    except Exception as e:
        log_error(f"娣诲姞澶辫触: {e}")


def add_documents_batch():
    """鎵归噺娣诲姞鏂囨。"""
    from core.document import read_file
    from config.settings import get_chunk_config
    
    print("\n  璇疯緭鍏ユ枃妗ｅ悕绉帮紙澶氫釜鐢ㄧ┖鏍兼垨閫楀彿鍒嗛殧锛?")
    input_str = input("  > ").strip()
    if not input_str:
        log_info("宸插彇娑?)
        return
    
    # 瑙ｆ瀽鏂囦欢鍚嶅垪琛?    names = []
    for sep in [",", " ", "\t"]:
        names = [n.strip() for n in input_str.split(sep) if n.strip()]
        if names:
            break
    
    if not names:
        log_info("鏈緭鍏ユ湁鏁堢殑鏂囨。鍚嶇О")
        return
    
    log_step(f"鎵归噺娣诲姞 {len(names)} 涓枃妗?)
    
    try:
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        success = 0
        failed = 0
        total_chunks = 0
        
        for i, name in enumerate(names, 1):
            doc_path = find_doc_in_docs(name)
            if not doc_path:
                log_error(f"[{i}/{len(names)}] 鏈壘鍒? {name}")
                failed += 1
                continue
            
            try:
                text = read_file(doc_path)
                if not text or not text.strip():
                    log_info(f"[{i}/{len(names)}] 璺宠繃绌烘枃浠? {Path(doc_path).name}")
                    continue
                
                doc_name = Path(doc_path).stem
                text = f"[鏂囦欢鍚? {doc_name}]\n{text}"
                doc = {"path": doc_path, "text": text}
                
                count = db.add(doc, chunk_cfg, source_type="local_file")
                total_chunks += count
                success += 1
                log_ok(f"[{i}/{len(names)}] {Path(doc_path).name} ({count} chunks)")
            except Exception as e:
                log_error(f"[{i}/{len(names)}] 澶辫触: {Path(doc_path).name} - {e}")
                failed += 1
        
        print()
        log_ok(f"鎵归噺娣诲姞瀹屾垚: {success} 鎴愬姛, {failed} 澶辫触, 鍏?{total_chunks} chunks")
        
    except Exception as e:
        log_error(f"杩炴帴鏁版嵁搴撳け璐? {e}")


def delete_document():
    """鍒犻櫎鍗曚釜鏂囨。鐨勫悜閲忚褰?""
    filename = input("\n  璇疯緭鍏ユ枃妗ｅ悕绉? ").strip()
    if not filename:
        log_info("宸插彇娑?)
        return
    
    try:
        _, db = connect_chroma()
        
        # 鏌ユ壘鍖归厤鐨勫悜閲忚褰?        docs = db.list_documents()
        matches = [d for d in docs if filename.lower() in d["source_name"].lower()]
        
        if not matches:
            log_error(f"鏈壘鍒板尮閰嶇殑鍚戦噺璁板綍: {filename}")
            return
        
        if len(matches) > 1:
            log_info("鎵惧埌澶氫釜鍖归厤:")
            for d in matches:
                log_info(f"  - {d['source_name']} ({d['chunks']} chunks)")
        
        doc = matches[0]
        log_step(f"鍒犻櫎鍚戦噺璁板綍: {doc['source_name']}")
        
        if not confirm(f"纭畾鍒犻櫎 {doc['source_name']} ({doc['chunks']} chunks)?"):
            return
        
        db.delete(doc["source"])
        log_ok(f"鍒犻櫎鎴愬姛: {doc['source_name']}")
        
    except Exception as e:
        log_error(f"鍒犻櫎澶辫触: {e}")


def delete_documents_batch():
    """鎵归噺鍒犻櫎鏂囨。鐨勫悜閲忚褰?""
    print("\n  璇疯緭鍏ユ枃妗ｅ悕绉帮紙澶氫釜鐢ㄧ┖鏍兼垨閫楀彿鍒嗛殧锛?")
    input_str = input("  > ").strip()
    if not input_str:
        log_info("宸插彇娑?)
        return
    
    # 瑙ｆ瀽鏂囦欢鍚嶅垪琛?    names = []
    for sep in [",", " ", "\t"]:
        names = [n.strip() for n in input_str.split(sep) if n.strip()]
        if names:
            break
    
    if not names:
        log_info("鏈緭鍏ユ湁鏁堢殑鏂囨。鍚嶇О")
        return
    
    try:
        _, db = connect_chroma()
        docs = db.list_documents()
        
        # 鏌ユ壘鎵€鏈夊尮閰?        to_delete = []
        for name in names:
            matches = [d for d in docs if name.lower() in d["source_name"].lower()]
            if matches:
                to_delete.extend(matches)
            else:
                log_warn(f"鏈壘鍒? {name}")
        
        if not to_delete:
            log_info("娌℃湁鎵惧埌鍖归厤鐨勬枃妗?)
            return
        
        # 鍘婚噸
        seen = set()
        unique_delete = []
        for d in to_delete:
            if d["source"] not in seen:
                seen.add(d["source"])
                unique_delete.append(d)
        
        log_step(f"鎵归噺鍒犻櫎 {len(unique_delete)} 涓枃妗ｇ殑鍚戦噺璁板綍")
        
        # 鏄剧ず灏嗚鍒犻櫎鐨勬枃妗?        for d in unique_delete:
            log_info(f"  - {d['source_name']} ({d['chunks']} chunks)")
        
        if not confirm("纭畾鍒犻櫎浠ヤ笂璁板綍?"):
            return
        
        success = 0
        failed = 0
        for d in unique_delete:
            try:
                db.delete(d["source"])
                log_ok(f"宸插垹闄? {d['source_name']}")
                success += 1
            except Exception as e:
                log_error(f"鍒犻櫎澶辫触: {d['source_name']} - {e}")
                failed += 1
        
        print()
        log_ok(f"鎵归噺鍒犻櫎瀹屾垚: {success} 鎴愬姛, {failed} 澶辫触")
        
    except Exception as e:
        log_error(f"杩炴帴鏁版嵁搴撳け璐? {e}")


def crawl_webpage():
    """鐖彇鍗曚釜缃戦〉"""
    from core.utils import md5_short
    
    url = input("\n  璇疯緭鍏ョ綉椤?URL: ").strip()
    if not url:
        log_info("宸插彇娑?)
        return
    
    log_step(f"鐖彇缃戦〉: {url}")
    
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        log_error("缂哄皯渚濊禆锛岃杩愯: uv pip install requests beautifulsoup4")
        return
    
    try:
        # 1. 鐖彇缃戦〉
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string if soup.title else url
        
        # 2. 鎻愬彇绾枃鏈?        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        text = " ".join(text.split())
        
        if not text:
            log_error("缃戦〉鍐呭涓虹┖")
            return
        
        # 3. 淇濆瓨鍒?data/web 鐩綍
        web_dir = ROOT / "data" / "web"
        web_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{md5_short(url)}.txt"
        filepath = web_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"[缃戦〉鏍囬: {title}]\n")
            f.write(f"[鏉ユ簮: {url}]\n")
            f.write(f"[鐖彇鏃堕棿: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n\n")
            f.write(text)
        
        # 4. 娣诲姞鍒板悜閲忓簱
        from core.document import read_file
        from config.settings import get_chunk_config
        
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        text_content = read_file(str(filepath))
        doc_name = filepath.stem
        doc = {"path": str(filepath), "text": f"[鏂囦欢鍚? {doc_name}]\n{text_content}"}
        count = db.add(doc, chunk_cfg, source_type="local_file")
        
        log_ok(f"鐖彇鎴愬姛: {filename} ({count} chunks)")
        
    except Exception as e:
        log_error(f"鐖彇澶辫触: {e}")


def crawl_webpages_batch():
    """鎵归噺鐖彇缃戦〉"""
    from core.utils import md5_short
    
    print("\n  璇疯緭鍏ョ綉椤?URL锛堝涓敤绌烘牸鎴栭€楀彿鍒嗛殧锛?")
    input_str = input("  > ").strip()
    if not input_str:
        log_info("宸插彇娑?)
        return
    
    # 瑙ｆ瀽 URL 鍒楄〃
    urls = []
    for sep in [",", " ", "\t"]:
        urls = [u.strip() for u in input_str.split(sep) if u.strip()]
        if urls:
            break
    
    if not urls:
        log_info("鏈緭鍏ユ湁鏁堢殑 URL")
        return
    
    log_step(f"鎵归噺鐖彇 {len(urls)} 涓綉椤?)
    
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        log_error("缂哄皯渚濊禆锛岃杩愯: uv pip install requests beautifulsoup4")
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
            # 鐖彇缃戦〉
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string if soup.title else url
            
            # 鎻愬彇绾枃鏈?            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            text = " ".join(text.split())
            
            if not text:
                log_info(f"[{i}/{len(urls)}] 璺宠繃绌虹綉椤? {url}")
                continue
            
            # 淇濆瓨鍒版湰鍦?            filename = f"{md5_short(url)}.txt"
            filepath = web_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"[缃戦〉鏍囬: {title}]\n")
                f.write(f"[鏉ユ簮: {url}]\n")
                f.write(f"[鐖彇鏃堕棿: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n\n")
                f.write(text)
            
            # 娣诲姞鍒板悜閲忓簱
            text_content = read_file(str(filepath))
            doc_name = filepath.stem
            doc = {"path": str(filepath), "text": f"[鏂囦欢鍚? {doc_name}]\n{text_content}"}
            count = db.add(doc, chunk_cfg, source_type="local_file")
            
            total_chunks += count
            success += 1
            log_ok(f"[{i}/{len(urls)}] {title} ({count} chunks)")
            
        except Exception as e:
            failed += 1
            log_error(f"[{i}/{len(urls)}] 澶辫触: {url} - {e}")
    
    print()
    log_ok(f"鎵归噺鐖彇瀹屾垚: {success} 鎴愬姛, {failed} 澶辫触, 鍏?{total_chunks} chunks")


def sync_documents(source: str = "all"):
    """鍚屾鏂囨。锛堝姣攈ash锛岃嚜鍔ㄥ鍒犳敼锛?""
    from core.document import load_all_documents
    from config.settings import get_chunk_config
    
    log_step("鍚屾鏂囨。...")
    
    try:
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        # 鏍规嵁鏁版嵁婧愬姞杞芥枃妗?        dirs = []
        if source in ("all", "docs"):
            dirs.append(ROOT / "data" / "docs")
        if source in ("all", "web"):
            dirs.append(ROOT / "data" / "web")
        
        documents = load_all_documents(*dirs)
        
        if not documents:
            log_info("娌℃湁鏈湴鏂囨。")
            return
        
        # 鏄剧ず鍔犺浇淇℃伅
        if source == "all":
            docs_count = len(load_all_documents(ROOT / "data" / "docs"))
            web_count = len(load_all_documents(ROOT / "data" / "web"))
            log_info(f"鍔犺浇 {len(documents)} 涓枃妗?({docs_count} docs + {web_count} web)")
        else:
            log_info(f"鍔犺浇 {len(documents)} 涓枃妗?)
        
        # 杩涘害鍥炶皟
        def on_progress(op, idx, total, name, count):
            if op == "add":
                progress_bar(idx, total, prefix="鏂板", suffix=f"{name} ({count} chunks)")
            elif op == "update":
                progress_bar(idx, total, prefix="鏇存柊", suffix=f"{name} ({count} chunks)")
            elif op == "delete":
                log_info(f"鍒犻櫎: {name}")
        
        stats = db.sync(documents, chunk_cfg, on_progress=on_progress)
        
        print()  # 鎹㈣
        if stats["added"] + stats["updated"] + stats["deleted"] == 0:
            log_info(f"鏃犲彉鍖?({stats['unchanged']} 涓枃浠舵湭鍙?")
        else:
            log_ok(f"鍚屾瀹屾垚: 鏂板 {stats['added']}, 鏇存柊 {stats['updated']}, 鍒犻櫎 {stats['deleted']}, 鏈彉 {stats['unchanged']}")
        
    except Exception as e:
        log_error(f"鍚屾澶辫触: {e}")


def rebuild_documents(source: str = "all"):
    """鍏ㄩ噺閲嶅缓鍚戦噺搴?""
    from core.document import load_all_documents
    from config.settings import get_chunk_config
    
    if not confirm("纭畾瑕佸叏閲忛噸寤哄悜閲忓簱锛熻繖灏嗘竻绌虹幇鏈夋暟鎹苟閲嶆柊澶勭悊鎵€鏈夋枃妗?, default=False):
        return
    
    log_step("鍏ㄩ噺閲嶅缓鍚戦噺搴?..")
    
    try:
        _, db = connect_chroma()
        chunk_cfg = get_chunk_config()
        
        # 鏍规嵁鏁版嵁婧愬姞杞芥枃妗?        dirs = []
        if source in ("all", "docs"):
            dirs.append(ROOT / "data" / "docs")
        if source in ("all", "web"):
            dirs.append(ROOT / "data" / "web")
        
        documents = load_all_documents(*dirs)
        
        if not documents:
            log_info("娌℃湁鏈湴鏂囨。")
            return
        
        # 鏄剧ず鍔犺浇淇℃伅
        if source == "all":
            docs_count = len(load_all_documents(ROOT / "data" / "docs"))
            web_count = len(load_all_documents(ROOT / "data" / "web"))
            log_info(f"鍔犺浇 {len(documents)} 涓枃妗?({docs_count} docs + {web_count} web)")
        else:
            log_info(f"鍔犺浇 {len(documents)} 涓枃妗?)
        
        # 杩涘害鍥炶皟
        def on_progress(op, idx, total, name, count):
            progress_bar(idx, total, prefix="閲嶅缓涓?, suffix=f"{name} ({count} chunks)")
        
        total_chunks = db.rebuild(documents, chunk_cfg, on_progress=on_progress)
        
        print()  # 鎹㈣
        log_ok(f"閲嶅缓瀹屾垚: {total_chunks} chunks, {len(documents)} 涓枃妗?)
        
    except Exception as e:
        log_error(f"閲嶅缓澶辫触: {e}")


def clean_orphan_records():
    """娓呯悊瀛ょ珛璁板綍"""
    log_step("妫€鏌ュ绔嬭褰?..")
    
    try:
        _, db = connect_chroma()
        docs_dir = str(ROOT / "data" / "docs")
        web_dir = str(ROOT / "data" / "web")
        
        orphans = db.check_orphan_records(docs_dir, web_dir)
        
        if not orphans:
            log_info("娌℃湁瀛ょ珛璁板綍")
            return
        
        log_info(f"鎵惧埌 {len(orphans)} 涓绔嬭褰?")
        for doc in orphans:
            log_info(f"  - {doc['source_name']} ({doc['chunks']} chunks)")
        
        if not confirm("纭畾娓呯悊杩欎簺瀛ょ珛璁板綍锛?):
            return
        
        count = 0
        for doc in orphans:
            try:
                db.delete(doc["source"])
                count += 1
            except:
                pass
        log_ok(f"娓呯悊瀹屾垚: {count} 涓绔嬭褰?)
        
    except Exception as e:
        log_error(f"娓呯悊澶辫触: {e}")


def main():
    """涓诲嚱鏁?""
    while True:
        header("Ezy-RAG 鏂囨。绠＄悊")
        
        # 鏄剧ず缁熻
        stats = get_database_stats()
        info_card("鏂囨。缁熻", {
            "鏈湴鏂囨。": f"{stats['docs_count']} 涓?,
            "缃戦〉鏁版嵁": f"{stats['web_count']} 涓?,
            "宸插鍏?: f"{stats['vector_docs']} 涓?,
            "鍚戦噺鍧?: f"{stats['chunks']} 涓?,
        })
        
        # 鑿滃崟
        choice = menu("鎿嶄綔", [
            "鏌ョ湅鏂囨。鍒楄〃",
            "娣诲姞鏂囨。",
            "鎵归噺娣诲姞",
            "鍒犻櫎鏂囨。",
            "鎵归噺鍒犻櫎",
            "缃戦〉鐖彇",
            "鍚屾鏂囨。",
            "鍏ㄩ噺閲嶅缓",
            "娓呯悊瀛ょ珛",
            "杩斿洖"
        ])
        
        if choice == 1:
            source = select_data_source("閫夋嫨鏌ョ湅鑼冨洿")
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
            # 缃戦〉鐖彇瀛愯彍鍗?            sub_choice = menu("缃戦〉鐖彇", [
                "鐖彇鍗曚釜缃戦〉",
                "鎵归噺鐖彇缃戦〉",
                "杩斿洖"
            ])
            if sub_choice == 1:
                crawl_webpage()
            elif sub_choice == 2:
                crawl_webpages_batch()
        elif choice == 7:
            source = select_data_source("閫夋嫨鍚屾鑼冨洿")
            sync_documents(source)
        elif choice == 8:
            source = select_data_source("閫夋嫨閲嶅缓鑼冨洿")
            rebuild_documents(source)
        elif choice == 9:
            clean_orphan_records()
        elif choice == 10:
            break
        
        if choice != 10:
            from cli.ui import pause
            pause()


if __name__ == "__main__":
    main()
