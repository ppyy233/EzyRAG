# -*- coding: utf-8 -*-
"""
Ezy-RAG V0.0.17 - 服务管理脚本
用法: python start_all.py
"""
import subprocess
import sys
import time
import socket
import os
import signal
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

PROCESSES = {}

OUR_PORTS = {
    "Embedding": int(os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234").split(":")[-1].split("/")[0]),
    "ChromaDB": int(os.getenv("CHROMA_SERVER_PORT", "9898")),
    "MCP": int(os.getenv("MCP_SERVER_PORT", "9766")),
    "Rerank": int(os.getenv("RERANK_LOCAL_URL", "http://127.0.0.1:5001").split(":")[-1].split("/")[0]),
}

SERVICE_TIMEOUT = {
    "Embedding": 60,
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

    if check_service(host, port):
        print(f"[OK] {name} 已经在运行（端口 {port} 已监听）")
        return True

    if name in PROCESSES and PROCESSES[name].poll() is None:
        pid = PROCESSES[name].pid
        print(f"  {name} 进程存在 (PID: {pid})，等待端口监听...")
        if wait_for_service(host, port, timeout):
            print(f"[OK] {name} 已启动 (PID: {pid}, 端口: {port})")
            return True
        else:
            print(f"[FAIL] {name} 启动超时 ({timeout}s)")
            return False

    print(f"启动 {name}...")
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=ROOT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
        PROCESSES[name] = process

        if wait_for_service(host, port, timeout):
            print(f"[OK] {name} 已启动 (PID: {process.pid}, 端口: {port})")
            return True
        else:
            print(f"[FAIL] {name} 启动超时 ({timeout}s)")
            return False
    except Exception as e:
        print(f"[FAIL] {name} 启动失败: {e}")
        return False


def stop_service(name: str) -> bool:
    """停止服务"""
    if name in PROCESSES and PROCESSES[name].poll() is None:
        pid = PROCESSES[name].pid
        try:
            print(f"停止 {name} (PID: {pid})...")
            if sys.platform == 'win32':
                result = subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True, check=False
                )
                if result.returncode == 0:
                    print(f"[OK] {name} 已停止")
                else:
                    print(f"[OK] {name} 已停止（进程可能已退出）")
            else:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                print(f"[OK] {name} 已停止")
            del PROCESSES[name]
            return True
        except Exception as e:
            print(f"[FAIL] {name} 停止失败: {e}")
            return False

    port = OUR_PORTS.get(name)
    if port and check_service("127.0.0.1", port):
        return stop_service_by_port(name, port)

    print(f"[INFO] {name} 未在运行")
    return False


def stop_service_by_port(name: str, port: int) -> bool:
    """通过端口查找并终止服务"""
    try:
        print(f"停止 {name} (端口: {port})...")
        if sys.platform == 'win32':
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True
            )
            for line in result.stdout.split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    pid = int(parts[-1])
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True, check=False
                    )
                    print(f"[OK] {name} 已停止 (PID: {pid})")
                    return True
        else:
            result = subprocess.run(
                ["lsof", "-i", f":{port}"],
                capture_output=True, text=True
            )
            for line in result.stdout.split('\n'):
                if "LISTEN" in line:
                    parts = line.split()
                    pid = int(parts[1])
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                    print(f"[OK] {name} 已停止 (PID: {pid})")
                    return True
        print(f"[INFO] {name} 未在运行")
        return False
    except Exception as e:
        print(f"[FAIL] {name} 停止失败: {e}")
        return False


def get_pid_by_port(port: int) -> str:
    """通过端口查找进程PID"""
    try:
        if sys.platform == 'win32':
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True
            )
            for line in result.stdout.split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    return line.split()[-1]
        else:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"],
                capture_output=True, text=True
            )
            if result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
    except:
        pass
    return "-"


def cleanup_zombie_processes():
    """清理僵尸进程"""
    for name in list(PROCESSES.keys()):
        process = PROCESSES[name]
        if process.poll() is not None:
            del PROCESSES[name]
        else:
            port = OUR_PORTS.get(name)
            if port and not check_service("127.0.0.1", port):
                try:
                    process.kill()
                except:
                    pass
                del PROCESSES[name]


def show_status():
    """显示服务状态"""
    cleanup_zombie_processes()

    chroma_host = os.getenv("CHROMA_SERVER_HOST", "127.0.0.1")
    chroma_port = int(os.getenv("CHROMA_SERVER_PORT", "9898"))
    mcp_host = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    mcp_port = int(os.getenv("MCP_SERVER_PORT", "9766"))

    embedding_mode = os.getenv("EMBEDDING_MODE", "cloud")
    rerank_enabled = os.getenv("RERANK_ENABLED", "true").lower() == "true"
    rerank_mode = os.getenv("RERANK_MODE", "local")

    print("\n服务状态:")
    print("-" * 70)
    print(f"{'服务':<20} {'状态':<10} {'PID':<10} {'端口/配置':<10}")
    print("-" * 70)

    if embedding_mode == "local":
        embedding_url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
        try:
            embedding_port = int(embedding_url.split(":")[-1].split("/")[0])
        except:
            embedding_port = 1234
        embedding_status = "运行中" if check_service("127.0.0.1", embedding_port) else "未运行"
        embedding_pid = PROCESSES.get("Embedding")
        if embedding_pid:
            embedding_pid = str(embedding_pid.pid) if embedding_pid.poll() is None else get_pid_by_port(embedding_port)
        else:
            embedding_pid = get_pid_by_port(embedding_port)
        print(f"{'Embedding (本地)':<20} {embedding_status:<10} {embedding_pid:<10} {embedding_port:<10}")
    else:
        embedding_url = os.getenv("EMBEDDING_CLOUD_URL", "https://api.siliconflow.cn/v1/embeddings")
        try:
            domain = embedding_url.split("//")[1].split("/")[0]
        except:
            domain = "unknown"
        print(f"{'Embedding (云端)':<20} {'已配置':<10} {'-':<10} {domain:<10}")

    chroma_status = "运行中" if check_service(chroma_host, chroma_port) else "未运行"
    chroma_pid = PROCESSES.get("ChromaDB")
    if chroma_pid:
        chroma_pid = str(chroma_pid.pid) if chroma_pid.poll() is None else get_pid_by_port(chroma_port)
    else:
        chroma_pid = get_pid_by_port(chroma_port)
    print(f"{'ChromaDB':<20} {chroma_status:<10} {chroma_pid:<10} {chroma_port:<10}")

    mcp_status = "运行中" if check_service(mcp_host, mcp_port) else "未运行"
    mcp_pid = PROCESSES.get("MCP")
    if mcp_pid:
        mcp_pid = str(mcp_pid.pid) if mcp_pid.poll() is None else get_pid_by_port(mcp_port)
    else:
        mcp_pid = get_pid_by_port(mcp_port)
    print(f"{'MCP':<20} {mcp_status:<10} {mcp_pid:<10} {mcp_port:<10}")

    if rerank_enabled:
        if rerank_mode == "local":
            rerank_url = os.getenv("RERANK_LOCAL_URL", "http://127.0.0.1:5001")
            try:
                rerank_port = int(rerank_url.split(":")[-1].split("/")[0])
            except:
                rerank_port = 5001
            rerank_status = "运行中" if check_service("127.0.0.1", rerank_port) else "未运行"
            rerank_pid = PROCESSES.get("Rerank")
            if rerank_pid:
                rerank_pid = str(rerank_pid.pid) if rerank_pid.poll() is None else get_pid_by_port(rerank_port)
            else:
                rerank_pid = get_pid_by_port(rerank_port)
            print(f"{'Rerank (本地)':<20} {rerank_status:<10} {rerank_pid:<10} {rerank_port:<10}")
        else:
            rerank_url = os.getenv("RERANK_CLOUD_URL", "https://api.cohere.com/v1/rerank")
            try:
                domain = rerank_url.split("//")[1].split("/")[0]
            except:
                domain = "unknown"
            print(f"{'Rerank (云端)':<20} {'已配置':<10} {'-':<10} {domain:<10}")
    else:
        print(f"{'Rerank':<20} {'未启用':<10} {'-':<10} {'-':<10}")

    print("-" * 70)


def show_config():
    """显示当前配置"""
    print("\n当前配置:")
    print("-" * 60)
    embedding_mode = os.getenv("EMBEDDING_MODE", "cloud")
    print(f"Embedding 模式: {embedding_mode}")
    if embedding_mode == "cloud":
        print(f"  URL: {os.getenv('EMBEDDING_CLOUD_URL', 'https://api.siliconflow.cn/v1/embeddings')}")
        api_key = os.getenv('EMBEDDING_CLOUD_API_KEY', '')
        if api_key:
            print(f"  API Key: ****{api_key[-4:]}")
        else:
            print(f"  API Key: 未配置")
        print(f"  模型: {os.getenv('EMBEDDING_CLOUD_MODEL', 'BAAI/bge-m3')}")
        print(f"  维度: {os.getenv('EMBEDDING_CLOUD_DIM', '1024')}")
    else:
        print(f"  URL: {os.getenv('EMBEDDING_LOCAL_URL', 'http://127.0.0.1:1234/v1/embeddings')}")
        print(f"  模型路径: {os.getenv('EMBEDDING_LOCAL_MODEL_PATH', 'data/models/embedding')}")
        print(f"  维度: {os.getenv('EMBEDDING_LOCAL_DIM', '2560')}")

    rerank_enabled = os.getenv("RERANK_ENABLED", "true").lower() == "true"
    print(f"\nRerank 启用: {rerank_enabled}")
    if rerank_enabled:
        rerank_mode = os.getenv("RERANK_MODE", "local")
        print(f"  模式: {rerank_mode}")
        if rerank_mode == "cloud":
            print(f"  URL: {os.getenv('RERANK_CLOUD_URL', 'https://api.cohere.com/v1/rerank')}")
            api_key = os.getenv('RERANK_CLOUD_API_KEY', '')
            if api_key:
                print(f"  API Key: ****{api_key[-4:]}")
            else:
                print(f"  API Key: 未配置")
            print(f"  模型: {os.getenv('RERANK_CLOUD_MODEL', 'rerank-multilingual-v3.0')}")
        else:
            print(f"  URL: {os.getenv('RERANK_LOCAL_URL', 'http://127.0.0.1:5001')}")
            print(f"  模型路径: {os.getenv('RERANK_LOCAL_MODEL_PATH', 'data/models/rerank')}")

    print(f"\nChromaDB: {os.getenv('CHROMA_SERVER_HOST', '127.0.0.1')}:{os.getenv('CHROMA_SERVER_PORT', '9898')}")
    print(f"MCP: {os.getenv('MCP_SERVER_HOST', '127.0.0.1')}:{os.getenv('MCP_SERVER_PORT', '9766')}")
    print(f"\n切块策略: {os.getenv('CHUNK_TEMPLATE', 'academic')}")


def check_dependencies() -> list:
    """检查依赖服务"""
    errors = []
    chroma_host = os.getenv("CHROMA_SERVER_HOST", "127.0.0.1")
    chroma_port = int(os.getenv("CHROMA_SERVER_PORT", "9898"))

    embedding_mode = os.getenv("EMBEDDING_MODE", "cloud")
    if embedding_mode == "local":
        embedding_url = os.getenv("EMBEDDING_LOCAL_URL", "http://127.0.0.1:1234/v1/embeddings")
        try:
            embedding_port = int(embedding_url.split(":")[-1].split("/")[0])
        except:
            embedding_port = 1234
        if not check_service("127.0.0.1", embedding_port):
            errors.append("Embedding 本地服务未运行")

    if not check_service(chroma_host, chroma_port):
        errors.append("ChromaDB 服务未运行")

    return errors


def check_orphan_records():
    """检查孤立记录"""
    try:
        import chromadb
        from config.settings import get_collection_name
        from core.scheduler import get_scheduler
        from core.repository import DocumentRepository

        client = chromadb.HttpClient(
            host=os.getenv("CHROMA_SERVER_HOST", "127.0.0.1"),
            port=int(os.getenv("CHROMA_SERVER_PORT", "9898")),
        )
        client.heartbeat()

        collection_name = get_collection_name()
        collection = client.get_collection(name=collection_name)
        emb_proxy = get_scheduler()
        repo = DocumentRepository(collection, emb_proxy)

        docs_dir = str(ROOT / "data" / "docs")
        orphans = repo.check_orphan_records(docs_dir)

        if orphans:
            print(f"\n  [!] 检测到 {len(orphans)} 个孤立记录（本地文件已删除）")
            print(f"  使用 'python db_manage.py clean' 命令清理")
            return True
        return False
    except Exception:
        return False


def main():
    """主函数"""
    chroma_host = os.getenv("CHROMA_SERVER_HOST", "127.0.0.1")
    chroma_port = int(os.getenv("CHROMA_SERVER_PORT", "9898"))
    mcp_host = os.getenv("MCP_SERVER_HOST", "127.0.0.1")
    mcp_port = int(os.getenv("MCP_SERVER_PORT", "9766"))

    rerank_enabled = os.getenv("RERANK_ENABLED", "true").lower() == "true"
    rerank_mode = os.getenv("RERANK_MODE", "local")

    check_orphan_records()

    while True:
        print("\n" + "=" * 60)
        print("  Ezy-RAG V0.0.17 - 服务管理")
        print("=" * 60)
        print("1. 查看服务状态")
        print("2. 查看当前配置")
        print("3. 启动服务")
        print("4. 停止服务")
        print("5. 重启服务")
        print("6. 修改配置（调用 init.py）")
        print("7. 退出")

        choice = input("\n请选择 (1-7): ").strip()

        if choice == "1":
            show_status()
        elif choice == "2":
            show_config()
        elif choice == "3":
            embedding_mode = os.getenv("EMBEDDING_MODE", "cloud")
            rerank_enabled = os.getenv("RERANK_ENABLED", "true").lower() == "true"
            rerank_mode = os.getenv("RERANK_MODE", "local")
            
            print("\n启动服务:")
            print("1. 启动所有服务")
            if embedding_mode == "local":
                print("2. 启动 Embedding (本地)")
            else:
                print("2. Embedding (云端 - 无需启动)")
            print("3. 启动 ChromaDB")
            print("4. 启动 MCP")
            if rerank_enabled and rerank_mode == "local":
                print("5. 启动 Rerank")
                print("6. 返回")
            else:
                print("5. 返回")
            sub_choice = input("\n请选择: ").strip()
            if sub_choice == "1":
                if embedding_mode == "local":
                    start_service("Embedding", "local.embedding", "127.0.0.1", OUR_PORTS["Embedding"])
                start_service("ChromaDB", "servers.chroma", chroma_host, chroma_port)
                start_service("MCP", "servers.mcp", mcp_host, mcp_port)
                if rerank_enabled and rerank_mode == "local":
                    start_service("Rerank", "local.rerank", "127.0.0.1", OUR_PORTS["Rerank"])
            elif sub_choice == "2":
                if embedding_mode == "local":
                    start_service("Embedding", "local.embedding", "127.0.0.1", OUR_PORTS["Embedding"])
                else:
                    print("[INFO] 云端模式无需启动本地 Embedding 服务")
            elif sub_choice == "3":
                start_service("ChromaDB", "servers.chroma", chroma_host, chroma_port)
            elif sub_choice == "4":
                errors = check_dependencies()
                if errors:
                    print("\n启动失败:")
                    for error in errors:
                        print(f"  [!] {error}")
                    print("\n请先启动依赖服务后再试。")
                else:
                    start_service("MCP", "servers.mcp", mcp_host, mcp_port)
            elif sub_choice == "5" and rerank_enabled and rerank_mode == "local":
                start_service("Rerank", "local.rerank", "127.0.0.1", OUR_PORTS["Rerank"])
            elif sub_choice == "5" or sub_choice == "6":
                continue
            else:
                print("无效的选择")
        elif choice == "4":
            embedding_mode = os.getenv("EMBEDDING_MODE", "cloud")
            rerank_enabled = os.getenv("RERANK_ENABLED", "true").lower() == "true"
            rerank_mode = os.getenv("RERANK_MODE", "local")
            
            print("\n停止服务:")
            print("1. 停止所有服务")
            if embedding_mode == "local":
                print("2. 停止 Embedding (本地)")
            else:
                print("2. Embedding (云端 - 无需停止)")
            print("3. 停止 ChromaDB")
            print("4. 停止 MCP")
            if rerank_enabled and rerank_mode == "local":
                print("5. 停止 Rerank")
                print("6. 返回")
            else:
                print("5. 返回")
            sub_choice = input("\n请选择: ").strip()
            if sub_choice == "1":
                if embedding_mode == "local":
                    stop_service("Embedding")
                stop_service("ChromaDB")
                stop_service("MCP")
                if rerank_enabled and rerank_mode == "local":
                    stop_service("Rerank")
            elif sub_choice == "2":
                if embedding_mode == "local":
                    stop_service("Embedding")
                else:
                    print("[INFO] 云端模式无需停止本地 Embedding 服务")
            elif sub_choice == "3":
                stop_service("ChromaDB")
            elif sub_choice == "4":
                stop_service("MCP")
            elif sub_choice == "5" and rerank_enabled and rerank_mode == "local":
                stop_service("Rerank")
            elif sub_choice == "5" or sub_choice == "6":
                continue
            else:
                print("无效的选择")
        elif choice == "5":
            embedding_mode = os.getenv("EMBEDDING_MODE", "cloud")
            rerank_enabled = os.getenv("RERANK_ENABLED", "true").lower() == "true"
            rerank_mode = os.getenv("RERANK_MODE", "local")
            
            print("\n重启服务:")
            print("1. 重启所有服务")
            if embedding_mode == "local":
                print("2. 重启 Embedding (本地)")
            else:
                print("2. Embedding (云端 - 无需重启)")
            print("3. 重启 ChromaDB")
            print("4. 重启 MCP")
            if rerank_enabled and rerank_mode == "local":
                print("5. 重启 Rerank")
                print("6. 返回")
            else:
                print("5. 返回")
            sub_choice = input("\n请选择: ").strip()
            if sub_choice == "1":
                if embedding_mode == "local":
                    stop_service("Embedding")
                stop_service("ChromaDB")
                stop_service("MCP")
                if rerank_enabled and rerank_mode == "local":
                    stop_service("Rerank")
                time.sleep(2)
                if embedding_mode == "local":
                    start_service("Embedding", "local.embedding", "127.0.0.1", OUR_PORTS["Embedding"])
                start_service("ChromaDB", "servers.chroma", chroma_host, chroma_port)
                start_service("MCP", "servers.mcp", mcp_host, mcp_port)
                if rerank_enabled and rerank_mode == "local":
                    start_service("Rerank", "local.rerank", "127.0.0.1", OUR_PORTS["Rerank"])
            elif sub_choice == "2":
                if embedding_mode == "local":
                    stop_service("Embedding")
                    time.sleep(2)
                    start_service("Embedding", "local.embedding", "127.0.0.1", OUR_PORTS["Embedding"])
                else:
                    print("[INFO] 云端模式无需重启本地 Embedding 服务")
            elif sub_choice == "3":
                stop_service("ChromaDB")
                time.sleep(2)
                start_service("ChromaDB", "servers.chroma", chroma_host, chroma_port)
            elif sub_choice == "4":
                stop_service("MCP")
                time.sleep(2)
                start_service("MCP", "servers.mcp", mcp_host, mcp_port)
            elif sub_choice == "5" and rerank_enabled and rerank_mode == "local":
                stop_service("Rerank")
                time.sleep(2)
                start_service("Rerank", "local.rerank", "127.0.0.1", OUR_PORTS["Rerank"])
            elif sub_choice == "5" or sub_choice == "6":
                continue
            else:
                print("无效的选择")
        elif choice == "6":
            subprocess.run([sys.executable, "init.py"], cwd=ROOT)
            load_dotenv(ROOT / "config" / ".env", override=True)
        elif choice == "7":
            for name in list(PROCESSES.keys()):
                stop_service(name)
            break
        else:
            print("无效的选择")


if __name__ == "__main__":
    main()
