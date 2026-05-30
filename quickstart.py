# -*- coding: utf-8 -*-
"""
Ezy-RAG — 一键启动脚本
用法: python quickstart.py

功能:
  - 首次使用: 环境检查 → 安装依赖 → 交互配置 → 启动服务 → 打开浏览器
  - 日常启动: 检查环境 → 启动服务 → 打开浏览器
"""
import sys
import json
import time
import socket
import subprocess
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config.version import VERSION, VERSION_DISPLAY


# ============================================================
#  UI 工具函数
# ============================================================

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


def input_with_default(prompt: str, default: str = "") -> str:
    """带默认值的输入，回车返回默认值"""
    if default:
        user_input = input(f"  {prompt} [{default}]: ").strip()
        return user_input if user_input else default
    else:
        return input(f"  {prompt}: ").strip()


def input_masked(prompt: str) -> str:
    """密码输入，显示 masked"""
    user_input = input(f"  {prompt}: ").strip()
    return user_input


# ============================================================
#  环境检查
# ============================================================

def check_port(host: str, port: int) -> bool:
    """检查端口是否被占用"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def check_python() -> tuple:
    """检查 Python 版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        return False, f"{version.major}.{version.minor}.{version.micro}"
    return True, f"{version.major}.{version.minor}.{version.micro}"


def check_uv() -> bool:
    """检查 uv 是否安装"""
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True, text=True, cwd=ROOT
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_node() -> bool:
    """检查 Node.js 是否安装"""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, cwd=ROOT
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_env() -> bool:
    """检查 .env 是否存在"""
    return (ROOT / "config" / ".env").exists()


def check_venv() -> bool:
    """检查虚拟环境是否已创建"""
    return (ROOT / ".venv").exists()


def check_frontend() -> bool:
    """检查前端是否已构建"""
    return (ROOT / "frontend" / "dist" / "index.html").exists()


def step_check_environment() -> bool:
    """Step 1: 检查环境"""
    print_step("1", "检查环境")

    ok, ver = check_python()
    if ok:
        print_ok(f"Python {ver}")
    else:
        print_error(f"Python {ver}（需要 >= 3.11）")
        return False

    if check_uv():
        print_ok("uv 已安装")
    else:
        print_error("uv 未安装（必需）")
        print_info("安装方法: curl -LsSf https://astral.sh/uv/install.sh | sh")
        return False

    if check_node():
        print_ok("Node.js 已安装")
    else:
        print_warn("Node.js 未安装（前端构建需要）")

    return True


# ============================================================
#  依赖安装
# ============================================================

def install_python_deps() -> bool:
    """安装 Python 依赖"""
    if check_venv():
        print_ok("Python 虚拟环境已存在")
        return True

    print_info("创建虚拟环境并安装 Python 依赖...")
    result = subprocess.run(
        ["uv", "sync"],
        cwd=str(ROOT),
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print_error(f"安装 Python 依赖失败: {result.stderr}")
        return False
    print_ok("Python 依赖已安装")
    return True


def install_frontend() -> bool:
    """安装前端依赖并构建"""
    frontend_dir = ROOT / "frontend"

    if check_frontend():
        print_ok("前端已构建")
        return True

    if not check_node():
        print_warn("Node.js 未安装，跳过前端构建")
        print_info("请手动运行: cd frontend && npm install && npm run build")
        return True

    if not (frontend_dir / "node_modules").exists():
        print_info("安装前端依赖...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(frontend_dir),
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print_error(f"安装前端依赖失败: {result.stderr}")
            return False
        print_ok("前端依赖已安装")

    print_info("构建前端...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(frontend_dir),
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print_error(f"构建前端失败: {result.stderr}")
        return False
    print_ok("前端已构建")
    return True


def step_install_dependencies() -> bool:
    """Step 2: 安装依赖"""
    print_step("2", "安装依赖")

    if not install_python_deps():
        return False

    if not install_frontend():
        return False

    return True


# ============================================================
#  端口冲突处理
# ============================================================

def read_port_from_env(key: str, default: int) -> int:
    """从 .env 读取端口配置"""
    try:
        env_path = ROOT / "config" / ".env"
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        if k.strip() == key and v.strip().isdigit():
                            return int(v.strip())
    except:
        pass
    return default


def get_pid_on_port(port: int) -> str:
    """获取占用端口的进程 PID"""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True
        )
        for line in result.stdout.split('\n'):
            if f":{port}" in line and "LISTENING" in line:
                return line.split()[-1]
    except:
        pass
    return ""


def kill_process_on_port(port: int) -> bool:
    """杀掉占用端口的进程"""
    pid = get_pid_on_port(port)
    if not pid:
        return False
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True
        )
        time.sleep(0.5)
        return not check_port("127.0.0.1", port)
    except:
        return False


def handle_port_conflict(port: int, service_name: str) -> tuple:
    """
    处理端口冲突，返回 (success, port)
    success: True=端口可用, False=用户放弃
    port: 最终使用的端口号
    """
    if not check_port("127.0.0.1", port):
        return True, port

    print()
    print_warn(f"端口 {port} ({service_name}) 已被占用")
    print()
    print("  1. 杀掉占用进程，继续")
    print("  2. 输入新端口")
    print("  3. 跳过此服务")

    while True:
        choice = input("\n  选择 (1-3): ").strip()

        if choice == '1':
            if kill_process_on_port(port):
                print_ok(f"已释放端口 {port}")
                return True, port
            else:
                print_error(f"无法释放端口 {port}，请手动处理")

        elif choice == '2':
            new_port_str = input(f"  输入新端口: ").strip()
            if new_port_str.isdigit() and 1024 <= int(new_port_str) <= 65535:
                new_port = int(new_port_str)
                if check_port("127.0.0.1", new_port):
                    print_warn(f"端口 {new_port} 也被占用")
                    continue
                print_ok(f"将使用端口 {new_port}")
                return True, new_port
            else:
                print_error("无效的端口号")

        elif choice == '3':
            print_info(f"跳过 {service_name}")
            return False, port

        else:
            print_error("请输入 1-3")


# ============================================================
#  交互配置
# ============================================================

def step_interactive_config() -> bool:
    """Step 3: 交互配置（仅 .env 不存在时）"""
    print_step("3", "配置")

    if check_env():
        print_ok("配置文件已存在，跳过配置")
        return True

    env = {}

    # --- 服务端口 ---
    print()
    print_info("▸ 服务端口")
    print_info("─" * 40)

    # ChromaDB 端口
    chroma_port_str = input_with_default("ChromaDB 端口", "9898")
    if not chroma_port_str.isdigit() or not (1024 <= int(chroma_port_str) <= 65535):
        print_error("无效端口，使用默认值 9898")
        chroma_port_str = "9898"
    success, chroma_port = handle_port_conflict(int(chroma_port_str), "ChromaDB")
    if not success:
        print_warn("跳过 ChromaDB 端口配置")
        chroma_port = 9898
    env['CHROMA_SERVER_HOST'] = '127.0.0.1'
    env['CHROMA_SERVER_PORT'] = str(chroma_port)

    # Web API 端口
    web_port_str = input_with_default("Web API 端口", "9767")
    if not web_port_str.isdigit() or not (1024 <= int(web_port_str) <= 65535):
        print_error("无效端口，使用默认值 9767")
        web_port_str = "9767"
    success, web_port = handle_port_conflict(int(web_port_str), "Web API")
    if not success:
        print_warn("跳过 Web API 端口配置")
        web_port = 9767

    # MCP 端口（固定 9766，不询问）
    env['MCP_SERVER_HOST'] = '127.0.0.1'
    env['MCP_SERVER_PORT'] = '9766'

    # --- Embedding ---
    print()
    print_info("▸ Embedding（向量化）")
    print_info("─" * 40)
    print_info("模式: cloud (云端)")

    env['EMBEDDING_MODE'] = 'cloud'
    env['EMBEDDING_CLOUD_URL'] = input_with_default(
        "URL", "https://api.siliconflow.cn/v1/embeddings"
    )
    env['EMBEDDING_CLOUD_MODEL'] = input_with_default("模型", "BAAI/bge-m3")
    env['EMBEDDING_CLOUD_DIM'] = ''

    while True:
        api_key = input_masked("API Key (必填)")
        if api_key:
            env['EMBEDDING_CLOUD_API_KEY'] = api_key
            break
        print_error("API Key 不能为空")

    # --- Rerank ---
    print()
    print_info("▸ Rerank（重排序）")
    print_info("─" * 40)

    rerank_enabled = input_with_default("是否启用 Rerank", "Y").lower()
    if rerank_enabled == 'n':
        env['RERANK_ENABLED'] = 'false'
        env['RERANK_MODE'] = 'cloud'
        env['RERANK_CLOUD_URL'] = ''
        env['RERANK_CLOUD_API_KEY'] = ''
        env['RERANK_CLOUD_MODEL'] = ''
        print_info("已禁用 Rerank")
    else:
        env['RERANK_ENABLED'] = 'true'
        env['RERANK_MODE'] = 'cloud'
        print_info("模式: cloud (云端)")

        env['RERANK_CLOUD_URL'] = input_with_default(
            "URL", "https://api.siliconflow.cn/v1/rerank"
        )
        env['RERANK_CLOUD_MODEL'] = input_with_default("模型", "BAAI/bge-reranker-v2-m3")

        api_key = input_masked("API Key (可选，回车跳过)")
        env['RERANK_CLOUD_API_KEY'] = api_key

    # --- 切块策略 ---
    print()
    print_info("▸ 切块策略")
    print_info("─" * 40)

    templates = {
        '1': ('academic', '英文文献专用'),
        '2': ('chinese', '中文专用'),
        '3': ('code', '数据分析/代码专用'),
    }

    print_info("  1. academic - 英文文献专用")
    print_info("  2. chinese  - 中文专用")
    print_info("  3. code     - 数据分析/代码专用")

    template_choice = input_with_default("选择模板", "1")
    if template_choice in templates:
        env['CHUNK_TEMPLATE'] = templates[template_choice][0]
    else:
        print_error("无效选择，使用默认值 academic")
        env['CHUNK_TEMPLATE'] = 'academic'

    # --- 确认 ---
    print()
    print_header("配置确认")

    rerank_status = "禁用" if env['RERANK_ENABLED'] == 'false' else f"cloud, {env['RERANK_CLOUD_MODEL']}"
    print_info(f"  Embedding: cloud, {env['EMBEDDING_CLOUD_MODEL']}")
    print_info(f"  Rerank:    {rerank_status}")
    print_info(f"  ChromaDB:  {env['CHROMA_SERVER_HOST']}:{env['CHROMA_SERVER_PORT']}")
    print_info(f"  Web API:   127.0.0.1:{web_port}")
    print_info(f"  切块模板:  {env['CHUNK_TEMPLATE']}")

    confirm = input("\n  确认写入配置文件? [Y/n]: ").strip().lower()
    if confirm == 'n':
        print_warn("已取消配置")
        return False

    # --- 写入 .env ---
    config_dir = ROOT / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    env_path = config_dir / ".env"
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f"# Ezy-RAG {VERSION_DISPLAY} — 环境配置\n")
        f.write("# 由 quickstart.py 创建\n\n")

        f.write("# ----- Embedding 配置 -----\n")
        f.write(f"EMBEDDING_MODE={env.get('EMBEDDING_MODE', 'cloud')}\n\n")
        f.write("# 云端配置\n")
        f.write(f"EMBEDDING_CLOUD_URL={env.get('EMBEDDING_CLOUD_URL', '')}\n")
        f.write(f"EMBEDDING_CLOUD_API_KEY={env.get('EMBEDDING_CLOUD_API_KEY', '')}\n")
        f.write(f"EMBEDDING_CLOUD_MODEL={env.get('EMBEDDING_CLOUD_MODEL', '')}\n")
        f.write(f"EMBEDDING_CLOUD_DIM={env.get('EMBEDDING_CLOUD_DIM', '')}\n\n")
        f.write("# 本地配置\n")
        f.write("EMBEDDING_LOCAL_URL=http://127.0.0.1:1234/v1/embeddings\n")
        f.write("EMBEDDING_LOCAL_MODEL_PATH=data/models/embedding\n")
        f.write("EMBEDDING_LOCAL_DIM=\n\n")

        f.write("# ----- Rerank 配置 -----\n")
        f.write(f"RERANK_ENABLED={env.get('RERANK_ENABLED', 'true')}\n")
        f.write(f"RERANK_MODE={env.get('RERANK_MODE', 'cloud')}\n\n")
        f.write("# 云端配置\n")
        f.write(f"RERANK_CLOUD_URL={env.get('RERANK_CLOUD_URL', '')}\n")
        f.write(f"RERANK_CLOUD_API_KEY={env.get('RERANK_CLOUD_API_KEY', '')}\n")
        f.write(f"RERANK_CLOUD_MODEL={env.get('RERANK_CLOUD_MODEL', '')}\n\n")
        f.write("# 本地配置\n")
        f.write("RERANK_LOCAL_URL=http://127.0.0.1:5001\n")
        f.write("RERANK_LOCAL_MODEL_PATH=data/models/rerank\n\n")

        f.write("# ----- 服务配置 -----\n")
        f.write(f"CHROMA_SERVER_HOST={env.get('CHROMA_SERVER_HOST', '127.0.0.1')}\n")
        f.write(f"CHROMA_SERVER_PORT={env.get('CHROMA_SERVER_PORT', '9898')}\n")
        f.write(f"MCP_SERVER_HOST={env.get('MCP_SERVER_HOST', '127.0.0.1')}\n")
        f.write(f"MCP_SERVER_PORT={env.get('MCP_SERVER_PORT', '9766')}\n\n")

        f.write("# ----- 切块策略 -----\n")
        f.write(f"CHUNK_TEMPLATE={env.get('CHUNK_TEMPLATE', 'academic')}\n")

    print_ok("已写入 config/.env")

    # --- 创建 config.json（如不存在）---
    config_path = config_dir / "config.json"
    if not config_path.exists():
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
                "default_template": env.get('CHUNK_TEMPLATE', 'academic')
            },
            "retrieval": {"k": 5, "fetch_k": 15}
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print_ok("已创建 config/config.json")

    return True


# ============================================================
#  启动服务
# ============================================================

def start_service(module: str, port: int, name: str) -> subprocess.Popen | None:
    """启动单个服务，返回进程对象"""
    if check_port("127.0.0.1", port):
        print_ok(f"{name} 已在运行 (端口 {port})")
        return None

    print_info(f"启动 {name}...")
    process = subprocess.Popen(
        [sys.executable, "-m", module],
        cwd=str(ROOT),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    )

    start_time = time.time()
    while time.time() - start_time < 10:
        if check_port("127.0.0.1", port):
            print_ok(f"{name} 已启动 (端口 {port})")
            return process
        time.sleep(0.5)

    print_error(f"{name} 启动超时")
    return None


def step_start_services() -> tuple:
    """Step 4: 启动服务，返回 (chroma_process, web_process)"""
    print_step("4", "启动服务")

    # 读取端口配置
    chroma_port = read_port_from_env('CHROMA_SERVER_PORT', 9898)

    chroma_process = start_service("servers.chroma", chroma_port, "ChromaDB")
    web_process = start_service("servers.web", 9767, "Web API")

    return chroma_process, web_process


# ============================================================
#  打开浏览器
# ============================================================

def step_open_browser():
    """Step 5: 打开浏览器"""
    print_step("5", "打开浏览器")

    url = "http://127.0.0.1:9767"
    print_info(f"访问地址: {url}")

    try:
        webbrowser.open(url)
        print_ok("浏览器已打开")
    except:
        print_warn("无法自动打开浏览器，请手动访问")


# ============================================================
#  主流程
# ============================================================

def main():
    print_header(f"Ezy-RAG {VERSION_DISPLAY} Quickstart")

    # Step 1: 环境检查
    if not step_check_environment():
        return

    # Step 2: 安装依赖（仅首次）
    if not check_venv() or not check_frontend():
        if not step_install_dependencies():
            return
    else:
        print_step("2", "依赖")
        print_ok("所有依赖已安装")

    # Step 3: 配置（仅 .env 不存在时）
    if not step_interactive_config():
        return

    # Step 4: 启动服务
    chroma_process, web_process = step_start_services()

    # Step 5: 打开浏览器
    step_open_browser()

    # 完成
    print_header("Quickstart 完成！")
    print()
    print_info("按 Ctrl+C 停止服务")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n  正在停止服务...")
        for proc in [chroma_process, web_process]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except:
                    proc.kill()
        print_ok("服务已停止")


if __name__ == "__main__":
    main()
