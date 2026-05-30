# -*- coding: utf-8 -*-
"""
Ezy-RAG 鈥?鏈嶅姟绠＄悊
鍙傝€冨墠绔璁＄殑绠€娲佹湇鍔＄鐞嗙晫闈?"""
import os
import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli.ui import header, status_card, menu, confirm, log_ok, log_error, log_info, log_step
from cli.cli_core import check_port, get_service_status, reload_env

# 鏈嶅姟妯″潡鏄犲皠
SERVICE_MODULES = {
    "chromadb": "servers.chroma",
    "embedding": "servers.embedding",
    "rerank": "servers.rerank",
    "mcp": "servers.mcp"
}


def get_services_display() -> list:
    """鑾峰彇鏈嶅姟鐘舵€佹樉绀烘暟鎹?""
    status = get_service_status()
    return [
        {"name": "ChromaDB", "online": status["chromadb"]["online"], "info": status["chromadb"]["info"]},
        {"name": "Embedding", "online": status["embedding"]["online"], "info": status["embedding"]["info"]},
        {"name": "Rerank", "online": status["rerank"]["online"], "info": status["rerank"]["info"], "skip": status["rerank"].get("skip", False)},
        {"name": "MCP", "online": status["mcp"]["online"], "info": status["mcp"]["info"]},
    ]


def start_service(name: str) -> bool:
    """鍚姩鍗曚釜鏈嶅姟"""
    key = name.lower()
    module = SERVICE_MODULES.get(key)
    if not module:
        log_error(f"鏈煡鏈嶅姟: {name}")
        return False
    
    status = get_service_status()
    svc = status.get(key, {})
    
    if svc.get("online"):
        log_info(f"{name} 宸插湪杩愯")
        return True
    
    if svc.get("skip"):
        log_info(f"{name} 鏈惎鐢紝璺宠繃")
        return True
    
    log_step(f"鍚姩 {name}...")
    try:
        subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=ROOT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
        time.sleep(2)
        
        # 妫€鏌ユ槸鍚﹀惎鍔ㄦ垚鍔?        status = get_service_status()
        if status.get(key, {}).get("online"):
            log_ok(f"{name} 鍚姩鎴愬姛")
            return True
        else:
            log_error(f"{name} 鍚姩瓒呮椂")
            return False
    except Exception as e:
        log_error(f"{name} 鍚姩澶辫触: {e}")
        return False


def stop_service_by_port(name: str, port: int) -> bool:
    """閫氳繃绔彛鍋滄鏈嶅姟"""
    log_step(f"鍋滄 {name}...")
    try:
        if sys.platform == 'win32':
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.split()[-1]
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
                    log_ok(f"{name} 宸插仠姝?)
                    return True
        else:
            result = subprocess.run(["lsof", "-i", f":{port}", "-t"], capture_output=True, text=True)
            if result.stdout.strip():
                pid = result.stdout.strip().split('\n')[0]
                os.kill(int(pid), 15)
                log_ok(f"{name} 宸插仠姝?)
                return True
        log_info(f"{name} 鏈湪杩愯")
        return False
    except Exception as e:
        log_error(f"{name} 鍋滄澶辫触: {e}")
        return False


def start_all():
    """鍚姩鎵€鏈夋湇鍔?""
    status = get_service_status()
    
    # 鍚姩 ChromaDB
    if not status["chromadb"]["online"]:
        start_service("chromadb")
    
    # 鍚姩 Embedding (浠呮湰鍦版ā寮?
    if status["embedding"]["mode"] == "local" and not status["embedding"]["online"]:
        start_service("embedding")
    
    # 鍚姩 Rerank (浠呮湰鍦版ā寮忎笖鍚敤)
    if status["rerank"]["enabled"] and status["rerank"]["mode"] == "local" and not status["rerank"]["online"]:
        start_service("rerank")
    
    # 鍚姩 MCP
    if not status["mcp"]["online"]:
        start_service("mcp")


def stop_all():
    """鍋滄鎵€鏈夋湇鍔?""
    status = get_service_status()
    
    if status["chromadb"]["online"]:
        stop_service_by_port("ChromaDB", status["chromadb"]["port"])
    
    if status["embedding"]["mode"] == "local" and status["embedding"]["online"] and status["embedding"].get("port"):
        stop_service_by_port("Embedding", status["embedding"]["port"])
    
    if status["rerank"]["enabled"] and status["rerank"]["mode"] == "local" and status["rerank"]["online"] and status["rerank"].get("port"):
        stop_service_by_port("Rerank", status["rerank"]["port"])
    
    if status["mcp"]["online"]:
        stop_service_by_port("MCP", status["mcp"]["port"])


def main():
    """涓诲嚱鏁?""
    while True:
        header("Ezy-RAG 鏈嶅姟绠＄悊")
        
        # 鏄剧ず鏈嶅姟鐘舵€?        status_card(get_services_display())
        
        # 鑿滃崟
        choice = menu("鎿嶄綔", [
            "鍚姩鍏ㄩ儴",
            "鍋滄鍏ㄩ儴",
            "鍒锋柊鐘舵€?,
            "杩斿洖"
        ])
        
        if choice == 1:
            if confirm("纭畾鍚姩鎵€鏈夋湇鍔★紵"):
                start_all()
        elif choice == 2:
            if confirm("纭畾鍋滄鎵€鏈夋湇鍔★紵"):
                stop_all()
        elif choice == 3:
            continue
        elif choice == 4:
            break


if __name__ == "__main__":
    main()
