# -*- coding: utf-8 -*-
"""
Ezy-RAG V1.0.0 — 服务管理脚本
用法: python start_all.py
"""
import subprocess
import sys
import time
import socket
import os
import signal
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROCESSES = {}

# 我们自己服务的端口
OUR_PORTS = {
    "ChromaDB": 9898,
    "MCP": 9766,
    "Rerank": 5001
}

# 各服务的超时时间（Rerank 需要加载模型，时间更长）
SERVICE_TIMEOUT = {
    "ChromaDB": 15,
    "MCP": 15,
    "Rerank": 45
}


def check_service(host: str, port: int) -> bool:
    """检查服务是否运行"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def wait_for_service(host: str, port: int, timeout: int = 15) -> bool:
    """等待服务启动"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return True
            time.sleep(0.5)
        except:
            time.sleep(0.5)
    return False


def start_service(name: str, module: str, host: str, port: int, timeout: int = None) -> bool:
    """启动服务"""
    if timeout is None:
        timeout = SERVICE_TIMEOUT.get(name, 15)

    cleanup_zombie_processes()

    # 1. 优先检查端口是否已监听
    if check_service(host, port):
        print(f"✓ {name} 已经在运行（端口 {port} 已监听）")
        return True

    # 2. 检查是否有残留进程（端口没监听，但进程在）
    if name in PROCESSES and PROCESSES[name].poll() is None:
        pid = PROCESSES[name].pid
        print(f"  {name} 进程存在 (PID: {pid})，等待端口监听...")
        if wait_for_service(host, port, timeout):
            print(f"✓ {name} 已启动 (PID: {pid}, 端口: {port})")
            return True
        else:
            print(f"✗ {name} 启动超时 ({timeout}s)")
            return False

    # 3. 启动新进程
    print(f"启动 {name}...")
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=ROOT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
        PROCESSES[name] = process

        if wait_for_service(host, port, timeout):
            print(f"✓ {name} 已启动 (PID: {process.pid}, 端口: {port})")
            return True
        else:
            print(f"✗ {name} 启动超时 ({timeout}s)")
            return False
    except Exception as e:
        print(f"✗ {name} 启动失败: {e}")
        return False


def stop_service(name: str) -> bool:
    """停止服务"""
    # 1. 先尝试从 PROCESSES 字典中停止
    if name in PROCESSES and PROCESSES[name].poll() is None:
        pid = PROCESSES[name].pid
        
        try:
            print(f"停止 {name} (PID: {pid})...")
            
            if sys.platform == 'win32':
                # Windows: 使用 taskkill 终止进程树
                result = subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True, check=False
                )
                if result.returncode == 0:
                    print(f"✓ {name} 已停止")
                else:
                    print(f"✓ {name} 已停止 (进程可能已退出)")
            else:
                # Linux/Mac: 使用 kill 终止进程组
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                print(f"✓ {name} 已停止")
            
            del PROCESSES[name]
            return True
        except Exception as e:
            print(f"✗ {name} 停止失败: {e}")
            return False
    
    # 2. 如果 PROCESSES 中没有，通过端口查找（只查找我们自己的端口）
    port = OUR_PORTS.get(name)
    if port and check_service("127.0.0.1", port):
        return stop_service_by_port(name, port)
    
    print(f"✗ {name} 未在运行")
    return False


def stop_service_by_port(name: str, port: int) -> bool:
    """通过端口查找并终止服务"""
    try:
        print(f"停止 {name} (端口: {port})...")
        
        if sys.platform == 'win32':
            # Windows: 使用 netstat 查找占用端口的进程
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True
            )

            for line in result.stdout.split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    pid = int(parts[-1])

                    # 终止进程树
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True, check=False
                    )

                    print(f"✓ {name} 已停止 (PID: {pid})")
                    return True
        else:
            # Linux/Mac: 使用 lsof 查找占用端口的进程
            result = subprocess.run(
                ["lsof", "-i", f":{port}"],
                capture_output=True, text=True
            )

            for line in result.stdout.split('\n'):
                if "LISTEN" in line:
                    parts = line.split()
                    pid = int(parts[1])

                    # 终止进程组
                    os.killpg(os.getpgid(pid), signal.SIGTERM)

                    print(f"✓ {name} 已停止 (PID: {pid})")
                    return True

        print(f"✗ {name} 未在运行")
        return False
    except Exception as e:
        print(f"✗ {name} 停止失败: {e}")
        return False


def cleanup_zombie_processes():
    """清理僵尸进程"""
    for name in list(PROCESSES.keys()):
        process = PROCESSES[name]
        if process.poll() is not None:
            del PROCESSES[name]


def show_status():
    """显示服务状态"""
    cleanup_zombie_processes()

    print("\n服务状态：")
    print("-" * 70)
    print(f"{'服务':<20} {'状态':<10} {'PID':<10} {'端口':<10}")
    print("-" * 70)

    # Embedding 服务
    embedding_status = "运行中" if check_service("127.0.0.1", 5000) else "未运行"
    print(f"{'Embedding 服务':<20} {embedding_status:<10} {'-':<10} {'5000':<10}")

    # ChromaDB
    chroma_status = "运行中" if check_service("127.0.0.1", 9898) else "未运行"
    chroma_pid = PROCESSES.get("ChromaDB")
    if chroma_pid:
        chroma_pid = str(chroma_pid.pid) if chroma_pid.poll() is None else "已退出"
    else:
        chroma_pid = "-"
    print(f"{'ChromaDB':<20} {chroma_status:<10} {chroma_pid:<10} {'9898':<10}")

    # MCP
    mcp_status = "运行中" if check_service("127.0.0.1", 9766) else "未运行"
    mcp_pid = PROCESSES.get("MCP")
    if mcp_pid:
        mcp_pid = str(mcp_pid.pid) if mcp_pid.poll() is None else "已退出"
    else:
        mcp_pid = "-"
    print(f"{'MCP':<20} {mcp_status:<10} {mcp_pid:<10} {'9766':<10}")

    # Rerank
    rerank_status = "运行中" if check_service("127.0.0.1", 5001) else "未运行"
    rerank_pid = PROCESSES.get("Rerank")
    if rerank_pid:
        rerank_pid = str(rerank_pid.pid) if rerank_pid.poll() is None else "已退出"
    else:
        rerank_pid = "-"
    print(f"{'Rerank':<20} {rerank_status:<10} {rerank_pid:<10} {'5001':<10}")
    print("-" * 70)


def check_dependencies() -> list:
    """检查依赖服务"""
    errors = []

    # 检查 Embedding 服务
    if not check_service("127.0.0.1", 5000):
        errors.append("Embedding 服务未运行")

    # 检查 ChromaDB 服务
    if not check_service("127.0.0.1", 9898):
        errors.append("ChromaDB 服务未运行")

    return errors


def main():
    """主函数"""
    while True:
        print("\n" + "=" * 60)
        print("  Ezy-RAG V1.0.0 — 服务管理")
        print("=" * 60)
        print("1. 查看服务状态")
        print("2. 启动服务")
        print("3. 停止服务")
        print("4. 重启服务")
        print("5. 退出")

        choice = input("\n请选择 (1-5): ").strip()

        if choice == "1":
            show_status()

        elif choice == "2":
            print("\n启动服务：")
            print("1. 启动所有服务")
            print("2. 启动 ChromaDB")
            print("3. 启动 MCP")
            print("4. 启动 Rerank")
            print("5. 返回")

            sub_choice = input("\n请选择 (1-5): ").strip()

            if sub_choice == "1":
                start_service("ChromaDB", "servers.chroma", "127.0.0.1", 9898)
                start_service("MCP", "servers.mcp", "127.0.0.1", 9766)
                start_service("Rerank", "servers.rerank", "127.0.0.1", 5001)

            elif sub_choice == "2":
                start_service("ChromaDB", "servers.chroma", "127.0.0.1", 9898)

            elif sub_choice == "3":
                errors = check_dependencies()
                if errors:
                    print("\n启动失败：")
                    for error in errors:
                        print(f"  ✗ {error}")
                    print("\n请先启动依赖服务后再试。")
                else:
                    start_service("MCP", "servers.mcp", "127.0.0.1", 9766)

            elif sub_choice == "4":
                start_service("Rerank", "servers.rerank", "127.0.0.1", 5001)

            elif sub_choice == "5":
                continue

            else:
                print("无效的选择")

        elif choice == "3":
            print("\n停止服务：")
            print("1. 停止所有服务")
            print("2. 停止 ChromaDB")
            print("3. 停止 MCP")
            print("4. 停止 Rerank")
            print("5. 返回")

            sub_choice = input("\n请选择 (1-5): ").strip()

            if sub_choice == "1":
                stop_service("ChromaDB")
                stop_service("MCP")
                stop_service("Rerank")

            elif sub_choice == "2":
                stop_service("ChromaDB")

            elif sub_choice == "3":
                stop_service("MCP")

            elif sub_choice == "4":
                stop_service("Rerank")

            elif sub_choice == "5":
                continue

            else:
                print("无效的选择")

        elif choice == "4":
            print("\n重启服务：")
            print("1. 重启所有服务")
            print("2. 重启 ChromaDB")
            print("3. 重启 MCP")
            print("4. 重启 Rerank")
            print("5. 返回")

            sub_choice = input("\n请选择 (1-5): ").strip()

            if sub_choice == "1":
                stop_service("ChromaDB")
                stop_service("MCP")
                stop_service("Rerank")
                time.sleep(2)
                start_service("ChromaDB", "servers.chroma", "127.0.0.1", 9898)
                start_service("MCP", "servers.mcp", "127.0.0.1", 9766)
                start_service("Rerank", "servers.rerank", "127.0.0.1", 5001)

            elif sub_choice == "2":
                stop_service("ChromaDB")
                time.sleep(2)
                start_service("ChromaDB", "servers.chroma", "127.0.0.1", 9898)

            elif sub_choice == "3":
                stop_service("MCP")
                time.sleep(2)
                start_service("MCP", "servers.mcp", "127.0.0.1", 9766)

            elif sub_choice == "4":
                stop_service("Rerank")
                time.sleep(2)
                start_service("Rerank", "servers.rerank", "127.0.0.1", 5001)

            elif sub_choice == "5":
                continue

            else:
                print("无效的选择")

        elif choice == "5":
            # 停止所有服务
            for name in list(PROCESSES.keys()):
                stop_service(name)
            break

        else:
            print("无效的选择")


if __name__ == "__main__":
    main()
