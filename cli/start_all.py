# -*- coding: utf-8 -*-
"""
Ezy-RAG — 服务管理
参考前端设计的简洁服务管理界面"""
import os
import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli.ui import header, status_card, menu, confirm, log_ok, log_error, log_info, log_step
from cli.cli_core import check_port, get_service_status, reload_env

# 服务模块映射
SERVICE_MODULES = {
    "chromadb": "servers.chroma",
    "embedding": "servers.embedding",
    "rerank": "servers.rerank",
    "mcp": "servers.mcp",
    "web": "servers.web"
}


def get_services_display() -> list:
    """获取服务状态显示数据"""
    status = get_service_status()
    return [
        {"name": "Web", "online": status["web"]["online"], "info": status["web"]["info"]},
        {"name": "ChromaDB", "online": status["chromadb"]["online"], "info": status["chromadb"]["info"]},
        {"name": "Embedding", "online": status["embedding"]["online"], "info": status["embedding"]["info"]},
        {"name": "Rerank", "online": status["rerank"]["online"], "info": status["rerank"]["info"], "skip": status["rerank"].get("skip", False)},
        {"name": "MCP", "online": status["mcp"]["online"], "info": status["mcp"]["info"]},
    ]


def start_service(name: str) -> bool:
    """启动单个服务"""
    key = name.lower()
    module = SERVICE_MODULES.get(key)
    if not module:
        log_error(f"未知服务: {name}")
        return False
    
    status = get_service_status()
    svc = status.get(key, {})
    
    if svc.get("online"):
        log_info(f"{name} 已在运行")
        return True
    
    if svc.get("skip"):
        log_info(f"{name} 未启用，跳过")
        return True
    
    log_step(f"启动 {name}...")
    try:
        subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=ROOT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
        time.sleep(2)
        
        # 检查是否启动成功
        status = get_service_status()
        if status.get(key, {}).get("online"):
            log_ok(f"{name} 启动成功")
            return True
        else:
            log_error(f"{name} 启动超时")
            return False
    except Exception as e:
        log_error(f"{name} 启动失败: {e}")
        return False


def stop_service_by_port(name: str, port: int) -> bool:
    """通过端口停止服务"""
    log_step(f"停止 {name}...")
    try:
        if sys.platform == 'win32':
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.split()[-1]
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
                    log_ok(f"{name} 已停止")
                    return True
        else:
            result = subprocess.run(["lsof", "-i", f":{port}", "-t"], capture_output=True, text=True)
            if result.stdout.strip():
                pid = result.stdout.strip().split('\n')[0]
                os.kill(int(pid), 15)
                log_ok(f"{name} 已停止")
                return True
        log_info(f"{name} 未在运行")
        return False
    except Exception as e:
        log_error(f"{name} 停止失败: {e}")
        return False


def start_all():
    """启动所有服务"""
    status = get_service_status()
    
    # 启动 Web（最先启动，其他服务依赖它）
    if not status["web"]["online"]:
        start_service("web")
    
    # 启动 ChromaDB
    if not status["chromadb"]["online"]:
        start_service("chromadb")
    
    # 启动 Embedding (仅本地模式)
    if status["embedding"]["mode"] == "local" and not status["embedding"]["online"]:
        start_service("embedding")
    
    # 启动 Rerank (仅本地模式且启用)
    if status["rerank"]["enabled"] and status["rerank"]["mode"] == "local" and not status["rerank"]["online"]:
        start_service("rerank")
    
    # 启动 MCP
    if not status["mcp"]["online"]:
        start_service("mcp")


def stop_all():
    """停止所有服务"""
    status = get_service_status()
    
    if status["chromadb"]["online"]:
        stop_service_by_port("ChromaDB", status["chromadb"]["port"])
    
    if status["embedding"]["mode"] == "local" and status["embedding"]["online"] and status["embedding"].get("port"):
        stop_service_by_port("Embedding", status["embedding"]["port"])
    
    if status["rerank"]["enabled"] and status["rerank"]["mode"] == "local" and status["rerank"]["online"] and status["rerank"].get("port"):
        stop_service_by_port("Rerank", status["rerank"]["port"])
    
    if status["mcp"]["online"]:
        stop_service_by_port("MCP", status["mcp"]["port"])
    
    # 停止 Web（最后停止）
    if status["web"]["online"]:
        stop_web()


def stop_web():
    """通过 API 关闭 Web 服务"""
    import httpx
    web_host = os.getenv("WEB_API_HOST", "127.0.0.1")
    web_port = int(os.getenv("WEB_API_PORT", "9767"))
    try:
        with httpx.Client(timeout=5) as client:
            r = client.post(f"http://{web_host}:{web_port}/api/services/shutdown")
            if r.status_code == 200:
                log_ok("Web 服务即将关闭")
                return True
            else:
                log_error(f"关闭失败: {r.status_code}")
                return False
    except Exception as e:
        log_error(f"关闭失败: {e}")
        return False


def main():
    """主函数"""
    while True:
        header("Ezy-RAG 服务管理")
        
        # 显示服务状态
        status_card(get_services_display())
        
        # 菜单
        choice = menu("操作", [
            "启动全部",
            "停止全部",
            "刷新状态",
            "返回"
        ])
        
        if choice == 1:
            if confirm("确定启动所有服务？"):
                start_all()
        elif choice == 2:
            if confirm("确定停止所有服务？"):
                stop_all()
        elif choice == 3:
            continue
        elif choice == 4:
            break


if __name__ == "__main__":
    main()
