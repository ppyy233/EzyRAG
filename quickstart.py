# -*- coding: utf-8 -*-
"""
Ezy-RAG — 一键启动脚本
用法: python quickstart.py
"""
import os
import sys
import time
import socket
import subprocess
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config.version import VERSION, VERSION_DISPLAY


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_step(step: str, description: str):
    print(f"\n  Step {step}: {description}")
    print("  " + "-" * 40)


def print_ok(message: str):
    print(f"  ✓ {message}")


def print_error(message: str):
    print(f"  ✗ {message}")


def print_warn(message: str):
    print(f"  ⚠ {message}")


def print_info(message: str):
    print(f"  {message}")


def check_port(host: str, port: int) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def check_python() -> tuple:
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        return False, f"{version.major}.{version.minor}.{version.micro}"
    return True, f"{version.major}.{version.minor}.{version.micro}"


def check_uv() -> bool:
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            cwd=ROOT
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_env() -> bool:
    return (ROOT / "config" / ".env").exists()


def check_frontend() -> bool:
    return (ROOT / "frontend" / "dist" / "index.html").exists()


def create_minimal_config():
    """创建最小配置，用于启动 Web API"""
    config_dir = ROOT / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    env_path = config_dir / ".env"
    if not env_path.exists():
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(f"# Ezy-RAG {VERSION_DISPLAY} — 环境配置\n")
            f.write("# 由 quickstart.py 创建的最小配置\n\n")
            f.write("# ----- Embedding 配置 -----\n")
            f.write("EMBEDDING_MODE=cloud\n\n")
            f.write("# 云端配置\n")
            f.write("EMBEDDING_CLOUD_URL=https://api.siliconflow.cn/v1/embeddings\n")
            f.write("EMBEDDING_CLOUD_API_KEY=\n")
            f.write("EMBEDDING_CLOUD_MODEL=BAAI/bge-m3\n")
            f.write("EMBEDDING_CLOUD_DIM=\n\n")
            f.write("# 本地配置\n")
            f.write("EMBEDDING_LOCAL_URL=http://127.0.0.1:1234/v1/embeddings\n")
            f.write("EMBEDDING_LOCAL_MODEL_PATH=data/models/embedding\n")
            f.write("EMBEDDING_LOCAL_DIM=\n\n")
            f.write("# ----- Rerank 配置 -----\n")
            f.write("RERANK_ENABLED=true\n")
            f.write("RERANK_MODE=cloud\n\n")
            f.write("# 云端配置\n")
            f.write("RERANK_CLOUD_URL=https://api.siliconflow.cn/v1/rerank\n")
            f.write("RERANK_CLOUD_API_KEY=\n")
            f.write("RERANK_CLOUD_MODEL=BAAI/bge-reranker-v2-m3\n\n")
            f.write("# 本地配置\n")
            f.write("RERANK_LOCAL_URL=http://127.0.0.1:5001\n")
            f.write("RERANK_LOCAL_MODEL_PATH=data/models/rerank\n\n")
            f.write("# ----- 服务配置 -----\n")
            f.write("CHROMA_SERVER_HOST=127.0.0.1\n")
            f.write("CHROMA_SERVER_PORT=9898\n")
            f.write("MCP_SERVER_HOST=127.0.0.1\n")
            f.write("MCP_SERVER_PORT=9766\n\n")
            f.write("# ----- 切块策略 -----\n")
            f.write("CHUNK_TEMPLATE=academic\n")
        print_ok("已创建 config/.env")
    
    config_path = config_dir / "config.json"
    if not config_path.exists():
        import json
        config = {
            "collection": {"name": "default_collection"},
            "docs": {"dir": "data/docs"},
            "web": {"dir": "data/web"},
            "chroma": {"dir": "data/chroma_db"},
            "chunk": {
                "templates": {
                    "academic": {
                        "name": "英文文献专用",
                        "chunk_size": 2000,
                        "overlap": 200,
                        "strategy": "recursive",
                        "separators": ["\n\n", "\n", "\r\n", "。", ". ", "！", "?", "？", "!", "；", ";", "，", ",", "、", " ", ""]
                    },
                    "chinese": {
                        "name": "中文专用",
                        "chunk_size": 1500,
                        "overlap": 150,
                        "strategy": "recursive",
                        "separators": ["\n\n", "\n", "。", "！", "？", "；", "，", "、", " ", ""]
                    },
                    "code": {
                        "name": "数据分析/代码专用",
                        "chunk_size": 3000,
                        "overlap": 300,
                        "strategy": "flat",
                        "separators": ["\n\n\n", "\n\n", "\n", ". ", " ", ""]
                    },
                    "custom": {
                        "name": "自定义模板",
                        "chunk_size": 1000,
                        "overlap": 100,
                        "strategy": "recursive",
                        "separators": ["\n\n", "\n", " ", ""]
                    }
                },
                "default_template": "academic"
            },
            "retrieval": {"k": 5, "fetch_k": 15}
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print_ok("已创建 config/config.json")


def build_frontend():
    """构建前端"""
    frontend_dir = ROOT / "frontend"
    
    if not (frontend_dir / "node_modules").exists():
        print_info("安装前端依赖...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(frontend_dir),
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print_error(f"安装前端依赖失败: {result.stderr}")
            return False
        print_ok("前端依赖已安装")
    
    print_info("构建前端...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print_error(f"构建前端失败: {result.stderr}")
        return False
    print_ok("前端已构建")
    return True


def start_web_server():
    """启动 Web API 服务器"""
    host = "127.0.0.1"
    port = 9767
    
    if check_port(host, port):
        print_warn(f"端口 {port} 已被占用，Web API 可能已在运行")
        return None
    
    print_info("启动 Web API 服务器...")
    process = subprocess.Popen(
        [sys.executable, "-m", "servers.web"],
        cwd=str(ROOT),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    )
    
    start_time = time.time()
    while time.time() - start_time < 15:
        if check_port(host, port):
            print_ok(f"Web API 已启动 (端口 {port})")
            return process
        time.sleep(0.5)
    
    print_error("Web API 启动超时")
    return None


def main():
    print_header(f"Ezy-RAG {VERSION_DISPLAY} Quickstart")
    
    print_step("1", "检查环境")
    ok, ver = check_python()
    if ok:
        print_ok(f"Python {ver}")
    else:
        print_error(f"Python {ver}（需要 >= 3.11）")
        return
    
    if check_uv():
        print_ok("uv 已安装")
    else:
        print_warn("uv 未安装（非必需）")
    
    print_step("2", "检查配置")
    if not check_env():
        print_warn("配置文件不存在，创建最小配置...")
        create_minimal_config()
    else:
        print_ok("配置文件已存在")
    
    print_step("3", "检查前端")
    if not check_frontend():
        print_warn("前端未构建，开始构建...")
        if not build_frontend():
            print_error("前端构建失败，请手动运行: cd frontend && npm install && npm run build")
            print_info("继续启动后端服务...")
    else:
        print_ok("前端已构建")
    
    print_step("4", "启动服务")
    process = start_web_server()
    if not process:
        return
    
    print_step("5", "打开浏览器")
    url = "http://127.0.0.1:9767"
    print_info(f"访问地址: {url}")
    try:
        webbrowser.open(url)
        print_ok("浏览器已打开")
    except:
        print_warn("无法自动打开浏览器，请手动访问")
    
    print_header("Quickstart 完成！")
    print("\n  所有服务已启动！")
    print_info("前端界面: http://127.0.0.1:9767")
    print_info("按 Ctrl+C 停止服务")
    print("")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n  正在停止服务...")
        if process:
            process.terminate()
            process.wait()
        print_ok("服务已停止")


if __name__ == "__main__":
    main()
