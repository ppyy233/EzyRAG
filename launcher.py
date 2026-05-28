# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.14 — 统一启动器
一键启动所有服务，包括后端 API、MCP、ChromaDB、前端

用法:
  python launcher.py                    # 启动所有服务
  python launcher.py --services api,mcp # 启动指定服务
  python launcher.py --frontend         # 启动前端开发服务器
  python launcher.py --stop             # 停止所有服务
"""
import subprocess
import sys
import os
import time
import signal
import argparse
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import settings

# 服务配置
SERVICES = {
    "chroma": {
        "module": "servers.chroma",
        "port": 9898,
        "name": "ChromaDB"
    },
    "mcp": {
        "module": "servers.mcp",
        "port": 9766,
        "name": "MCP Server"
    },
    "api": {
        "module": "servers.api",
        "port": 9767,
        "name": "API Server"
    },
    "rerank": {
        "module": "servers.rerank",
        "port": 5001,
        "name": "Rerank Server"
    }
}

# 进程管理
processes = {}

def check_port(port: int) -> bool:
    """检查端口是否被占用"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except:
        return False

def start_service(name: str, config: dict) -> bool:
    """启动服务"""
    module = config["module"]
    port = config["port"]
    service_name = config["name"]
    
    # 检查端口是否已被占用
    if check_port(port):
        print(f"  [SKIP] {service_name} 已在运行 (端口 {port})")
        return True
    
    print(f"  [START] {service_name}...")
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=ROOT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
        processes[name] = process
        
        # 等待服务启动
        time.sleep(2)
        
        if process.poll() is None:
            print(f"  [OK] {service_name} 已启动 (PID: {process.pid}, 端口: {port})")
            return True
        else:
            print(f"  [FAIL] {service_name} 启动失败")
            return False
    except Exception as e:
        print(f"  [FAIL] {service_name} 启动失败: {e}")
        return False

def stop_service(name: str) -> bool:
    """停止服务"""
    if name not in processes:
        return False
    
    process = processes[name]
    if process.poll() is not None:
        del processes[name]
        return False
    
    service_name = SERVICES[name]["name"]
    print(f"  [STOP] {service_name}...")
    
    try:
        if sys.platform == 'win32':
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], 
                         capture_output=True, check=False)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        
        del processes[name]
        print(f"  [OK] {service_name} 已停止")
        return True
    except Exception as e:
        print(f"  [FAIL] {service_name} 停止失败: {e}")
        return False

def stop_all_services():
    """停止所有服务"""
    for name in list(processes.keys()):
        stop_service(name)

def show_status():
    """显示服务状态"""
    print("\n" + "=" * 60)
    print("  Ezy-RAG 服务状态")
    print("=" * 60)
    
    for name, config in SERVICES.items():
        port = config["port"]
        service_name = config["name"]
        status = "运行中" if check_port(port) else "未运行"
        pid = processes[name].pid if name in processes and processes[name].poll() is None else "-"
        print(f"  {service_name:<20} {status:<10} PID: {pid:<10} 端口: {port}")
    
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Ezy-RAG 统一启动器")
    parser.add_argument("--services", type=str, default="all",
                       help="启动的服务 (chroma,mcp,api,rerank,all)")
    parser.add_argument("--frontend", action="store_true",
                       help="启动前端开发服务器")
    parser.add_argument("--stop", action="store_true",
                       help="停止所有服务")
    parser.add_argument("--status", action="store_true",
                       help="显示服务状态")
    args = parser.parse_args()
    
    print("=" * 60)
    print("  Ezy-RAG V0.0.14 — 统一启动器")
    print("=" * 60)
    
    # 显示状态
    if args.status:
        show_status()
        return
    
    # 停止所有服务
    if args.stop:
        stop_all_services()
        return
    
    # 确定要启动的服务
    if args.services == "all":
        services_to_start = ["chroma", "mcp", "api"]
    else:
        services_to_start = args.services.split(",")
    
    # 启动服务
    print("\n启动服务:")
    for name in services_to_start:
        if name in SERVICES:
            start_service(name, SERVICES[name])
        else:
            print(f"  [SKIP] 未知服务: {name}")
    
    # 启动前端
    if args.frontend:
        frontend_dir = ROOT / "frontend"
        if frontend_dir.exists():
            print("\n启动前端开发服务器...")
            try:
                subprocess.Popen(
                    ["npm", "run", "dev"],
                    cwd=frontend_dir,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
                )
                print("  [OK] 前端开发服务器已启动 (http://localhost:5173)")
            except Exception as e:
                print(f"  [FAIL] 前端启动失败: {e}")
        else:
            print("  [SKIP] 前端目录不存在")
    
    # 显示状态
    print("\n" + "=" * 60)
    print("  服务已启动!")
    print("=" * 60)
    print("\n访问地址:")
    print("  前端: http://localhost:5173")
    print("  API 文档: http://localhost:9767/docs")
    print("  MCP 服务: http://localhost:9766")
    print("\n按 Ctrl+C 停止所有服务")
    
    # 等待用户中断
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止所有服务...")
        stop_all_services()
        print("已停止所有服务")

if __name__ == "__main__":
    main()
